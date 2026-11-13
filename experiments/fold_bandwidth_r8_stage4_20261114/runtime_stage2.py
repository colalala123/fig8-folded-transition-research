"""R8 fail-closed release: prepublished T1, local T2/T3, no stage5."""
from common_stage2 import *
from solve_block import solve_stage
from prepare_r8 import histories,propose_history
import geometry,subprocess,hashlib
def verify_release(root,case):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stopped/paused')
    cfg=read(root/'authorization.json')
    if not cfg['human_authorized'] or cfg['execution_revision']!='R8_STAGE4' or cfg['batch']!='4' or cfg['limits']!=LIMITS:raise RuntimeError('R8 authorization mismatch')
    if (cfg['prior_geometry_total'],cfg['prior_Analyze_total'],cfg['batch_geometry_limit'],cfg['R8_cumulative_geometry_cap'])!=(133,1226,24,157):raise RuntimeError('budget mismatch')
    if (cfg['cores'],cfg['tasks'],cfg['serial'],cfg['no_hook'])!=(14,1,True,True):raise RuntimeError('resource mismatch')
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen code/data changed '+rel)
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('historical evidence changed '+p)
    if not read(HERE/'offline/TEST_RESULTS.json')['passed']:raise RuntimeError('R8-1 offline gate failed')
    w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id'];i=f['attempt_ordinal'];s=cfg['designs'][p]
    if any((w/n).exists() for n in ('worker_started.json','done.json','failure.txt')):raise RuntimeError('duplicate dispatch prohibited')
    if f['resume'] or f['inherited_Analyze'] or f['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('input auth changed')
    if cfg['case_specs'][case]!=dict(parent_id=p,attempt_ordinal=i) or not 1<=i<=3:raise RuntimeError('unauthorized slot')
    for prev in cfg['parent_order'][:cfg['parent_order'].index(p)]:
        if not read(root/'decisions'/(prev+'_FINAL.json'))['complete']:raise RuntimeError('prior parent incomplete')
    if cfg['parent_order'].index(p)>=4:
        if sum(read(root/'decisions'/(t+'_FINAL.json'))['tuned'] for t in cfg['parent_order'][:4])<2:raise RuntimeError('R8 first four usable <2; stop')
    pred=f['design']
    if i==1:
        if pred['geometry_mm']!=s['geometry_mm'] or pred['prediction']!=s['prediction'] or pred['tuning'] is not None:raise RuntimeError('T1 not frozen law chain')
    else:
        sg=propose_history(histories(root,p,cfg),s['nominal_a_mm'],'folded')
        if not sg['needs_solve'] or sg!=pred['tuning'] or sg['geometry_mm']!=pred['geometry_mm']:raise RuntimeError('T2/T3 not frozen local tuner')
    g=pred['geometry_mm'];dim=geometry.chain.dimensions(g) if hasattr(geometry,'chain') else None
    from presubmit import presubmit
    import chain
    dim=chain.dimensions(g)
    if g['Wm']!=s['geometry_mm']['Wm'] or abs(dim['a_mm']-s['nominal_a_mm'])>1e-8 or abs(dim['g_mm']-s['g_mm'])>1e-8:raise RuntimeError('Wm/a/g changed')
    if not presubmit(g,s['nominal_a_mm'])['can_submit'] or geometry.slot_boxes(g,'folded')!=f['expected_boxes']:raise RuntimeError('geometry mismatch')
    proof=read(root/'publications'/(case+'.json'))
    if not proof['remote_verified'] or proof['authorization_sha256']!=sha(root/'authorization.json') or proof['freeze_sha256']!=sha(w/'input/freeze.json'):raise RuntimeError('not published')
    files={**cfg['code_hashes'],**cfg['frozen_hashes'],(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix():sha(w/'input/freeze.json')}
    for rel,h in files.items():
        if hashlib.sha256(subprocess.check_output(['git','show',proof['commit']+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('publication not bound '+rel)
    if sha(HERE/'pre_solve'/(case+'.json'))!=sha(w/'input/freeze.json'):raise RuntimeError('public input mismatch')
    return cfg,f
