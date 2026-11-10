"""One isolated, blocking R5 staged geometry. No queue, hooks, GUI, or external AEDT polling.

Adapted from the user's wideband_resolve.py lifecycle, not its Z03 physics.
Importing this module is offline. One call site, at most 14 actual invocations per geometry.
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

from staged_mesh_r5 import LIMITS, NumericalStop, history, next_stage, check_transition

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
DESIGN='Wideband vertical transition'
SETUP='Setup19'

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

BASES=('S1_BASE_N04','S1_BASE_N14','S1_BASE_N08')

def verify_prior(root,case):
    if (root/'STOP_R5.json').exists():raise RuntimeError('R5 stop active')
    if case not in BASES:raise RuntimeError('This runner only covers 1a')
    for prior in BASES[:BASES.index(case)]:
        w=root/'runs'/prior
        gate=read(w/'review'/'REVIEW_R5.json')
        if not gate['baseline_pass'] or gate['native_sha256']!=sha(w/'native/full_modes.npz') or (w/'failure.txt').exists():
            raise RuntimeError('Prior R5 baseline did not pass: '+prior)

def charge(root,case,w,label,record):
    # Exclusive durable event files are the ledger. Requests count even when the API fails.
    if record['Analyze_requested']==0:
        used=list((root/'ledger').glob('geometry_*.json'))
        if len(used)+1>=LIMITS['1a'] or len(used)+1>=sum(LIMITS.values()):
            raise RuntimeError('Geometry budget exhausted (includes original R4 N04)')
        write(root/'ledger'/f'geometry_{case}.json',dict(case=case,batch='1a',at=now()))
    idx=record['Analyze_requested']
    if idx>=14:raise RuntimeError('R5 14-call cap')
    event=dict(at=now(),case=case,index=idx,stage=label,cores=14,tasks=1,blocking=True,setup=SETUP)
    write(root/'ledger'/f'Analyze_{case}_{idx:02d}.json',event)
    record['Analyze_requested']+=1

def saved_setting(project,setup_values,sweep_values):
    m=model_block(project.read_text(encoding='utf-8'))
    sections=re.findall(r"\$begin 'Setup19'(.*?)\$end 'Setup19'",m.group(),re.S)
    if len(sections)!=1:raise RuntimeError('Missing native saved Setup19')
    sw=re.findall(r"\$begin 'Sweep1'(.*?)\$end 'Sweep1'",sections[0],re.S)
    if len(sw)!=1:raise RuntimeError('Missing native saved Sweep1')
    config=sections[0].split("$begin 'Sweeps'",1)[0]
    for text,vals in ((config,setup_values),(sw[0],sweep_values)):
        for key,value in vals.items():
            found=re.findall(r'^\s*'+re.escape(key)+r'=(.*?)\s*$',text,re.M)
            if len(found)!=1:raise RuntimeError('Saved setting not unique: '+key)
            raw=found[0].strip()
            if isinstance(value,bool):ok=raw.lower()==str(value).lower()
            elif isinstance(value,(float,int)):ok=float(raw)==value
            else:ok=raw.strip("'")==value
            if not ok:raise RuntimeError(f'Saved setting mismatch: {key}={raw}, expected {value!r}')

def is_wave_port(kind):
    return str(kind).replace(' ','').casefold()=='waveport'

def execute(root,case):
    import psutil
    verify_prior(root,case)
    cfg=read(root/'authorization_r5.json')
    if not cfg['human_authorized'] or cfg['limits']!=LIMITS or cfg['total_geometry_limit']!=186:
        raise RuntimeError('R5 authorization mismatch')
    old=root.parent/'fig8_fold_bandwidth_r4_20261110'
    for rel,h in cfg['historical_files'].items():
        if sha(old/rel)!=h:raise RuntimeError('R4 evidence mismatch: '+rel)
    if sha(REPO/cfg['plan_path'])!=cfg['plan_sha256']:raise RuntimeError('R5 plan mismatch')
    w=root/'runs'/case
    write(w/'worker_started.json',dict(at=now(),pid=os.getpid(),create_time=psutil.Process().create_time()))
    app=None;scratch=None;result=None;failure=None;observer_stop=threading.Event();observer=None
    record=dict(case=case,solve_completed=False,numerical_pass=None,design_pass=None,Analyze_requested=0)
    try:
        for rel,h in cfg['code_hashes'].items():
            if sha(REPO/rel)!=h:raise RuntimeError('Worker/config code changed: '+rel)
        freeze=read(w/'input/freeze.json')
        if freeze['authorization_sha256']!=sha(root/'authorization_r5.json'):raise RuntimeError('Resume freeze mismatch')
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
        shutil.copyfile(seed,project)
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
        if pid in existing:
            app=None
            raise RuntimeError('Attached to preexisting desktop; not closing it')
        owner=psutil.Process(pid)
        write(w/'owner.json',dict(pid=pid,create_time=owner.create_time(),port=port,cmdline=owner.cmdline(),at=now()))
        from scratch_guard import configure_scratch,restore_scratch,same_path
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
        setup=app.get_setup(SETUP)
        if setup.is_solved:raise RuntimeError('Fresh geometry unexpectedly solved')
        if [sw.name for sw in setup.sweeps]!=['Sweep1']:raise RuntimeError('Expected only Sweep1')
        sw={'RangeStart':'0.01GHz','RangeEnd':'15GHz','RangeStep':'0.01GHz',
            'Type':'Interpolating','InterpTolerance':1.0,'EnforcePassivity':False}
        acf=w/'worker.acf';shutil.copy2(Path(app.pyaedt_dir)/'misc/pyaedt_local_config.acf',acf)
        for k,v,st in [('NumCores',14,False),('NumEngines',1,False),('ConfigName',f'fig8r5_{port}',True),('DesignType','HFSS',True),('UseAutoSettings',False,False)]:
            if not update_hpc_option(str(acf),k,v,st):raise RuntimeError('ACF update failed: '+k)
        # Observe actual native processes without an external AEDT connection.
        observed=[]
        active_stage=[None]
        def observe():
            seen=set()
            with (w/'evidence/solver_processes.jsonl').open('x',encoding='utf-8') as f:
                while not observer_stop.wait(.25):
                    for p in psutil.process_iter(['name','cmdline','create_time']):
                        try:
                            if (p.info['name'] or '').lower()!='hf3d.exe':continue
                            parents=p.parents()
                            if not any(x.pid==pid and x.create_time()==owner.create_time() for x in parents):continue
                            cmd=' '.join(p.info['cmdline'] or [])
                            key=(p.pid,p.info['create_time'])
                            if key in seen:continue
                            seen.add(key)
                            isolated=str(tmp).replace(chr(92),'/').casefold() in cmd.replace(chr(92),'/').casefold()
                            hpc=bool(re.search(r'-max_processors 14(?:\s|$)',cmd) and re.search(r'-numParallelGroups 1(?:\s|$)',cmd))
                            q=dict(at=now(),pid=p.pid,stage=active_stage[0],scratch_isolated=isolated,
                                   actual_14core_1group=hpc,**p.info)
                            observed.append(q)
                            f.write(json.dumps(q)+'\n');f.flush()
                            if isolated and hpc and not (w/'supervised_start.json').exists():
                                write(w/'supervised_start.json',dict(at=now(),actual_14core_1group=True,process=q))
                        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        observer=threading.Thread(target=observe,daemon=True);observer.start()

        def get_history(path):
            if not app.export_convergence(SETUP,output_file=str(path)):
                raise RuntimeError('Convergence export failed')
            return history(path.read_text(encoding='utf-8-sig'))

        rows=[]
        while True:
            if rows:
                record.update(passes=rows[-1][0],mesh_cells=rows[-1][1],delta_s=rows[-1][2])
            label,passes,percent=next_stage(rows)
            sweep_on=percent is None
            base={'MinimumPasses':passes,'MaximumPasses':passes,'UseMaxTetIncrease':False,
                  'MaxDeltaS':.005,'MinimumConvergedPasses':2}
            setup=app.get_setup(SETUP)
            if not sweep_on and not setup.update({**base,'PercentRefinement':percent}):
                raise RuntimeError('Failed to configure adaptive stage')
            if sweep_on:
                # Do not edit adaptive settings at all for sweep.
                percent=last_percent
            sweep=next(s for s in setup.sweeps if s.name=='Sweep1')
            sweep.auto_update=False
            sweep.props.update({**sw,'IsEnabled':sweep_on})
            if not sweep.update():raise RuntimeError('Failed to configure Sweep1')
            sweep.auto_update=True
            if not app.save_project():raise RuntimeError('Save failed')
            saved_setting(project,{**base,'PercentRefinement':percent},{**sw,'IsEnabled':sweep_on})
            if rows and get_history(w/'native'/f'pre_{label}.txt')!=rows:
                raise NumericalStop('Edit invalidated cached adaptive history; do not restart')
            write(w/'evidence'/f'{label}_settings.json',dict(setup=base,percent=percent,sweep={**sw,'IsEnabled':sweep_on},
                 project_sha256=sha(project),scratch=scratch,pre_history_verified=bool(rows)))
            if not same_path(app.temp_directory,tmp):raise RuntimeError('AEDT scratch mismatch before Analyze')
            if any((p.info['name'] or '').lower()=='hf3d.exe' for p in psutil.process_iter(['name'])):
                raise RuntimeError('An active solver appeared before Analyze; preserving serial guard')
            active_stage[0]=label
            charge(root,case,w,label,record)
            print('ANALYZE_START',case,label,flush=True)
            if not app.analyze_setup(SETUP,acf_file=str(acf),blocking=True,revert_to_initial_mesh=False):
                raise RuntimeError('Analyze returned False: '+label)
            if not app.save_project():raise RuntimeError('Save failed after Analyze')
            path=w/'native'/('convergence.txt' if sweep_on else f'{label}.txt')
            after=get_history(path)
            check_transition(rows,after,passes,sweep=sweep_on)
            messages=list(app.odesktop.GetMessages(app.project_name,app.design_name,0))
            write(w/'evidence'/f'{label}_messages.json',messages)
            if any('[error]' in m.lower() for m in messages):raise RuntimeError('Native AEDT error: '+label)
            current=[q for q in observed if q['stage']==label]
            if not current or not all(q['scratch_isolated'] and q['actual_14core_1group'] for q in current):
                raise RuntimeError('Missing or mismatched owned solver isolation/HPC evidence: '+label)
            write(w/'evidence'/f'{label}_result.json',dict(passes=passes,mesh_cells=after[-1][1],
                  delta_s=after[-1][2],prior_history_unchanged=True,solver_process_count=len(current)))
            print('ANALYZE_RESULT',case,label,after[-1],flush=True)
            if sweep_on:
                if not any('interpolating frequency sweep complete. converged.' in m.lower() for m in messages):
                    raise NumericalStop('No native interpolating sweep convergence evidence')
                break
            last_percent=percent
            rows=after
        record.update(numerical_pass=True)
        app.export_mesh_stats(SETUP,output_file=str(w/'native/mesh.txt'))
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
        if z.shape!=(len(f),24) or not np.isfinite(z).all() or len(f)!=1500 or not np.allclose(f,np.arange(1,1501)/100,atol=1e-9,rtol=0):raise RuntimeError('Invalid native modes')
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
        record['solve_completed']=True
        result=dict(**record,at=now(),native_sha256=sha(w/'native/full_modes.npz'),offline_review_required=True)
    except BaseException as e:
        if isinstance(e,NumericalStop):record['numerical_pass']=False
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
            if not (root/'STOP_R5.json').exists():write(root/'STOP_R5.json',dict(at=now(),case=case,reason='R5 numerical stop' if record['numerical_pass'] is False else 'R5 technical stop; inspect before any continuation',record=record))
        else:
            if not record['numerical_pass'] and not (root/'STOP_R5.json').exists():
                write(root/'STOP_R5.json',dict(at=now(),case=case,reason='R5 numerical stop',record=record))
            write(w/'done.json',result)
        print('TERMINAL',case,'failure' if failure else 'done',flush=True)
    return 1 if failure else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--case',required=True)
    a=p.parse_args()
    with serial_lock(a.runtime):sys.exit(execute(a.runtime,a.case))
