"""R6 授权、账本与独立进程求解；旧目录只读。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from common_r6 import *
from roles_r6 import evaluate,classify
from recovery_r5 import cache_files

PLAN='docs/PLAN_20261110_FOLD_BANDWIDTH_R6.md'

def prepare(root):
    old=root.parent/'fig8_fold_bandwidth_r5_20261111'
    prior=old/'r5_cache_recovery_v1'
    src=prior/'runs/S1_BASE_N14'
    cfg=read(old/'authorization_r5.json')
    if read(prior/'STOP.json')['case']!='S1_BASE_N14':raise RuntimeError('旧停止案例不一致')
    if not read(src/'cleanup.json')['released'] or (src/'model.aedt.lock').exists():raise RuntimeError('原缓存仍被占用')
    old_geo=list((old/'ledger').glob('geometry_*.json'))
    old_calls=list((old/'ledger').glob('Analyze_*.json'))
    if len(old_geo)!=2 or len(old_calls)!=9:raise RuntimeError('历史预算不符')
    gate=read(prior/'runs/S1_BASE_N04/review/REVIEW_R5.json')
    if not gate['baseline_pass'] or gate['native_sha256']!=sha(prior/'runs/S1_BASE_N04/native/full_modes.npz'):raise RuntimeError('N04有效结果不符')
    commit=subprocess.check_output(['git','rev-parse','origin/claude/fold-bandwidth-plan'],cwd=REPO,text=True).strip()
    if not commit.startswith('b917d09'):raise RuntimeError('计划分支已更新，请重新审核')
    if subprocess.check_output(['git','show',commit+':'+PLAN],cwd=REPO)!=(REPO/PLAN).read_bytes():raise RuntimeError('R6文本不符')
    cache=cache_files(src)
    model=read(REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json')
    boxes=read(REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/SLOT_BOXES.json')
    mapping={x['id']:x['boxes'] for x in boxes}
    root.mkdir(exist_ok=False);(root/'ledger').mkdir();(root/'baseline_ref').mkdir()
    shutil.copytree(prior/'runs/S1_BASE_N04/review',root/'baseline_ref/S1_BASE_N04')
    files=[HERE/n for n in ('common_r6.py','roles_r6.py','observer_r6.py','runtime_r6.py','worker_r6.py','review_r6.py')]
    files += [R4/n for n in ('headless_worker_r5.py','scratch_guard.py','native_geometry.py','staged_mesh_r5.py','stage_messages_r5.py','recovery_r5.py','review_r5.py','STAGE1_CRITERIA_R5.json')]
    files += sorted((REPO/'experiments/fold_bandwidth_r2_20261110').glob('*.py'))
    historical={str(p):sha(p) for p in [prior/'STOP.json',old/'STOP_R5.json',old/'authorization_r5.json',src/'RUN_RECORD.json',src/'cleanup.json',src/'input/freeze.json',src/'evidence/adaptive_00_settings.json',prior/'runs/S1_BASE_N04/review/REVIEW_R5.json',prior/'runs/S1_BASE_N04/native/full_modes.npz',*old_geo,*old_calls]}
    config=dict(at=now(),human_authorized=True,plan_path=PLAN,plan_commit=commit,plan_sha256=sha(REPO/PLAN),
        limits=LIMITS,total_geometry_limit=187,prior_geometry_total=3,prior_Analyze_total=10,
        cores=14,tasks=1,serial=True,no_hook=True,aedt_install=cfg['aedt_install'],
        user_authorization='同意R6：允许跨进程缓存续算；1a上限5、总上限187；N14通过后N08，再1b。',
        code_hashes={p.relative_to(REPO).as_posix():sha(p) for p in files},historical_hashes=historical,
        n14_cache_source=str(src),n14_cache_manifest=cache,
        historical_n14_role_note='首段1个命令未保留，按归档记录推断为端口准备进程；由N08冷启动记录事后核验。',
        sweep_role_policy='按阶段核验；最终扫频保持网格历史不变，不要求重新自适应。此语义已向用户提问，未确认前不提交最终扫频。')
    write(root/'authorization.json',config)
    for case in (BASES[1],BASES[2],*STEPS):
        w=root/'runs'/case
        for k in ('input','evidence','native'):(w/k).mkdir(parents=True)
        pred=next(x for x in model['designs'] if x['id']==case)
        hashes={**model['source_hashes'],**{p.relative_to(REPO).as_posix():sha(p) for p in [REPO/'hfss/INV01_A14.aedt',REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json',REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/SLOT_BOXES.json']}}
        if case in BASES:
            for name in ('state.json','sparams.csv'):
                archive=REPO/'data/raw'/pred['source_case']/name
                hashes[archive.relative_to(REPO).as_posix()]=sha(archive)
        write(w/'input/freeze.json',dict(design=pred,expected_boxes=mapping[case],source_hashes=hashes,
              authorization_sha256=sha(root/'authorization.json'),resume=case==BASES[1],inherited_Analyze=1 if case==BASES[1] else 0,
              inherited_geometry=case==BASES[1],cache_recovery_ordinal=1 if case==BASES[1] else 0))
    w=root/'runs'/BASES[1]
    shutil.copyfile(src/'model.aedt',w/'model.aedt')
    shutil.copytree(src/'model.aedtresults',w/'model.aedtresults')
    if cache_files(w)!=cache or cache_files(src)!=cache:raise RuntimeError('缓存副本字节不一致')
    write(root/'release_1a.json',dict(plan_commit=commit,at=now(),authorization_sha256=sha(root/'authorization.json')))

def verify_release(root,case):
    if (root/'STOP.json').exists():raise RuntimeError('本R6停止记录尚未处理')
    c=read(root/'authorization.json')
    if not c['human_authorized'] or c['limits']!=LIMITS or c['total_geometry_limit']!=187:raise RuntimeError('授权或预算不符')
    if sha(REPO/c['plan_path'])!=c['plan_sha256']:raise RuntimeError('R6计划哈希不符')
    for rel,h in c['code_hashes'].items():
        if sha(REPO/rel)!=h:raise RuntimeError('冻结执行代码变化:'+rel)
    for p,h in c['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('历史证据变化:'+p)
    if case not in (BASES[1],BASES[2],*STEPS):raise RuntimeError('该执行器不覆盖此批')
    freeze=read(root/'runs'/case/'input/freeze.json')
    if freeze['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('输入授权哈希不符')
    batch=freeze['design']['batch']
    release=read(root/f'release_{batch}.json')
    if release['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('批次释放文件不符')
    if case==BASES[2] and not read(root/'runs'/BASES[1]/'review/REVIEW_R6.json')['baseline_pass']:
        raise RuntimeError('N14基准未通过')
    if batch=='1b':
        if not read(root/'gate_1a.json')['passed']:raise RuntimeError('三个基准未全部通过')
        for prev in STEPS[:STEPS.index(case)]:
            if not read(root/'runs'/prev/'review/REVIEW_R6.json')['numerical_pass']:
                raise RuntimeError('前一个阶梯点数值验收未通过')
    return c,freeze

def charge(root,case,label,record,freeze):
    batch=freeze['design']['batch']
    ledger=root/'ledger'
    geom=[read(p) for p in ledger.glob('geometry_*.json')]
    if record['Analyze_requested']==0:
        if 3+len(geom)>=187 or (3 if batch=='1a' else 0)+sum(x['batch']==batch for x in geom)>=LIMITS[batch]:
            raise RuntimeError('几何预算已满')
        write(ledger/f'geometry_{case}.json',dict(case=case,batch=batch,at=now()))
    i=record['Analyze_requested']
    if i>=14:raise RuntimeError('单几何最多初始1次、续算12次、扫频1次')
    write(ledger/f'Analyze_{case}_{i:02d}.json',dict(at=now(),case=case,batch=batch,index=i,stage=label,cores=14,tasks=1))
    record['Analyze_requested']+=1

def solve_stage(root,case,w,label,record,freeze,app,acf):
    import psutil
    if label=='final_sweep':
        consent=read(root/'sweep_role_confirmation.json')
        if consent.get('policy')!='stage_specific':raise RuntimeError('最终扫频进程规则待确认')
    out=w/'evidence'/f'{label}_solver.jsonl';stop=w/'evidence'/f'{label}_observer.stop';ready=w/'evidence'/f'{label}_observer.ready'
    with (w/'evidence'/f'{label}_observer.log').open('x',encoding='utf-8') as f:
        p=subprocess.Popen([sys.executable,'-u',str(HERE/'observer_r6.py'),str(w),str(out),str(ready),str(stop)],
             stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+15
            while not ready.exists():
                if p.poll() is not None or time.monotonic()>deadline:raise RuntimeError('独立观察器启动失败')
                time.sleep(.05)
            if any((x.info['name'] or '').lower()=='hf3d.exe' for x in psutil.process_iter(['name'])):raise RuntimeError('出现其他求解，保持串行')
            charge(root,case,label,record,freeze)
            print('ANALYZE_START',case,label,flush=True)
            ok=app.analyze_setup(SETUP,acf_file=str(acf),blocking=True,revert_to_initial_mesh=False)
            write(w/'evidence'/f'{label}_solve_return.json',dict(at=now(),returned_ok=bool(ok)))
        finally:
            stop.touch(exist_ok=False)
            if p.wait(timeout=20)!=0:raise RuntimeError('观察器异常退出')
    if not ok:raise RuntimeError('HFSS求解API返回失败:'+label)
    obs=[json.loads(x) for x in out.read_text(encoding='utf-8').splitlines()]
    return obs

def validate_stage(root,case,w,label,obs):
    q=evaluate(obs,label);write(w/'evidence'/f'{label}_role_check.json',q)
    if not q['passed']:raise RuntimeError('进程角色核验失败:'+json.dumps(q,ensure_ascii=False))
    if case==BASES[2] and label=='adaptive_00':
        first=classify(obs[0]['command_tail'])['role']
        verdict=dict(first_role=first,port_preparation_observed=first in ('-port_adapt','-port_solve'),
            note='N14历史首进程只作推断，不回写其未知命令。')
        write(w/'evidence/n14_hypothesis_check.json',verdict)
        if not verdict['port_preparation_observed']:
            write(root/'N14_NEEDS_REVIEW.json',dict(at=now(),reason='N08首个观察进程非端口准备，按R6将N14改标待核实',first_role=first))
            raise RuntimeError('N08首个观察进程非端口准备，N14待核实')
    if not (w/'supervised_start.json').exists():
        adaptive=[x for x in obs if classify(x['command_tail'])['role']=='-solve_broadband_adapt']
        if adaptive:write(w/'supervised_start.json',dict(at=now(),actual_14core_1group=True,process=adaptive[0]))
    return q

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);prepare(p.parse_args().root.resolve())
