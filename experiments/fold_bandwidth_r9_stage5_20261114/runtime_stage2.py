"""Fail closed R9 release: immutable code, published geometries, order and conditional gates."""
from common_stage2 import *
from solve_block import solve_stage
from prepare_r9 import histories,suggestion,spec
import geometry,chain,hashlib,subprocess
from presubmit import presubmit
def verify_release(root,case):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stop/pause')
    cfg=read(root/'authorization.json')
    if not cfg['human_authorized'] or cfg['execution_revision']!='R9_STAGE5' or cfg['batch']!='5':raise RuntimeError('R9 authorization')
    if (cfg['prior_geometry_total'],cfg['prior_Analyze_total'],cfg['batch_geometry_limit'],cfg['R9_cumulative_geometry_cap'])!=(151,1406,26,177):raise RuntimeError('budget')
    if (cfg['cores'],cfg['tasks'],cfg['serial'],cfg['no_hook'])!=(14,1,True,True):raise RuntimeError('resources')
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen file changed '+rel)
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('old evidence changed '+p)
    if not read(HERE/'offline/TEST_RESULTS.json')['passed']:raise RuntimeError('offline tests')
    w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id'];i=f['attempt_ordinal'];s=spec(root,p,cfg)
    if any((w/n).exists() for n in ('worker_started.json','done.json','failure.txt')):raise RuntimeError('duplicate dispatch')
    if f['resume'] or f['inherited_Analyze'] or f['authorization_sha256']!=sha(root/'authorization.json') or cfg['case_specs'][case]!=dict(parent_id=p,attempt_ordinal=i):raise RuntimeError('input mismatch')
    for prev in cfg['parent_order'][:cfg['parent_order'].index(p)]:
        if not read(root/'decisions'/(prev+'_FINAL.json'))['complete']:raise RuntimeError('prior incomplete')
    if p in cfg['parent_order'][6:]:
        gate=read(root/'R9_2_PUBLICATION.json')
        for rel,h in gate['hashes'].items():
            if sha(REPO/rel)!=h or hashlib.sha256(subprocess.check_output(['git','show',gate['commit']+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('R9-2 not frozen/published')
    if p.endswith(('W2','W3')):
        d1=read(root/'decisions/S5R9_W1_FINAL.json')
        if not d1['tuned']:raise RuntimeError('W1 not usable; skip W2/W3')
        if p.endswith('W3'):
            d2=read(root/'decisions/S5R9_W2_FINAL.json')
            if not d2['tuned'] or d2['BW15_star']-d1['BW15_star']<.12:raise RuntimeError('W3 condition failed')
    pred=f['design']
    if i==1:
        if pred['geometry_mm']!=s['geometry_mm'] or pred['prediction']!=s['prediction'] or pred['tuning'] is not None:raise RuntimeError('T1 changed')
    else:
        sg=suggestion(root,p,cfg)
        if not sg['needs_solve'] or sg!=pred['tuning'] or sg['geometry_mm']!=pred['geometry_mm']:raise RuntimeError('not frozen tuner')
    g=pred['geometry_mm'];d=chain.dimensions(g)
    if g['Wm']!=s['geometry_mm']['Wm'] or abs(d['a_mm']-s['nominal_a_mm'])>1e-8 or abs(d['g_mm']-s['g_mm'])>1e-8:raise RuntimeError('fixed shape changed')
    if any(v<.01 for v in g.values()) or any(abs(v*1000-round(v*1000))>1e-7 for k,v in g.items() if k!='Wm' or v not in (1.936496,1.810636,1.711610)):raise RuntimeError('dimension grid')
    if not presubmit(g,s['nominal_a_mm'])['can_submit'] or geometry.slot_boxes(g,'folded')!=f['expected_boxes']:raise RuntimeError('geometry screen')
    if pred.get('dense_confirmation'):
        b=read(root/'decisions/S5R9_B1_FINAL.json')
        if not b['delivery_pass'] or g!=read(case_dir(root,b['selected_case'],cfg)/'input/freeze.json')['design']['geometry_mm']:raise RuntimeError('dense not exact passed B1')
    proof=read(root/'publications'/(case+'.json'))
    if not proof['remote_verified'] or proof['authorization_sha256']!=sha(root/'authorization.json') or proof['freeze_sha256']!=sha(w/'input/freeze.json'):raise RuntimeError('not published')
    files={**cfg['code_hashes'],**cfg['frozen_hashes'],(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix():sha(w/'input/freeze.json')}
    for rel,h in files.items():
        if hashlib.sha256(subprocess.check_output(['git','show',proof['commit']+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('published blob mismatch '+rel)
    return cfg,f
