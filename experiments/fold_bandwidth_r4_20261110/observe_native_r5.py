"""File/OS only observer; does not attach to AEDT or change solver decisions."""
import argparse
import json
from pathlib import Path
import re
import time
import psutil

def stamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def capture(w, out, seconds):
    owner=json.loads((w/'owner.json').read_text(encoding='utf-8'))
    token=str((w/'tmp').resolve()).replace(chr(92),'/').casefold()+'/'
    seen=set()
    end=time.monotonic()+seconds
    with out.open('x',encoding='utf-8') as f:
        while time.monotonic()<end:
            if (w/'failure.txt').exists() or (w/'done.json').exists():break
            for p in psutil.process_iter(['name','cmdline','create_time']):
                info=p.info
                if (info['name'] or '').casefold()!='hf3d.exe':continue
                try:
                    if not any(q.pid==owner['pid'] and q.create_time()==owner['create_time'] for q in p.parents()):continue
                    key=(p.pid,info['create_time'])
                    if key in seen:continue
                    seen.add(key)
                    cmd=' '.join(info['cmdline'] or [])
                    row=dict(at=stamp(),solver_pid=p.pid,solver_create_time=key[1],aedt_pid=owner['pid'],
                        aedt_create_time=owner['create_time'],verified_owned_ancestry=True,
                        isolated_scratch=token in cmd.replace(chr(92),'/').casefold(),
                        actual_14core_1group=bool(re.search(r'-max_processors 14(?:\s|$)',cmd)
                                                    and re.search(r'-numParallelGroups 1(?:\s|$)',cmd)))
                    f.write(json.dumps(row)+'\n');f.flush()
                except (psutil.NoSuchProcess,psutil.AccessDenied):continue
            time.sleep(.3)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('output',type=Path);p.add_argument('--seconds',type=int,default=600)
    a=p.parse_args();capture(a.run,a.output,a.seconds)
