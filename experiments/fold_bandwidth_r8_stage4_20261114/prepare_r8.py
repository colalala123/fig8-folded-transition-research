"""R8 independent stage4 authorization/freeze; never reopens old queues."""
import copy,argparse,shutil
from common_stage2 import *
from tuning import *
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r8_stage4_20261114')
OLDROOT=Path('F:/2026-1/circuit/test/output/fig8_r7_3r_20261113')
def histories(root,p,cfg):
    hh=[]
    for i in range(1,4):
        c=p+f'__T{i}';w=case_dir(root,c,cfg)
        if (w/'review/visual_ack.json').exists():
            a=read(w/'review/visual_ack.json')
            if not a['actually_viewed'] or a['plot_sha256']!=sha(w/'review/S11_S21.png') or a['extraction_sha256']!=sha(w/'review/extraction_R2.json'):raise RuntimeError('invalid real-view ACK')
            hh.append(dict(case=c,q=read(w/'review/extraction_R2.json'),tuning=read(w/'input/freeze.json')['design'].get('tuning')))
    return hh
def prepare(root):
    import psutil
    if root.exists():raise RuntimeError('runtime already exists')
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native active')
    audit=read(REPO/'experiments/fold_bandwidth_r7_3r_20261113/FINAL_VERIFICATION.json')
    if (audit['total_geometry'],audit['total_Analyze'],audit['numerical_cases'])!=(133,1226,27) or audit['archive_errors']:raise RuntimeError('prior budget mismatch')
    cfg=copy.deepcopy(read(OLDROOT/'authorization.json'))
    cfg.update(at=now(),batch='4',execution_revision='R8_STAGE4',limits=LIMITS,prior_geometry_total=133,prior_Analyze_total=1226,
        batch_geometry_limit=24,total_geometry_limit=187,R8_cumulative_geometry_cap=157,prior_parent_geometry={},designs={},parent_order=[],case_paths={},case_specs={},
        plan_commit='9f90b07dc4a1d01cfbae58850b47a89c128c080b',
        user_authorization='用户明确同意R8第0节变化：先3.4 R8-1离线推送冻结，D1–D8每项最多3几何，共24；阶段4后停，不进5。',
        historical_hashes={str(OLDROOT/'STOP.json'):sha(OLDROOT/'STOP.json'),str(OLDROOT/'authorization.json'):sha(OLDROOT/'authorization.json'),
          str(REPO/'experiments/fold_bandwidth_r7_3r_20261113/FINAL_MANIFEST.json'):sha(REPO/'experiments/fold_bandwidth_r7_3r_20261113/FINAL_MANIFEST.json')})
    # Old batch limits are historical maxima, never additive authorization transfers.
    for k in ('R7_new_geometry_cap','stage3_prior_geometry','stage3_prior_Analyze','n14_cache_manifest'):cfg.pop(k,None)
    cfg['plan_hashes']['docs/PLAN_20261110_FOLD_BANDWIDTH_R8.md']=sha(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R8.md')
    for rel in read(HERE/'offline/TRAINING.json')['source_sha256']:cfg['historical_hashes'][str(REPO/rel)]=sha(REPO/rel)
    for lp in (OLDROOT/'ledger').glob('*.json'):cfg['historical_hashes'][str(lp)]=sha(lp)
    for c in read(HERE/'offline/T1_GEOMETRIES.json'):
        p=c['id'];cfg['parent_order'].append(p)
        cfg['designs'][p]=dict(**c,kind='EQ',topology='folded',max_Analyze=3,material_role='archived_lossy',board_half_x_mm=15.)
        for i in range(1,4):
            case=p+f'__T{i}';cfg['case_paths'][case]=f'runs/{p}/attempt_{i:03d}';cfg['case_specs'][case]=dict(parent_id=p,attempt_ordinal=i)
    (HERE/'freeze').mkdir();(HERE/'pre_solve').mkdir()
    write(HERE/'freeze/REGISTRY.json',dict(designs=list(cfg['designs'].values()),T1_law_chain='global frozen parameter polynomial, no nearest-point override; J rounding only',
        T1_data_role='prospective test permanently retained',T2_T3_data_role='tuned, never independent test',primary_BW='quadratic platform + tip cost; other five models scored separately',
        archived_width_precision_exception='N04/N14/N08 keep archived Wm exact per R4/R7; new widths and all adjustable dimensions on 0.001 mm grid',stage5_enabled=False))
    write(HERE/'freeze/BUDGET.json',dict(prior_geometry=133,prior_Analyze=1226,new_geometry_cap=24,per_parent_cap=3,per_geometry_API_cap=14,cumulative_stage4_cap=157,total_hard_cap=187,
         stage5_geometry_reserved=30,stage5_authorized=False,old_unused_slots_not_transferred=True))
    cfg['frozen_hashes']={p.relative_to(REPO).as_posix():sha(p) for d in ('offline','freeze') for p in sorted((HERE/d).glob('*.json'))}
    cfg['code_hashes']={**cfg['code_hashes'],**{p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')}}
    root.mkdir(parents=True)
    for n in ('ledger','decisions','model_freeze'):(root/n).mkdir()
    write(root/'authorization.json',cfg);shutil.copyfile(OLDROOT/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:v for k,v in cfg.items() if k not in ('historical_hashes','prior_cases','prior_decisions')})
    for p in cfg['parent_order']:attempt(root,p,1)
    print('PREPARED_R8',root)
def attempt(root,p,i):
    cfg=read(root/'authorization.json');s=cfg['designs'][p];c=p+f'__T{i}';w=case_dir(root,c,cfg)
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists() or w.exists():raise RuntimeError('stop/pause/existing input')
    pred=copy.deepcopy(s);previous=None
    if i==1:pred['tuning']=None
    else:
        hh=histories(root,p,cfg);sg=propose_history(hh,s['nominal_a_mm'],'folded')
        if not sg['needs_solve']:return sg
        pred.update(geometry_mm=sg['geometry_mm'],tuning=sg,screen=sg['screen'],prediction=dict(response_y=sg['predicted_y'],frozen_BW_laws_unchanged=True),data_role='tuned_not_independent_test')
        previous=sha(case_dir(root,p+f'__T{i-1}',cfg)/'review/extraction_R2.json')
    if not pred['screen']['can_submit']:return dict(needs_solve=False,reason='frozen_geometry_screen_fail_skip_no_replacement')
    for n in ('input','native','evidence'):(w/n).mkdir(parents=True)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,design=pred,nominal_a_mm=s['nominal_a_mm'],expected_boxes=geometry.slot_boxes(pred['geometry_mm'],'folded'),
        source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,
        previous_extraction_sha256=previous,solver_started=False)
    for dest in (w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')):write(dest,f)
    return dict(needs_solve=True,case=c)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','attempt']);ap.add_argument('parent',nargs='?');ap.add_argument('i',type=int,nargs='?');a=ap.parse_args()
    print(prepare(ROOT) if a.command=='prepare' else attempt(ROOT,a.parent,a.i))
