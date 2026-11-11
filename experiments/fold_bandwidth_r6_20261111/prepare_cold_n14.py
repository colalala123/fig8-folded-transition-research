"""R6 2.3 唯一N14冷启动退路，保留所有旧证据。仅准备，不启动。"""
import argparse,shutil
from common_r6 import *

def prepare(previous,dest):
    if dest.exists():raise RuntimeError('冷启动目录已存在，不覆盖')
    rec=read(previous/'runs/S1_BASE_N14/RUN_RECORD.json')
    txt=(previous/'runs/S1_BASE_N14/native/reopened_convergence.txt').read_text(encoding='utf-8-sig')
    if rec['new_Analyze_requested']!=0 or 'Completed : N/A' not in txt or list((previous/'ledger').glob('Analyze_*.json')):
        raise RuntimeError('并非已核验的零Analyze无缓存情形')
    if not rec['cleanup']['released']:raise RuntimeError('桌面清理未确认')
    # Exclusive historical release marker prevents granting a second cold attempt.
    write(previous/'cold_restart_release.json',dict(at=now(),case='S1_BASE_N14',cold_restart_ordinal=1,
        destination=str(dest),plan_section='R6 2.3',reason='原生收敛表没有16轮，缓存不通过；旧numerical_pass=false是解析器标签，并非一次最终数值不达标。'))
    dest.mkdir();(dest/'ledger').mkdir()
    shutil.copytree(previous/'baseline_ref',dest/'baseline_ref')
    cfg=read(previous/'authorization.json')
    cfg['historical_hashes'].update({str(p):sha(p) for p in [previous/'STOP.json',previous/'cold_restart_release.json',previous/'runs/S1_BASE_N14/native/reopened_convergence.txt']})
    cfg.update(cold_restart_case='S1_BASE_N14',cold_restart_ordinal=1,at=now(),
               explanation='按R6仅因缓存核验失败新增一次N14冷启动，计入1a5次和总187次；失败不得再次冷启动。')
    write(dest/'authorization.json',cfg)
    repair=read(previous/'prelaunch_repair_v2.json');repair['authorization_sha256']=sha(dest/'authorization.json')
    write(dest/'prelaunch_repair_v2.json',repair)
    for case in (BASES[1],BASES[2],*STEPS):
        w=dest/'runs'/case
        for k in ('input','evidence','native'):(w/k).mkdir(parents=True)
        freeze=read(previous/'runs'/case/'input/freeze.json')
        freeze.update(authorization_sha256=sha(dest/'authorization.json'),resume=False,inherited_Analyze=0,inherited_geometry=False,cache_recovery_ordinal=0)
        if case==BASES[1]:freeze.update(cold_restart_ordinal=1,failed_geometry_record=str(previous/'runs'/case/'RUN_RECORD.json'))
        write(w/'input/freeze.json',freeze)
    write(dest/'release_1a.json',dict(at=now(),plan_commit=cfg['plan_commit'],authorization_sha256=sha(dest/'authorization.json')))
    shutil.copyfile(previous/'sweep_role_confirmation.json',dest/'sweep_role_confirmation.json')
    out=HERE/'cache_validation'
    out.mkdir(exist_ok=False)
    shutil.copyfile(previous/'runs/S1_BASE_N14/native/reopened_convergence.txt',out/'N14_empty_convergence.txt')
    write(out/'RESOLUTION.json',dict(at=now(),cache_valid=False,new_Analyze=0,cold_restart_authorized=True,
        raw_stop_label='R6数值停止',corrected_classification='缓存核验技术失败；不是最终网格或S参数不达标',
        original_records_unchanged=True,cold_restart_limit=1,prior_geometry_total=3,prior_Analyze_total=10))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('previous',type=Path);p.add_argument('dest',type=Path)
    a=p.parse_args();prepare(a.previous.resolve(),a.dest.resolve())
