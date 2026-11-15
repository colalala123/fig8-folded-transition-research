"""Explicit one-shot no-Analyze native validation for a frozen R3 case."""
import argparse,os,shutil,socket,sys,traceback
from common_stage2 import *
from prepare_r10 import ROOT
from geometry_gate import check_ir
from native_validation import validate_native

def preflight(root,case):
    import psutil
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);source=w/'input/freeze.json';fz=read(source)
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stopped/paused')
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('resource occupied')
    for rel,h in {**cfg['code_hashes'],**cfg['frozen_hashes'],**cfg['plan_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen file changed '+rel)
    if fz['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('input binding')
    check_ir(fz['design']['cad_ir'])
    out=root/'preflights'/case;out.mkdir(exist_ok=False)
    write(out/'CLAIM.json',dict(at=now(),case=case,input_sha256=sha(source),no_Analyze=True))
    for n in ('tmp','native'):(out/n).mkdir()
    app=None;scratch=None;failed=None;proof=None
    try:
        if shutil.disk_usage(root).free<35*1024**3:raise RuntimeError('free space <35GiB')
        project=out/'model.aedt';shutil.copyfile(REPO/'hfss/INV01_A14.aedt',project)
        os.environ['TEMP']=os.environ['TMP']=str(out/'tmp');os.environ['ANSYSEM_ROOT242']=cfg['aedt_install'];os.environ.pop('PYAEDT_USE_PRE_GRPC_ARGS',None)
        from ansys.aedt.core.generic import general_methods as gm
        gm._get_pids_by_name_windows=lambda name:[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').casefold()==name.casefold()]
        from ansys.aedt.core import Hfss,settings
        settings.grpc_secure_mode=True;settings.grpc_local=True;settings.grpc_listen_all=False;settings.aedt_log_file=str(out/'native/startup.log')
        s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
        app=Hfss(project=str(project),design=DESIGN,version='2024.2',port=port,machine='localhost',new_desktop=True,non_graphical=True,close_on_exit=False)
        owner=psutil.Process(app.desktop_class.aedt_process_id);write(out/'OWNER.json',dict(pid=owner.pid,create_time=owner.create_time(),port=port))
        if Path(app.project_file).resolve()!=project.resolve():raise RuntimeError('wrong project')
        def forbidden(*a,**kw):raise RuntimeError('Analyze forbidden in R11 preflight')
        app.analyze=forbidden;app.analyze_setup=forbidden
        from scratch_guard import configure_scratch,restore_scratch
        scratch=configure_scratch(app,out/'tmp')
        from native_control import apply_case
        geom=apply_case(app,fz['design']);write(out/'GEOMETRY_PROOF.json',geom)
        import geometry
        boxes=native_boxes(project);compare=geometry.compare_boxes(fz['expected_boxes'],boxes)
        write(out/'SLOT_COMPARE.json',compare)
        if not compare['passed']:raise RuntimeError('saved slot readback mismatch')
        v=validate_native(app,fz['design'],out/'design_validation',source)
        if any((p.info['name'] or '').lower()=='hf3d.exe' for p in psutil.process_iter(['name'])):raise RuntimeError('unexpected solver during zero-Analyze validation')
        proof=dict(at=now(),case=case,passed=True,new_Analyze=0,hf3d_seen=False,input_sha256=sha(source),authorization_sha256=sha(root/'authorization.json'),
            native_validation=v,code_hashes={p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    except BaseException:failed=traceback.format_exc();print(failed,flush=True)
    finally:
        cleanup=dict(at=now(),app_created=app is not None,released=False,scratch_restored=False)
        if app is not None:
            if scratch is not None:
                try:cleanup['scratch_restored']=restore_scratch(app,scratch)
                except BaseException:failed=(failed or '')+traceback.format_exc()
            try:cleanup['released']=bool(app.release_desktop(close_projects=True,close_desktop=True))
            except BaseException:failed=(failed or '')+traceback.format_exc()
        write(out/'CLEANUP.json',cleanup)
        if not cleanup['released'] or not cleanup['scratch_restored']:failed=(failed or '')+'\ncleanup not confirmed'
        if failed:
            (out/'failure.txt').write_text(failed,encoding='utf-8')
            if not (root/'STOP.json').exists():write(root/'STOP.json',dict(at=now(),case=case,reason='R12 R4 pre-Analyze native validation/tool failure; stop, no automatic R5',new_Analyze=0))
        else:
            proof['cleanup']=cleanup;write(out/'PASS.json',proof)
        public=HERE/'validation'/case;public.mkdir(parents=True,exist_ok=False)
        for n in ('GEOMETRY_PROOF.json','SLOT_COMPARE.json','CLEANUP.json','PASS.json','failure.txt'):
            if (out/n).exists():shutil.copyfile(out/n,public/n)
        if (out/'design_validation').exists():shutil.copytree(out/'design_validation',public/'design_validation')
        write(public/'MANIFEST.json',{p.relative_to(public).as_posix():sha(p) for p in public.rglob('*') if p.is_file()})
    if failed:raise SystemExit(2)
    print(dict(case=case,passed=True,new_Analyze=0),flush=True)

def aggregate(root):
    from validation_gate import verify_one
    cfg=read(root/'authorization.json')
    for c in cfg['required_preflight_cases']:verify_one(root,c,cfg)
    if list((root/'ledger').glob('Analyze_*.json')):raise RuntimeError('first solve happened before seven-point freeze')
    write(HERE/'validation/ALL_SEVEN.json',dict(at=now(),passed=True,new_Analyze=0,cases=cfg['required_preflight_cases'],
        pass_hashes={c:sha(HERE/'validation'/c/'PASS.json') for c in cfg['required_preflight_cases']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case');a=p.parse_args()
    with serial_lock(ROOT):aggregate(ROOT) if a.case=='aggregate' else preflight(ROOT,a.case)
