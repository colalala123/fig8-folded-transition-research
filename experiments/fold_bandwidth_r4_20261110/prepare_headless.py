"""Offline preparation only. Does not import PyAEDT or start any process."""
import argparse
from pathlib import Path
from headless_worker import REPO,HERE,LIMITS,read,write,sha,now,patch_template

def prepare(root):
    if read(root/'budget_ledger.json')['total_requested']!=0:raise RuntimeError('Not a fresh campaign')
    if (root/'headless_resume_v1.json').exists():raise RuntimeError('Resume already prepared')
    frozen=REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json'
    f=read(frozen);boxfile=frozen.parent/'SLOT_BOXES.json'
    boxes={x['id']:x['boxes'] for x in read(boxfile)}
    for rel,h in f['source_hashes'].items():
        if sha(REPO/rel)!=h:raise RuntimeError('Frozen source changed: '+rel)
    patch_template((REPO/'hfss/INV01_A14.aedt').read_text(encoding='utf-8'))
    cfg=dict(at=now(),human_authorized=True,mode='per_case_headless_blocking',
        direct_user_request='Read wideband_resolve.py; one Python per point, own headless AEDT, blocking solve, file markers; fix then start background simulation.',
        source_example_sha256=sha(Path('F:/2026-2/wideband_resolve.py')),
        supersedes_stop_sha256=sha(root/'STOP.json'),
        resolution='Latest direct human instruction replaces GUI initialization prerequisite with isolated headless PyAEDT lifecycle. Old STOP preserved.',
        python_requested='D:/miniconda3/envs/fxl/python.exe',python_requested_exists=False,
        python_actual='F:/2026-1/circuit/test/.venv/Scripts/python.exe',python_version='3.12.13',pyaedt_version='0.26.3',
        aedt_install='D:/Program Files/AnsysEM/v242/Win64',
        cores=14,tasks=1,serial=True,hook_enabled=False,batch_limits=LIMITS,total_limit=185,
        geometry_scope='batch1a only in this worker; no implicit authorization of dispatch past gates',
        setup_policy={'MaximumPasses':32,'MinimumPasses':32,'PercentRefinement':15,'MaxDeltaS':.005},
        setup_rationale='Cold-start single-call heuristic, frozen before solve. Archived final22passes/5percent assumes cached staged refinement and cannot be reused as a cold-start mesh policy. 32/15 is NOT a mesh guarantee. Actual100000-112000 and delta<=.005 gates unchanged; fail => stop, not another Analyze.',
        code_hashes={str(p.relative_to(REPO)).replace('\\','/'):sha(p) for p in [HERE/'headless_worker.py',HERE/'native_geometry.py',HERE/'prepare_headless.py']})
    write(root/'headless_resume_v1.json',cfg)
    for d in f['designs']:
        if d['batch']!='1a':continue
        w=root/'runs'/d['id']/'attempt_001';w.mkdir(parents=True,exist_ok=False)
        for sub in ['input','native','result','evidence']:(w/sub).mkdir()
        hashes={**f['source_hashes'],str(frozen.relative_to(REPO)).replace('\\','/'):sha(frozen),str(boxfile.relative_to(REPO)).replace('\\','/'):sha(boxfile)}
        write(w/'input/freeze.json',dict(frozen_at=now(),design=d,expected_boxes=boxes[d['id']],source_hashes=hashes,
            resume_sha256=sha(root/'headless_resume_v1.json'),fresh_results=True,setup_policy=cfg['setup_policy']))
    print('Prepared 3 baseline inputs; Analyze=0; no software launched.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True)
    prepare(ap.parse_args().runtime)
