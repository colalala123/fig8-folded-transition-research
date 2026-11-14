"""One bounded tool preflight on already-frozen P13; NO Analyze capability."""
import json,os,shutil,socket,sys,traceback
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;REPO=H.parents[1]
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r6_20261111'))
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r4_20261110'))
from scratch_guard import configure_scratch,restore_scratch
from common_r6 import write,read,sha,now,native_boxes
import native_control

def preflight():
    root=Path('F:/2026-1/circuit/test/output/fig8_r10_preflight_P13_20261115')
    if root.exists():raise RuntimeError('preflight already attempted; no overwrite/retry')
    if any((p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native resource occupied')
    root.mkdir();(root/'tmp').mkdir();(root/'native').mkdir()
    os.environ['TEMP']=os.environ['TMP']=str(root/'tmp');os.environ['ANSYSEM_ROOT242']='D:/Program Files/AnsysEM/v242/Win64'
    os.environ.pop('PYAEDT_USE_PRE_GRPC_ARGS',None)
    from ansys.aedt.core.generic import general_methods as gm
    gm._get_pids_by_name_windows=lambda name:[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').casefold()==name.casefold()]
    from ansys.aedt.core import Hfss,settings
    settings.grpc_secure_mode=True;settings.grpc_local=True;settings.grpc_listen_all=False;settings.aedt_log_file=str(root/'native/startup.log')
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
    source=REPO/'experiments/fold_bandwidth_r10_stage6_r1_20261115/pre_solve/S6R10_P13__T1.json';fz=read(source)
    project=root/'model.aedt';shutil.copyfile(REPO/'hfss/INV01_A14.aedt',project)
    app=None;scratch=None;failed=None;proof=None
    try:
        app=Hfss(project=str(project),design='Wideband vertical transition',version='2024.2',port=port,machine='localhost',new_desktop=True,non_graphical=True,close_on_exit=False)
        owner=psutil.Process(app.desktop_class.aedt_process_id);write(root/'owner.json',dict(pid=owner.pid,create_time=owner.create_time(),port=port,at=now()))
        if Path(app.project_file).resolve()!=project.resolve():raise RuntimeError('wrong project identity')
        def forbidden(*args,**kwargs):raise RuntimeError('Analyze forbidden in preflight')
        app.analyze_setup=forbidden;app.analyze=forbidden
        scratch=configure_scratch(app,root/'tmp')
        geom=native_control.apply_case(app,fz['design']);write(root/'GEOMETRY_PROOF.json',geom)
        observed=native_boxes(project);write(root/'NATIVE_SLOT_BOXES.json',observed)
        sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'));import geometry
        compare=geometry.compare_boxes(fz['expected_boxes'],observed);write(root/'SLOT_COMPARE.json',compare)
        if not compare['passed']:raise RuntimeError('native saved slot coordinates mismatch')
        hf3d=[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='hf3d.exe']
        if hf3d:raise RuntimeError('unexpected solver during no-solve preflight')
        proof=dict(at=now(),passed=True,case='S6R10_P13__T1',frozen_input_sha256=sha(source),new_Analyze=0,hf3d_seen=False,
            native_geometry_and_copper_edges=geom['native_acceptance'],ports_from_saved_AEDT_file=True,slot_comparison=compare,
            geometry_unchanged_from_R10_1=True,code_sha256={p.name:sha(p) for p in (H/'native_control.py',H/'cad_ir.py',H/'preflight_no_solve.py')})
    except BaseException:failed=traceback.format_exc();print(failed,flush=True)
    finally:
        cleanup=dict(at=now(),released=False)
        if app is not None:
            if scratch is not None:cleanup['scratch_restored']=restore_scratch(app,scratch)
            cleanup['released']=bool(app.release_desktop(close_projects=True,close_desktop=True))
        write(root/'CLEANUP.json',cleanup)
        if failed:(root/'failure.txt').write_text(failed,encoding='utf-8')
        elif not cleanup['released']:raise RuntimeError('cleanup not confirmed')
        else:proof['cleanup']=cleanup;write(root/'PASS.json',proof);print(json.dumps(proof,ensure_ascii=False),flush=True)
    if failed:raise SystemExit(2)

if __name__=='__main__':preflight()
