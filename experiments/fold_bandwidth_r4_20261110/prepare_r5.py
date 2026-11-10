"""Create a separate R5 runtime once; never mutate the R4 ledger or stop."""
from pathlib import Path
import argparse
import shutil
import subprocess
from headless_worker_r5 import HERE, REPO, BASES, LIMITS, now, read, sha, write, saved_setting
PLAN='docs/PLAN_20261110_FOLD_BANDWIDTH_R5.md'
COMMIT='c4f0667'

def prepare(root):
    previous=root.parent/'fig8_fold_bandwidth_r4_20261110'
    old=read(previous/'budget_ledger.json')
    if old['total_requested']!=1 or old['batches']['1a']['requested']!=1 or len(old['attempts'])!=1 or old['attempts'][0]['case']!=BASES[0]:
        raise ValueError('Unexpected R4 budget; cannot carry forward')
    stop=read(previous/'STOP_R4_HEADLESS_V2.json')
    if stop['case']!=BASES[0] or stop['record']['numerical_pass'] is not False:raise ValueError('Unexpected historical stop')
    commit=subprocess.check_output(['git','rev-parse',COMMIT],cwd=REPO,text=True).strip()
    if subprocess.check_output(['git','rev-parse','origin/claude/fold-bandwidth-plan'],cwd=REPO,text=True).strip()!=commit:
        raise ValueError('Review branch tip changed')
    if subprocess.check_output(['git','show',commit+':'+PLAN],cwd=REPO)!=(REPO/PLAN).read_bytes():
        raise ValueError('Working R5 plan does not match commit')
    f=REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json'
    boxes=f.parent/'SLOT_BOXES.json'
    defs=read(f)
    idx={x['id']:x['boxes'] for x in read(boxes)}
    seed=REPO/'hfss/INV01_A14.aedt'
    saved_setting(seed,{'MaxDeltaS':.005,'MinimumConvergedPasses':2,'UseMaxTetIncrease':False},
                 {'RangeStart':'0.01GHz','RangeEnd':'15GHz','RangeStep':'0.01GHz','Type':'Interpolating','InterpTolerance':1.0})
    hashes=lambda files:{p.relative_to(REPO).as_posix():sha(p) for p in files}
    for rel,h in defs['source_hashes'].items():
        if sha(REPO/rel)!=h:raise ValueError('Frozen input changed: '+rel)
    code=hashes([HERE/n for n in ('headless_worker_r5.py','scratch_guard.py','native_geometry.py','staged_mesh_r5.py',
                                 'prepare_r5.py','review_r5.py','STAGE1_CRITERIA_R5.json')])
    archive_paths=[]
    for x in defs['designs']:
        if x['id'] in BASES:
            archive_paths.extend(REPO/'data/raw'/x['source_case']/n for n in ('state.json','sparams.csv'))
    root.mkdir(exist_ok=False)
    (root/'ledger').mkdir()
    shutil.copyfile(previous/'budget_ledger.json',root/'ledger'/'historical_R4.json')
    write(root/'authorization_r5.json',dict(at=now(),human_authorized=True,plan_path=PLAN,plan_commit=commit,
         plan_sha256=sha(REPO/PLAN),limits=LIMITS,total_geometry_limit=186,prior_geometry_attempts=1,prior_Analyze_requests=1,
         call_policy='1 initial + at most 12 continuations + 1 final sweep per geometry',cores=14,tasks=1,serial=True,
         no_hook=True,scope='this release runner: R5 batch1a, in order N04 redo, N14, N08',code_hashes=code,
         aedt_install=read(previous/'headless_resume_v2.json')['aedt_install'],
         historical_files={rel:sha(previous/rel) for rel in ('authorization.json','budget_ledger.json','STOP.json',
                           'STOP_R4_HEADLESS.json','STOP_R4_HEADLESS_V2.json')},
         stop_resolution='Direct human R5 authorization; historical R4 stop remains unchanged.',
         user_authorization='同意 R5 的两处授权变化（1a 增加 1 次重做 N04，总上限 186；“1 次”按一个几何走完分段加密计）'))
    for case in BASES:
        w=root/'runs'/case
        for n in ('input','native','evidence'):(w/n).mkdir(parents=True)
        write(w/'input/freeze.json',dict(frozen_at=now(),design=next(x for x in defs['designs'] if x['id']==case),
             expected_boxes=idx[case],source_hashes={**defs['source_hashes'],**hashes([f,boxes,seed,*archive_paths])},
             authorization_sha256=sha(root/'authorization_r5.json'),fresh_results=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path)
    prepare(p.parse_args().runtime.resolve())
