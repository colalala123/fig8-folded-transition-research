"""Run only fixed local offline tests, capture actual results in a new directory.

No solver/network command path or arbitrary command argument is provided.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import platform
import subprocess
import sys
import numpy as np
import scipy
from common import REPO, write, sha


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    paths=['experiments/fold_bandwidth_r1_20261110/test_r1.py',
           'experiments/fold_bandwidth_phase0_20261110/test_phase0.py',
           'tests/test_research.py', 'tools/verify_archive.py']
    records=[]
    for i,path in enumerate(paths):
        started=datetime.now(timezone.utc).isoformat()
        r=subprocess.run([sys.executable,path],cwd=REPO,capture_output=True,text=True,encoding='utf-8')
        log=out/f'test_{i+1}.txt'
        with log.open('x',encoding='utf8') as stream:stream.write(r.stdout+r.stderr)
        records.append(dict(command=['python',path],started_at_UTC=started,
                            script_sha256=sha(REPO/path),
                            finished_at_UTC=datetime.now(timezone.utc).isoformat(),exit_code=r.returncode,
                            output=log.name,output_sha256=sha(log)))
        print(path,r.returncode)
    summary=dict(actual_execution=True,all_passed=all(r['exit_code']==0 for r in records),
                 environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
                 runs=records,new_Analyze_requests=0,hook_messages=0)
    write(out/'VALIDATION_R1.json',summary)
    if not summary['all_passed']:raise SystemExit(1)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)
