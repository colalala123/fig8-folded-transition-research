"""单点显式后台派发与文件状态读取；不接AEDT、不自动越过审核、不发hook。"""
import argparse
import json
import os
import subprocess
import sys
import time
from common_stage2 import *
from runtime_stage2 import verify_release

def status(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    state=dict(case=case,terminal=False,state='not_started')
    if (w/'failure.txt').exists():return dict(**{**state,'terminal':True,'state':'failure'})
    if (w/'done.json').exists():return dict(**{**state,'terminal':True,'state':'done'})
    if (w/'worker_started.json').exists():
        import psutil
        identity=read(w/'worker_started.json')
        try:
            p=psutil.Process(identity['pid'])
            if abs(p.create_time()-identity['create_time'])>.01:raise RuntimeError('PID复用')
            state.update(state='running',worker_pid=p.pid)
        except (psutil.NoSuchProcess,psutil.AccessDenied,RuntimeError) as e:
            state.update(state='worker_identity_missing_without_terminal',error=str(e))
        last=[]
        for log in sorted((w/'evidence').glob('*_solver.jsonl')):
            lines=log.read_text(encoding='utf-8').splitlines()
            if lines:
                try:last.append(json.loads(lines[-1]))
                except json.JSONDecodeError:pass # 原子整行尚未完成时下次再看，不猜测。
        if last:state['last_solver']=max(last,key=lambda r:r['at'])
    return state

def launch(root,case):
    cfg,freeze=verify_release(root,case)
    w=case_dir(root,case,cfg)
    import psutil
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):
        raise RuntimeError('已有外部求解，保持串行，不派发')
    # 任何异常都保留此独占释放记录，不能删除或自动重试。
    write(w/'launcher_claim.json',dict(at=now(),case=case,freeze_sha256=sha(w/'input/freeze.json')))
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
    with (w/'worker.stdout.log').open('x',encoding='utf-8') as out,(w/'worker.stderr.log').open('x',encoding='utf-8') as err:
        p=subprocess.Popen([sys.executable,'-u',str(HERE/'worker_stage2.py'),'--runtime',str(root),'--case',case],
           cwd=REPO,env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    write(w/'launcher_spawn.json',dict(at=now(),case=case,pid=p.pid))
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        s=status(root,case)
        if s['terminal'] or s['state']=='worker_identity_missing_without_terminal':
            print(json.dumps(s,ensure_ascii=False));return s
        # 端口准备不冒充真实14核；只在观察到自适应角色时报告启动。
        logs=list((w/'evidence').glob('*_solver.jsonl'))
        for log in logs:
            for line in log.read_text(encoding='utf-8').splitlines():
                try:x=json.loads(line)
                except json.JSONDecodeError:continue
                if x['role']=='-solve_broadband_adapt' and x.get('max_processors')==14 and x.get('numParallelGroups')==1 and x.get('verified_owned_ancestry') and x.get('isolated_scratch'):
                    proof=dict(at=now(),case=case,actual_14core_1group=True,observation=x,worker=read(w/'worker_started.json'))
                    write(w/'evidence/actual_start_observed.json',proof)
                    print(json.dumps(proof,ensure_ascii=False));return proof
        if p.poll() is not None:
            print(json.dumps(dict(state='launcher_exited_check_worker_files',spawn_returncode=p.returncode),ensure_ascii=False))
            return status(root,case)
        time.sleep(1)
    s=status(root,case);s['note']='监督窗口结束但没有确认真实自适应启动；未杀进程、未重试。'
    print(json.dumps(s,ensure_ascii=False));return s

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['status','launch']);p.add_argument('root',type=Path);p.add_argument('case')
    a=p.parse_args()
    if a.command=='launch':launch(a.root.resolve(),a.case)
    else:print(json.dumps(status(a.root.resolve(),a.case),ensure_ascii=False,indent=2))
