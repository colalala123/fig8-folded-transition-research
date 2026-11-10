"""Versioned one-time R5 cache recovery; import and prepare are offline."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from headless_worker_r5 import BASES, HERE, REPO, read, sha, write, now, charge
from staged_mesh_r5 import history, next_stage

REL = 'r5_cache_recovery_v1'
RESUME = BASES[0]

def path_for(root, case):
    return root/REL/'runs'/case

def cache_files(w):
    paths=[w/'model.aedt']
    results=w/'model.aedtresults'
    if not results.is_dir():raise RuntimeError('Missing cached result directory')
    paths+=sorted(p for p in results.rglob('*') if p.is_file())
    if len(paths)<2:raise RuntimeError('Missing cached result files')
    result={}
    for p in paths:
        if p.is_symlink() or p.is_junction() or not p.resolve().is_relative_to(w.resolve()):
            raise RuntimeError('Unsafe cache path')
        if p.name.lower().endswith('.lock'):raise RuntimeError('Cache contains lock')
        result[p.relative_to(w).as_posix()]=sha(p)
    return result

def prepare(root):
    src=root/'runs'/RESUME
    status=read(root/'CURRENT_STATUS.json')
    cfg=read(root/'authorization_r5.json')
    if status['phase']!='stopped_R5_technical' or status['stop_sha256']!=sha(root/'STOP_R5.json'):
        raise RuntimeError('No eligible R5 interruption')
    if not read(src/'cleanup.json')['released'] or (src/'model.aedt.lock').exists():
        raise RuntimeError('Prior cache ownership unclear')
    if not (src/'failure.txt').exists() or (src/'done.json').exists():raise RuntimeError('Not interrupted')
    if sorted(p.name for p in (root/'ledger').glob('Analyze_*.json'))!=['Analyze_S1_BASE_N04_00.json']:
        raise RuntimeError('Unexpected existing Analyze charges')
    if sorted(p.name for p in (root/'ledger').glob('geometry_*.json'))!=['geometry_S1_BASE_N04.json']:
        raise RuntimeError('Unexpected existing geometry charges')
    for rel,h in cfg['code_hashes'].items():
        if sha(REPO/rel)!=h:raise RuntimeError('Original frozen code changed')
    if subprocess.check_output(['git','rev-parse','origin/claude/fold-bandwidth-plan'],cwd=REPO,text=True).strip()!=cfg['plan_commit']:
        raise RuntimeError('Plan branch advanced')
    prior=src/'native/adaptive_00.txt'
    rows=history(prior.read_text(encoding='utf-8-sig'))
    if len(rows)!=16 or rows[-1]!=(16,56998,.016087) or next_stage(rows)!=('adaptive_01',17,10):
        raise RuntimeError('Unexpected historical convergence')
    cache=cache_files(src)
    r=root/REL;r.mkdir(exist_ok=False)
    for case in BASES:
        w=path_for(root,case)
        for k in ('input','native','evidence'):(w/k).mkdir(parents=True)
        shutil.copyfile(root/'runs'/case/'input/freeze.json',w/'input/freeze.json')
    dest=path_for(root,RESUME)
    shutil.copyfile(src/'model.aedt',dest/'model.aedt')
    shutil.copytree(src/'model.aedtresults',dest/'model.aedtresults')
    if cache_files(dest)!=cache or cache_files(src)!=cache:raise RuntimeError('Cache clone mismatch')
    shutil.copyfile(prior,dest/'input/prior_convergence.txt')
    keys=('headless_worker_r5_cache_v1.py','review_r5_cache_v1.py','recovery_r5.py','observe_stage_r5.py','observe_native_r5.py',
          'stage_messages_r5.py','staged_mesh_r5.py','headless_worker_r5.py','scratch_guard.py','native_geometry.py',
          'review_headless.py','review_r5.py','STAGE1_CRITERIA_R5.json')
    write(r/'authorization.json',dict(at=now(),direct_reply='同意，你验证完再推送一遍',one_cache_resume=True,
        no_new_n04_geometry=True,initial_Analyze_charged=1,case_Analyze_cap=14,plan_commit=cfg['plan_commit'],
        frozen_authorization=sha(root/'authorization_r5.json'),resolved_stop_sha256=sha(root/'STOP_R5.json'),
        prior_history_sha256=sha(prior),cached_files=cache,
        code_hashes={p.relative_to(REPO).as_posix():sha(p) for p in (HERE/k for k in keys)},
        freezes={case:sha(path_for(root,case)/'input/freeze.json') for case in BASES}))

def verify_release(root,case):
    if case not in BASES or (root/REL/'STOP.json').exists():raise RuntimeError('Case out of scope or new stop active')
    a=read(root/REL/'authorization.json')
    if not a['one_cache_resume'] or not a['no_new_n04_geometry'] or a['case_Analyze_cap']!=14:
        raise RuntimeError('Invalid recovery authorization')
    if sha(root/'STOP_R5.json')!=a['resolved_stop_sha256'] or sha(root/'authorization_r5.json')!=a['frozen_authorization']:
        raise RuntimeError('Historical stop or authorization changed')
    for rel,h in a['code_hashes'].items():
        if sha(REPO/rel)!=h:raise RuntimeError('Recovery code changed: '+rel)
    w=path_for(root,case)
    if sha(w/'input/freeze.json')!=a['freezes'][case]:raise RuntimeError('Recovery freeze changed')
    for p in BASES[:BASES.index(case)]:
        prior=path_for(root,p)
        gate=read(prior/'review/REVIEW_R5.json')
        if (prior/'failure.txt').exists() or not gate['baseline_pass'] or gate['native_sha256']!=sha(prior/'native/full_modes.npz'):
            raise RuntimeError('Prior R5 baseline not passed: '+p)
    return a

def confirm_cache(root,w,a):
    if cache_files(w)!=a['cached_files'] or sha(w/'input/prior_convergence.txt')!=a['prior_history_sha256']:
        raise RuntimeError('Recovery copy differs from verified clone')
    if (w/'model.aedt.lock').exists() or sorted(p.name for p in (root/'ledger').glob('Analyze_S1_BASE_N04_*.json'))!=['Analyze_S1_BASE_N04_00.json']:
        raise RuntimeError('Recovery already attempted or cache locked')
    return history((w/'input/prior_convergence.txt').read_text(encoding='utf-8-sig'))

def solve_stage(root,case,w,label,record,app,setup,acf):
    """Start an OS-only process before each call. Budget is charged at submission."""
    import psutil
    out=w/'evidence'/f'{label}_solver.jsonl'
    stop=w/'evidence'/f'{label}_observer.stop'
    ready=w/'evidence'/f'{label}_observer.ready'
    log=w/'evidence'/f'{label}_observer.log'
    with log.open('x',encoding='utf-8') as stream:
        p=subprocess.Popen([sys.executable,'-u',str(HERE/'observe_stage_r5.py'),str(w),str(out),str(ready),str(stop)],
                           stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+15
            while not ready.exists():
                if p.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('Independent OS observer did not start')
                time.sleep(.1)
            if any((x.info['name'] or '').casefold()=='hf3d.exe' for x in psutil.process_iter(['name'])):
                raise RuntimeError('External solver appeared before Analyze')
            charge(root,case,w,label,record)
            print('ANALYZE_START',case,label,flush=True)
            ok=app.analyze_setup(setup,acf_file=str(acf),blocking=True,revert_to_initial_mesh=False)
        finally:
            stop.touch(exist_ok=False)
            if p.wait(timeout=20)!=0:raise RuntimeError('Independent OS observer failed')
    if not ok:raise RuntimeError('Analyze returned False: '+label)
    observed=[json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
    if not observed or not all(q['verified_owned_ancestry'] and q['isolated_scratch'] and q['actual_14core_1group'] for q in observed):
        raise RuntimeError('Missing or mismatched real solver evidence: '+label)
    if not (w/'supervised_start.json').exists():
        write(w/'supervised_start.json',dict(at=now(),stage=label,actual_14core_1group=True,process=observed[0]))
    return observed

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path)
    prepare(p.parse_args().runtime.resolve())
