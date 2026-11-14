"""阶段2b独立求解入口的门槛。导入不连接HFSS；没有授权冻结不得运行。"""
import json
import os
import subprocess
import sys
import time
from common_stage2 import *
from budget_stage2 import charge
from tuning import propose
import geometry

def solve_stage(root,case,w,label,record,freeze,app,acf):
    import psutil
    if label=='final_sweep':
        consent=read(root/'sweep_role_confirmation.json')
        if consent.get('policy')!='stage_specific':raise RuntimeError('最终扫频进程规则待确认')
    out=w/'evidence'/f'{label}_solver.jsonl';stop=w/'evidence'/f'{label}_observer.stop';ready=w/'evidence'/f'{label}_observer.ready'
    with (w/'evidence'/f'{label}_observer.log').open('x',encoding='utf-8') as f:
        p=subprocess.Popen([sys.executable,'-u',str(R6/'observer_r6_v2.py'),str(w),str(out),str(ready),str(stop)],
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
