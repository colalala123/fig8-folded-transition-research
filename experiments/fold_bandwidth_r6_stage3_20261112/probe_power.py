"""在独立缓存副本中核验功率后处理；不求解、不改变源文件。"""
import os,sys,json,shutil,socket,traceback
from pathlib import Path
import psutil
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r6_stage2b_20261112'))
from common_stage2 import *
from power_native import export_modes,power_exports
def main(dest):
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('已有桌面/求解，不启动探针')
    source=Path('F:/2026-1/circuit/test/output/fig8_r6_2b_20261112/runs/S2_E2_N04_g0.40/attempt_002')
    if dest.exists():raise RuntimeError('探针目录已存在，不能覆盖重试')
    dest.mkdir(parents=True);(dest/'native').mkdir();(dest/'evidence').mkdir();tmp=dest/'tmp';tmp.mkdir()
    before=sha(source/'model.aedt')
    shutil.copyfile(source/'model.aedt',dest/'model.aedt')
    shutil.copytree(source/'model.aedtresults',dest/'model.aedtresults')
    write(dest/'COPY_PROOF.json',dict(source_project_sha256=before,copied_project_sha256=sha(dest/'model.aedt'),new_Analyze=0))
    os.environ['TEMP']=os.environ['TMP']=str(tmp)
    os.environ['ANSYSEM_ROOT242']='D:/Program Files/AnsysEM/v242/Win64'
    from ansys.aedt.core.generic import general_methods as gm
    gm._get_pids_by_name_windows=lambda n:[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()==n.lower()]
    from ansys.aedt.core import Hfss,settings
    settings.grpc_secure_mode=True;settings.grpc_local=True;settings.grpc_listen_all=False
    settings.aedt_log_file=str(dest/'native/aedt_startup.log')
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
    app=None;scratch=None
    try:
        app=Hfss(project=str(dest/'model.aedt'),design=DESIGN,version='2024.2',port=port,machine='localhost',new_desktop=True,non_graphical=True,close_on_exit=False)
        write(dest/'owner.json',dict(pid=app.desktop_class.aedt_process_id,create_time=psutil.Process(app.desktop_class.aedt_process_id).create_time()))
        from scratch_guard import configure_scratch,restore_scratch
        scratch=configure_scratch(app,tmp)
        def hist(p):
            if not app.export_convergence(SETUP,output_file=str(p)):raise RuntimeError('收敛导出失败')
            return history(p.read_text(encoding='utf-8-sig'))
        export_modes(app,dest/'native/full_modes.npz')
        q=power_exports(app,dest,hist,write)
        write(dest/'PROBE_PASSED.json',dict(**q,source_unchanged=sha(source/'model.aedt')==before))
        print('POWER_PROBE_PASSED',q,flush=True)
    except BaseException:
        (dest/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
    finally:
        if app:
            if scratch:restore_scratch(app,scratch)
            app.release_desktop(close_projects=True,close_desktop=True)
        assert sha(source/'model.aedt')==before
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
