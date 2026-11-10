"""File-only completion watcher. No AEDT, network, hook, or next-point launch."""
import argparse
import json
from pathlib import Path
import time

def wait(paths):
    start=time.monotonic()
    while time.monotonic()-start<21600:
        found={str(p):('failure' if (p/'failure.txt').exists() else 'done') for p in paths
               if (p/'failure.txt').exists() or (p/'done.json').exists()}
        if len(found)==len(paths):return found
        time.sleep(5)
    return {'status':'watch_timeout_no_retry','seconds':21600}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('paths',nargs='+',type=Path);a.add_argument('--notice',type=Path,required=True)
    q=a.parse_args();result=wait(q.paths)
    with q.notice.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)
