"""R6 独立后台 worker；分段历史与原生进程角色双重核验。"""
import argparse
import os
from pathlib import Path
import shutil
import socket
import sys
import traceback
from common_r6 import *
from runtime_r6 import verify_release,solve_stage,validate_stage
from recovery_r5 import cache_files
from stage_messages_r5 import new_messages

def execute(root,case):
    import psutil
    cfg,freeze=verify_release(root,case)
    w=root/'runs'/case
    resume=freeze['resume']
    write(w/'worker_started.json',dict(at=now(),pid=os.getpid(),create_time=psutil.Process().create_time()))
    app=None;scratch=None;result=None;failure=None
    record=dict(case=case,solve_completed=False,numerical_pass=None,design_pass=None,Analyze_requested=freeze['inherited_Analyze'],inherited_Analyze_requests=freeze['inherited_Analyze'])
    try:
        for rel,h in cfg['code_hashes'].items():
            if sha(REPO/rel)!=h:raise RuntimeError('Worker/config code changed: '+rel)
        freeze=read(w/'input/freeze.json')
        if freeze['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('Resume freeze mismatch')
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
        project=w/'model.aedt'
        if resume:
            if cache_files(w)!=cfg['n14_cache_manifest']:raise RuntimeError('N14缓存字节不符')
            prior=[]
        else:
            if list(w.glob('*.aedtresults')) or project.exists():
                raise RuntimeError('Fresh unsolved project required')
            shutil.copyfile(REPO/'hfss/INV01_A14.aedt',project)
            prior=[]
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
        if Path(app.project_file).resolve()!=project.resolve():raise RuntimeError('Unexpected native project')
        if not resume:
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
        if [sw.name for sw in setup.sweeps]!=['Sweep1']:raise RuntimeError('Expected only Sweep1')
        sw={'RangeStart':'0.01GHz','RangeEnd':'15GHz','RangeStep':'0.01GHz',
            'Type':'Interpolating','InterpTolerance':1.0,'EnforcePassivity':False}
        acf=w/'worker.acf';shutil.copy2(Path(app.pyaedt_dir)/'misc/pyaedt_local_config.acf',acf)
        for k,v,st in [('NumCores',14,False),('NumEngines',1,False),('ConfigName',f'fig8r6_{port}',True),('DesignType','HFSS',True),('UseAutoSettings',False,False)]:
            if not update_hpc_option(str(acf),k,v,st):raise RuntimeError('ACF update failed: '+k)
        def get_history(path):
            if not app.export_convergence(SETUP,output_file=str(path)):
                raise RuntimeError('Convergence export failed')
            return history(path.read_text(encoding='utf-8-sig'))

        rows=prior
        if resume:
            # No geometry/setup edits or solve before proving the reopened history.
            rows=get_history(w/'native/reopened_convergence.txt')
            if len(rows)!=16:
                raise RuntimeError('N14缓存不含完整16轮；不得直接续算')
            if get_history(w/'native/reopened_convergence_repeat.txt')!=rows:
                raise RuntimeError('N14缓存重复导出记录不一致')
            saved_setting(project,{'MinimumPasses':16,'MaximumPasses':16,'PercentRefinement':30,
                         'MaxDeltaS':.005,'MinimumConvergedPasses':2},{**sw,'IsEnabled':False})
            write(w/'evidence/cache_verified.json',dict(at=now(),rows=len(rows),last=rows[-1],before_Analyze=True,
                geometry_unchanged=True,byte_identical_to_retained_cache=True,
                note='旧N14未导出收敛表；R6明确允许以完整16轮原生回读及冻结设置核对接续。',
                historical_first_role_note=cfg['historical_n14_role_note']))
            print('CACHE_VERIFIED',case,rows[-1],flush=True)
            last_percent=30
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
            before_messages=list(app.odesktop.GetMessages(app.project_name,app.design_name,0))
            write(w/'evidence'/f'{label}_before_messages.json',before_messages)
            current=solve_stage(root,case,w,label,record,freeze,app,acf)
            if not app.save_project():raise RuntimeError('Save failed after Analyze')
            path=w/'native'/('convergence.txt' if sweep_on else f'{label}.txt')
            after=get_history(path)
            check_transition(rows,after,passes,sweep=sweep_on)
            all_messages=list(app.odesktop.GetMessages(app.project_name,app.design_name,0))
            messages=new_messages(before_messages,all_messages)
            write(w/'evidence'/f'{label}_messages.json',messages)
            if any('[error]' in m.lower() for m in messages):raise RuntimeError('Native AEDT error: '+label)
            write(w/'evidence'/f'{label}_result.json',dict(passes=passes,mesh_cells=after[-1][1],
                  delta_s=after[-1][2],prior_history_unchanged=True,solver_process_count=len(current)))
            validate_stage(root,case,w,label,current)
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
        record['new_Analyze_requested']=record['Analyze_requested']-record['inherited_Analyze_requests']
        write(w/'RUN_RECORD.json',dict(**record,finished_at=now(),cleanup=cleanup))
        if failure:
            (w/'failure.txt').write_text(failure,encoding='utf-8')
            if not (root/'STOP.json').exists():write(root/'STOP.json',dict(at=now(),case=case,reason='R6数值停止' if record['numerical_pass'] is False else 'R6技术中断；按2.3审核修复和缓存后再接续',record=record))
        else:
            if record['numerical_pass'] is not True and not (root/'STOP.json').exists():
                write(root/'STOP.json',dict(at=now(),case=case,reason='R6数值停止',record=record))
            write(w/'done.json',result)
        print('TERMINAL',case,'failure' if failure else 'done',flush=True)
    return 1 if failure else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--case',required=True)
    a=p.parse_args()
    with serial_lock(a.runtime):sys.exit(execute(a.runtime,a.case))
