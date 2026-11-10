"""One isolated, blocking Fig8 solve. No queue, hooks, GUI, or external AEDT polling.

Adapted from the user's wideband_resolve.py lifecycle, not its Z03 physics.
Importing this module is offline. Exactly one analyze_setup call is present.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import threading
import time
import traceback

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
DESIGN='Wideband vertical transition'
SETUP='Setup19'
LIMITS={'1a':3,'1b':9,'2a':45,'2b':66,'3':42,'4':8,'5':12}

def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,q):
    with Path(p).open('x',encoding='utf-8') as f:
        json.dump(q,f,ensure_ascii=False,indent=2,allow_nan=False,default=str)
        f.flush();os.fsync(f.fileno())

def model_block(text):
    matches=[m for m in re.finditer(r"\$begin 'HFSSModel'.*?\$end 'HFSSModel'",text,re.S)
             if re.search(r"^\s*Name='"+re.escape(DESIGN)+r"'\s*$",m.group(),re.M)]
    if len(matches)!=1:raise ValueError('Target design not unique')
    return matches[0]

def patch_template(text):
    """Only the exact target setup; duplicate strings elsewhere are NOT replaced."""
    m=model_block(text);block=m.group()
    setups=list(re.finditer(r"\$begin 'Setup19'.*?\$end 'Setup19'",block,re.S))
    if len(setups)!=1:raise ValueError('Target setup not unique')
    a=setups[0];s=a.group()
    required={"RangeStart='0.01GHz'":"RangeStart='0.01GHz'",
              "RangeEnd='15GHz'":"RangeEnd='15GHz'",
              "RangeStep='0.01GHz'":"RangeStep='0.01GHz'",
              'MaxDeltaS=0.005':'MaxDeltaS=0.005',
              'MaximumPasses=22':'MaximumPasses=32',
              'MinimumPasses=22':'MinimumPasses=32',
              'PercentRefinement=5':'PercentRefinement=15'}
    for old,new in required.items():
        if len(re.findall(r'^\s*'+re.escape(old)+r'\s*$',s,re.M))!=1:
            raise ValueError('Replacement not unique: '+old)
        s=s.replace(old,new)
    block=block[:a.start()]+s+block[a.end():]
    return text[:m.start()]+block+text[m.end():]

def native_boxes(project):
    s=model_block(Path(project).read_text(encoding='utf-8')).group();out=[]
    for m in re.finditer(r"Name='(StructureBSlot_[^']+)'",s):
        b=re.search(r"\$begin 'BoxParameters'(.*?)\$end 'BoxParameters'",s[m.end():],re.S)
        if not b:raise ValueError('Missing native operand')
        vals=dict(re.findall(r"(\w+)='([^']+)'",b.group(1)))
        keys=('XPosition','YPosition','ZPosition','XSize','YSize','ZSize')
        if any(not re.fullmatch(r'[+-]?[\d.eE+-]+mm',vals.get(k,'')) for k in keys):
            raise ValueError('Native operand not literal mm')
        out.append({'name':m.group(1),'parameters_mm':{k:float(vals[k][:-2]) for k in keys}})
    return out

def convergence(text):
    rows=re.findall(r'^\s*(\d+)\|\s*(\d+)\|\s*([^|]+)\|',text,re.M)
    if not rows:raise ValueError('No convergence table')
    p,n,d=rows[-1];delta=float(d)
    converged=bool(re.search(r'Converged\s*:\s*Yes',text))
    return dict(passes=int(p),mesh_cells=int(n),delta_s=delta,converged=converged,
                numerical_pass=100000<=int(n)<=112000 and delta<=.005 and converged)

@contextmanager
def serial_lock(root):
    import msvcrt
    f=(root/'headless_serial.lock').open('a+b');f.seek(0)
    if f.read(1)==b'':f.write(b'0');f.flush()
    f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
    try:yield
    finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1);f.close()

def charge(root,case):
    # Serial lock held by worker throughout configuration, Analyze, export, cleanup.
    p=root/'budget_ledger.json';b=read(p)
    if {k:v['limit'] for k,v in b['batches'].items()}!=LIMITS:raise RuntimeError('Budget mismatch')
    if b['total_requested']>=185 or b['batches']['1a']['requested']>=3:raise RuntimeError('Budget exhausted')
    if any(x.get('case')==case for x in b['attempts']):raise RuntimeError('Case already charged')
    request=dict(case=case,batch='1a',at=now(),Analyze_requests=1,method='one blocking full adaptive+sweep')
    write(root/(case+'_Analyze_request.json'),request)
    b['total_requested']+=1;b['batches']['1a']['requested']+=1;b['attempts'].append(request)
    tmp=root/(case+'_ledger_next.json');write(tmp,b);os.replace(tmp,p)
    return request

def is_wave_port(kind):
    return str(kind).replace(' ','').casefold()=='waveport'

def execute(root,case):
    import psutil
    if (root/'STOP_R4_HEADLESS_V2.json').exists():
        raise RuntimeError('R4 numerical stop from v2: new explicit recovery instruction/revision required')
    cfg=read(root/'headless_resume_v3.json')
    if cfg['mode']!='per_case_headless_blocking' or not cfg['human_authorized']:raise RuntimeError('Missing authorization')
    auth=read(root/'authorization.json')
    if not auth['execution_authorized'] or auth['batch_Analyze_limits']!=LIMITS or auth['total_Analyze_limit']!=185:
        raise RuntimeError('R4 authorization mismatch')
    if sha(REPO/auth['plan_path'])!=auth['plan_sha256']:raise RuntimeError('R4 plan hash changed')
    if sha(root/'STOP.json')!=cfg['supersedes_stop_sha256']:raise RuntimeError('Wrong stop resolution')
    if sha(root/'STOP_R4_HEADLESS.json')!=cfg['resolved_preflight_stop_sha256']:raise RuntimeError('Preflight resolution mismatch')
    if (root/'STOP_R4_HEADLESS_V3.json').exists():raise RuntimeError('New stop active')
    if case not in ['S1_BASE_N04','S1_BASE_N14','S1_BASE_N08']:raise RuntimeError('Worker limited to batch1a')
    w=root/'runs'/case/cfg['attempt_directories'][case]
    if (w/'worker_started.json').exists():raise RuntimeError('Do not rerun attempt')
    write(w/'worker_started.json',dict(at=now(),pid=os.getpid(),create_time=psutil.Process().create_time()))
    app=None;scratch=None;result=None;failure=None;observer_stop=threading.Event();observer=None
    record=dict(case=case,solve_completed=False,numerical_pass=None,design_pass=None,Analyze_requested=0)
    try:
        for rel,h in cfg['code_hashes'].items():
            if sha(REPO/rel)!=h:raise RuntimeError('Worker/config code changed: '+rel)
        freeze=read(w/'input/freeze.json')
        if freeze['resume_sha256']!=sha(root/'headless_resume_v3.json'):raise RuntimeError('Resume freeze mismatch')
        for rel,h in freeze['source_hashes'].items():
            if sha(REPO/rel)!=h:raise RuntimeError('Frozen model source mismatch: '+rel)
        pred=freeze['design'];g=pred['geometry_mm']
        sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
        from presubmit import presubmit
        import geometry
        gate=presubmit(g,nominal_a=g['Ls3']-g['Ws'])
        write(w/'evidence/presubmit.json',gate)
        if not gate['can_submit']:raise RuntimeError('Geometry screen failed')
        if any((p.info['name'] or '').lower()=='hf3d.exe' for p in psutil.process_iter(['name'])):
            raise RuntimeError('Another solver active; no resource stealing')
        if shutil.disk_usage(root).free<35*1024**3:raise RuntimeError('Disk free <35GiB')
        if list(w.glob('*.aedtresults')):raise RuntimeError('Fresh results directory required')
        project=w/'model.aedt'
        if project.exists():raise RuntimeError('Existing project must not be overwritten')
        seed=REPO/'hfss/INV01_A14.aedt'
        project.write_text(patch_template(seed.read_text(encoding='utf-8')),encoding='utf-8')
        tmp=w/'tmp';tmp.mkdir();os.environ['TEMP']=os.environ['TMP']=str(tmp)
        os.environ['ANSYSEM_ROOT242']=cfg['aedt_install']
        os.environ.pop('PYAEDT_USE_PRE_GRPC_ARGS',None)
        from ansys.aedt.core.generic import general_methods as gm
        def pids_by_name(name):
            return [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').casefold()==name.casefold()]
        gm._get_pids_by_name_windows=pids_by_name
        from ansys.aedt.core import Hfss,settings
        from ansys.aedt.core.application.job_manager import update_hpc_option
        settings.grpc_secure_mode=True;settings.grpc_local=True;settings.grpc_listen_all=False
        settings.aedt_log_file=str(w/'native/aedt_startup.log')
        s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
        existing={p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='ansysedt.exe'}
        write(w/'evidence/start_requested.json',dict(at=now(),port=port,existing_aedt_pids=sorted(existing),non_graphical=True))
        app=Hfss(project=str(project),design=DESIGN,version='2024.2',port=port,machine='localhost',
                 new_desktop=True,non_graphical=True,close_on_exit=False)
        pid=app.desktop_class.aedt_process_id
        if pid in existing:raise RuntimeError('Attached to preexisting desktop')
        owner=psutil.Process(pid)
        write(w/'owner.json',dict(pid=pid,create_time=owner.create_time(),port=port,cmdline=owner.cmdline(),at=now()))
        from scratch_guard import configure_scratch,restore_scratch
        scratch=configure_scratch(app,tmp)
        write(w/'evidence/scratch_readback.json',scratch)
        from native_geometry import apply_folded_geometry
        geom=apply_folded_geometry(app,**{k.lower():v for k,v in g.items()})
        write(w/'evidence/geometry_build.json',geom)
        observed=native_boxes(project);write(w/'evidence/native_slot_boxes.json',observed)
        compare=geometry.compare_boxes(freeze['expected_boxes'],observed)
        write(w/'evidence/slot_comparison.json',compare)
        if not compare['passed']:raise RuntimeError('Native slot coordinates mismatch')
        ports={b.name:dict(b.props) for b in app.boundaries if is_wave_port(b.type)}
        write(w/'evidence/ports.json',ports)
        if set(ports)!={'1','2'} or any(int(v['NumModes'])!=2 for v in ports.values()):
            raise RuntimeError('Two ports with two modes each required')
        setup=app.get_setup(SETUP);sweep=next(x for x in setup.sweeps if x.name=='Sweep1')
        expected={'MaxDeltaS':.005,'MaximumPasses':32,'MinimumPasses':32,'PercentRefinement':15}
        if any(setup.props[k]!=v for k,v in expected.items()):raise RuntimeError('Setup differs from freeze')
        sw={'RangeStart':'0.01GHz','RangeEnd':'15GHz','RangeStep':'0.01GHz','IsEnabled':True}
        if any(sweep.props[k]!=v for k,v in sw.items()):raise RuntimeError('Sweep differs from freeze')
        write(w/'evidence/settings.json',dict(setup=dict(setup.props),sweep=dict(sweep.props),ports=ports,project_sha256=sha(project)))
        acf=w/'worker.acf';shutil.copy2(Path(app.pyaedt_dir)/'misc/pyaedt_local_config.acf',acf)
        for k,v,st in [('NumCores',14,False),('NumEngines',1,False),('ConfigName',f'fig8r4_{port}',True),('DesignType','HFSS',True),('UseAutoSettings',False,False)]:
            if not update_hpc_option(str(acf),k,v,st):raise RuntimeError('ACF update failed: '+k)
        # Passive OS observer is in this same worker, never attaches a second AEDT client.
        def observe():
            seen=set()
            with (w/'evidence/solver_processes.jsonl').open('x',encoding='utf-8') as f:
                while not observer_stop.wait(1):
                    for p in psutil.process_iter(['name','cmdline','create_time']):
                        try:
                            if (p.info['name'] or '').lower()!='hf3d.exe':continue
                            cmd=' '.join(p.info['cmdline'] or [])
                            if str(tmp).replace('\\','/').lower() not in cmd.replace('\\','/').lower():continue
                            key=(p.pid,p.info['create_time'])
                            if key in seen:continue
                            seen.add(key);q=dict(at=now(),pid=p.pid,**p.info)
                            f.write(json.dumps(q)+'\n');f.flush()
                            if '-max_processors 14' in cmd and '-numParallelGroups 1' in cmd and not (w/'supervised_start.json').exists():
                                write(w/'supervised_start.json',dict(at=now(),actual_14core_1group=True,process=q))
                        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        observer=threading.Thread(target=observe,daemon=True);observer.start()
        if any((p.info['name'] or '').lower()=='hf3d.exe' for p in psutil.process_iter(['name'])):
            raise RuntimeError('External solver appeared before Analyze')
        charge(root,case);record['Analyze_requested']=1
        write(w/'analyze_started.json',dict(at=now(),cores=14,tasks=1,blocking=True,setup=SETUP))
        print('ANALYZE_START',case,flush=True)
        if not app.analyze_setup(SETUP,acf_file=str(acf),blocking=True):raise RuntimeError('Analyze returned False')
        record['solve_completed']=True
        if not app.save_project():raise RuntimeError('Save failed')
        app.export_convergence(SETUP,output_file=str(w/'native/convergence.txt'))
        app.export_mesh_stats(SETUP,output_file=str(w/'native/mesh.txt'))
        numeric=convergence((w/'native/convergence.txt').read_text(encoding='utf-8'))
        record.update(numeric);write(w/'evidence/numerical.json',numeric)
        modes=['1:1','1:2','2:1','2:2']
        expr=[f'S({a},{b})' for a in modes for b in modes]+[f'{k}({a})' for k in ['Zo','Gamma'] for a in modes]
        data=app.post.get_solution_data(expressions=expr,setup_sweep_name='Setup19 : Sweep1',domain='Sweep',report_category='Modal Solution Data')
        if not data:raise RuntimeError('No native full-mode solution')
        import numpy as np
        f=np.asarray(data.primary_sweep_values,float)
        unit=data.units_sweeps.get('Freq','')
        scale={'GHz':1.,'MHz':.001,'kHz':1e-6,'Hz':1e-9}[unit];f=f*scale
        z=[]
        for ex in expr:
            _,real=data.get_expression_data(ex,formula='real');_,imag=data.get_expression_data(ex,formula='imag')
            z.append(np.asarray(real,float)+1j*np.asarray(imag,float))
        z=np.asarray(z).T
        if z.shape!=(len(f),24) or not np.isfinite(z).all() or not np.all(np.diff(f)>0):raise RuntimeError('Invalid native modes')
        np.savez_compressed(w/'native/full_modes.npz',f_GHz=f,S=z[:,:16].reshape(-1,4,4),Zo=z[:,16:20],Gamma=z[:,20:24])
        import csv
        with (w/'native/full_modes.csv').open('x',newline='',encoding='utf-8') as fp:
            writer=csv.writer(fp);writer.writerow(['f_GHz']+[f'{ex}_{part}' for ex in expr for part in ['real','imag']])
            for fr,row in zip(f,z):writer.writerow([fr]+[v for val in row for v in [val.real,val.imag]])
        write(w/'native/metadata.json',dict(case=case,geometry=g,mode_order=modes,matrix_convention='output,input',
              normalization='native_HFSS_modal_coefficients_not_yet_power_normalization_certified',
              propagation_evidence='complex Gamma and Zo exported for each mode/frequency; no invented propagation flags',
              full_mode_power_certified=False,frequency_unit=unit))
        if not (w/'supervised_start.json').exists():raise RuntimeError('Missing actual14core process evidence')
        result=dict(**record,at=now(),native_sha256=sha(w/'native/full_modes.npz'),offline_review_required=True)
    except BaseException:
        failure=traceback.format_exc();print(failure,flush=True)
    finally:
        observer_stop.set()
        if observer:observer.join(timeout=5)
        cleanup={'at':now(),'app_created':app is not None,'released':False}
        if app is not None:
            if scratch is not None:
                try:cleanup['scratch_restored']=restore_scratch(app,scratch)
                except BaseException:
                    cleanup['scratch_restore_error']=traceback.format_exc()
                    failure=(failure or '')+'\nScratch restoration failed; see cleanup.json'
            try:cleanup['released']=bool(app.release_desktop(close_projects=True,close_desktop=True))
            except BaseException:cleanup['error']=traceback.format_exc()
        write(w/'cleanup.json',cleanup)
        if app is not None and not cleanup['released']:failure=(failure or '')+'\nAEDT cleanup not confirmed'
        write(w/'RUN_RECORD.json',dict(**record,finished_at=now(),cleanup=cleanup))
        if failure:
            (w/'failure.txt').write_text(failure,encoding='utf-8')
            if not (root/'STOP_R4_HEADLESS_V3.json').exists():write(root/'STOP_R4_HEADLESS_V3.json',dict(at=now(),case=case,reason='worker technical failure; inspect before any continuation',record=record))
        else:
            if not record['numerical_pass'] and not (root/'STOP_R4_HEADLESS_V3.json').exists():
                write(root/'STOP_R4_HEADLESS_V3.json',dict(at=now(),case=case,reason='R4 numerical stop',record=record))
            write(w/'done.json',result)
        print('TERMINAL',case,'failure' if failure else 'done',flush=True)
    return 1 if failure else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--case',required=True)
    a=p.parse_args()
    with serial_lock(a.runtime):sys.exit(execute(a.runtime,a.case))
