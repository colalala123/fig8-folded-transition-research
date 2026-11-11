"""独立只读 OS 观察器；绝不连接 AEDT、不提交仿真。"""
import argparse
import hashlib
import json
import time
import psutil
from common_r6 import read,write,now
from roles_r6 import tail_of_command,classify

def capture(w,out,ready,stop):
    owner=read(w/'owner.json')
    token=str((w/'tmp').resolve()).replace(chr(92),'/').casefold()+'/'
    seen=set();end=time.monotonic()+18000
    with out.open('x',encoding='utf-8') as f:
        write(ready,dict(at=now(),pid=psutil.Process().pid,create_time=psutil.Process().create_time()))
        while not stop.exists():
            if time.monotonic()>end:raise TimeoutError('观察器超时，禁止重发求解')
            for p in psutil.process_iter(['name','cmdline','create_time']):
                info=dict(p.info)
                if (info['name'] or '').casefold()!='hf3d.exe':continue
                try:
                    if not any(a.pid==owner['pid'] and abs(a.create_time()-owner['create_time'])<.001 for a in p.parents()):continue
                    key=(p.pid,info['create_time'])
                    if key in seen:continue
                    cmd=' '.join(info['cmdline'] or [])
                    tail=tail_of_command(info['cmdline'])
                    # Unexpected paths are retained in a local sidecar, not the public command tail.
                    path_found=bool(__import__('re').search(r'[A-Za-z]:[/\\]|\\\\',tail))
                    if path_found:
                        write(w/'evidence'/f'private_command_{p.pid}.json',dict(command=cmd))
                        tail='[未预期路径，详情保留在本地]'
                    q=dict(at=now(),solver_pid=p.pid,solver_create_time=key[1],aedt_pid=owner['pid'],
                           verified_owned_ancestry=True,isolated_scratch=token in cmd.replace(chr(92),'/').casefold(),
                           command_tail=tail,raw_command_sha256=hashlib.sha256(cmd.encode()).hexdigest(),**classify(tail))
                    f.write(json.dumps(q,ensure_ascii=False)+'\n');f.flush()
                    seen.add(key)
            time.sleep(.05)

if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser()
    for k in ('run','output','ready','stop'):p.add_argument(k,type=Path)
    a=p.parse_args();capture(a.run,a.output,a.ready,a.stop)
