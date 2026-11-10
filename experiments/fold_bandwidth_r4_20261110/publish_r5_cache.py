"""Collect terminal evidence for publication, excluding host/credential/cache paths."""
import argparse
import json
from pathlib import Path
import shutil
from headless_worker_r5 import BASES, HERE, read, sha, now, write
from recovery_r5 import REL, path_for, cache_files

def collect(root,case):
    w=path_for(root,case)
    record=read(w/'RUN_RECORD.json')
    if not (w/'done.json').exists() and not (w/'failure.txt').exists():raise RuntimeError('Not terminal')
    auth=read(root/REL/'authorization.json')
    if cache_files(root/'runs'/BASES[0])!=auth['cached_files']:
        raise RuntimeError('Original N04 cache changed')
    out=HERE/'r5_cache_results'/case
    out.mkdir(parents=True,exist_ok=False)
    for name in ('adaptive_00.txt','convergence.txt','reopened_convergence.txt','mesh.txt','full_modes.npz','full_modes.csv','metadata.json'):
        source=w/'native'/name
        if source.exists():shutil.copyfile(source,out/name)
    for name in ('REVIEW_R5.json','extraction_R2.json','S11_S21.png'):
        source=w/'review'/name
        if source.exists():shutil.copyfile(source,out/name)
    for name in ('cache_verified.json','slot_comparison.json'):
        source=w/'evidence'/name
        if source.exists():shutil.copyfile(source,out/name)
    for p in sorted((w/'native').glob('adaptive_*.txt')):
        if not (out/p.name).exists():shutil.copyfile(p,out/p.name)
    stages=[]
    for p in sorted((w/'evidence').glob('*_solver.jsonl')):
        obs=[json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
        stage=p.name.removesuffix('_solver.jsonl')
        stage_result=w/'evidence'/f'{stage}_result.json'
        stage_setting=w/'evidence'/f'{stage}_settings.json'
        saved=read(stage_setting) if stage_setting.exists() else None
        if saved:saved['scratch']={'verified':saved['scratch']['verified']}
        stages.append(dict(stage=stage,os_samples=len(obs),
                           owned_14core_and_isolated=bool(obs) and all(x['verified_owned_ancestry'] and x['actual_14core_1group'] and x['isolated_scratch'] for x in obs),
                           settings=saved,result=read(stage_result) if stage_result.exists() else None,
                           independent_observer_sha256=sha(p)))
    ledger=root/'ledger'
    case_calls=[read(p) for p in sorted(ledger.glob(f'Analyze_{case}_*.json'))]
    budget=dict(geometry_total=1+len(list(ledger.glob('geometry_*.json'))),
                batch_1a_limit=4,total_geometry_limit=186,
                actual_Analyze_total=1+len(list(ledger.glob('Analyze_*.json'))),case_Analyze_calls=case_calls)
    gate=read(w/'review/REVIEW_R5.json') if (w/'review/REVIEW_R5.json').exists() else None
    summary=dict(at=now(),case=case,original_n04_cache_unchanged=True,cache_reopened=(w/'evidence/cache_verified.json').exists(),
                 record={k:v for k,v in record.items() if k!='cleanup'},
                 cleanup={k:v for k,v in record['cleanup'].items() if k in {'app_created','released','scratch_restored'}},
                 baseline_pass=gate['baseline_pass'] if gate else None,stages=stages,budget=budget)
    if (w/'failure.txt').exists():
        # Only include exception type; full log remains local.
        lines=[x for x in (w/'failure.txt').read_text(encoding='utf-8').splitlines() if x.strip()]
        summary['terminal_failure_last_line']=lines[-1].replace(str(root),'[runtime]') if lines else 'Empty failure artifact'
    write(out/'SUMMARY.json',summary)
    write(out/'MANIFEST.json',{p.name:sha(p) for p in sorted(out.iterdir())})
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('case',choices=BASES)
    a=p.parse_args();collect(a.runtime.resolve(),a.case)
