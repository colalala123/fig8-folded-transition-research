"""新工程副本三类建模预检：不Analyze、不改原工程、不消耗几何预算。"""
import sys,os,shutil,socket,traceback
from common_stage2 import *
from native_control import apply_geometry
from prepare_stage3 import rows
def main(dest):
    import psutil
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('已有桌面/求解，不抢占')
    if dest.exists():raise RuntimeError('不覆盖预检')
    dest.mkdir(parents=True);tmp=dest/'tmp';tmp.mkdir()
    src=REPO/'hfss/INV01_A14.aedt';original=sha(src);project=dest/'model.aedt';shutil.copyfile(src,project)
    os.environ['TEMP']=os.environ['TMP']=str(tmp);os.environ['ANSYSEM_ROOT242']='D:/Program Files/AnsysEM/v242/Win64'
    from ansys.aedt.core.generic import general_methods as gm
    gm._get_pids_by_name_windows=lambda n:[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()==n.lower()]
    from ansys.aedt.core import Hfss,settings
    settings.grpc_secure_mode=True;settings.grpc_local=True;settings.grpc_listen_all=False
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
    app=None;scratch=None;proof={}
    try:
        app=Hfss(project=str(project),design=DESIGN,version='2024.2',port=port,machine='localhost',new_desktop=True,non_graphical=True,close_on_exit=False)
        from scratch_guard import configure_scratch,restore_scratch
        scratch=configure_scratch(app,tmp)
        import geometry
        rr=rows()
        # Straight then folded lossless, then widened folded. No cached results.
        tests=[('straight',rr[0],'archived_lossy',15.),('lossless',rr[2],'lossless_control',15.),('boundary',rr[2],'archived_lossy',20.)]
        for label,row,mat,h in [tests[int(sys.argv[2])]]:
            q=apply_geometry(app,row['geometry_mm'],row['topology'],mat,h)
            boxes=native_boxes(project);cmp=geometry.compare_boxes(geometry.slot_boxes(row['geometry_mm'],row['topology']),boxes)
            if not cmp['passed']:raise RuntimeError('预检槽盒不符 '+label)
            proof[label]=dict(build=q,slot_comparison=cmp)
        write(dest/'NATIVE_PREFLIGHT.json',dict(passed=True,new_Analyze=0,source_unchanged=sha(src)==original,proof=proof))
    finally:
        cleanup={}
        if app:
            if scratch:cleanup['scratch_restored']=restore_scratch(app,scratch)
            cleanup['released']=bool(app.release_desktop(close_projects=True,close_desktop=True))
        write(dest/'cleanup.json',cleanup)
        assert sha(src)==original
    print('NATIVE_PREFLIGHT_PASSED',flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
