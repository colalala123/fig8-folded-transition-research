"""R10 fail-closed dispatch: immutable/published inputs, finite stage gates."""
import hashlib,subprocess
from common_stage2 import *
from solve_block import solve_stage
from prepare_r10 import spec,suggestion,INITIAL
import cad_ir,numpy as np

def published_blobs(proof,files):
    if not proof['remote_verified']:raise RuntimeError('publication not verified')
    for rel,h in files.items():
        if sha(REPO/rel)!=h or hashlib.sha256(subprocess.check_output(['git','show',proof['commit']+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('published/frozen blob mismatch '+rel)

def verify_release(root,case):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stop/pause')
    cfg=read(root/'authorization.json')
    if not cfg['human_authorized'] or cfg['execution_revision']!='R11_STAGE6_R3':raise RuntimeError('R10 authorization')
    if (cfg['cores'],cfg['tasks'],cfg['serial'],cfg['no_hook'])!=(14,1,True,True):raise RuntimeError('resources')
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen file changed '+rel)
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('historical evidence changed '+p)
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed']:raise RuntimeError('offline tests not passed')
    from validation_gate import verify_all_seven
    verify_all_seven(root,cfg)
    w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id'];n=p.removeprefix('S6R10_');i=f['attempt_ordinal']
    if any((w/z).exists() for z in ('worker_started.json','done.json','failure.txt')):raise RuntimeError('duplicate dispatch')
    if f['resume'] or f['inherited_Analyze'] or f['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('input authorization mismatch')
    if cfg['case_specs'][case]!=dict(parent_id=p,attempt_ordinal=i,numerical_retry=f['numerical_retry']):raise RuntimeError('unregistered attempt')
    for prev in cfg['parent_order'][:cfg['parent_order'].index(p)]:
        if not read(root/'decisions'/(prev+'_FINAL.json'))['complete']:raise RuntimeError('prior incomplete '+prev)
    if n not in INITIAL+['P1dense','P2dense']:
        gate=read(root/'R10_2_PUBLICATION.json');published_blobs(gate,gate['hashes'])
    if n=='W4' and not read(root/'decisions/S6R10_W3_FINAL.json')['passed']:raise RuntimeError('W3 not usable; W4 must be skipped')
    pred=f['design'];s=spec(root,p,cfg)
    if f['numerical_retry']:
        original=case_dir(root,f['logical_case'],cfg);ev=read(original/'NUMERICAL_FAILURE.json')
        if not ev['same_settings_retry_allowed'] or pred!=read(original/'input/freeze.json')['design'] or f['previous_extraction_sha256']!=sha(original/'failure.txt'):raise RuntimeError('not identical numerical retry')
    elif (n in ('B1R','W4') and i>1):
        sg=suggestion(root,p,cfg)
        if not sg['needs_solve'] or sg!=pred['tuning'] or sg['geometry_mm']!=pred['geometry_mm']:raise RuntimeError('not frozen tuner')
    elif pred!=s:raise RuntimeError('frozen first/single geometry changed')
    ir=pred['cad_ir'];rebuilt=cad_ir.build(ir['base_geometry_mm'],ir['etch_e_mm'],ir['er'],ir['h_mm'],port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed')
    from geometry_gate import check_ir
    check_ir(ir)
    if ir!=cad_ir.json_value(rebuilt) or f['expected_boxes']!=ir['expected_slot_boxes']:raise RuntimeError('CAD IR not reproducible')
    if not pred['screen']['can_submit'] or not np.allclose([pred['geometry_mm'][k] for k in ir['geometry_mm']],[ir['geometry_mm'][k] for k in ir['geometry_mm']],atol=1e-9,rtol=0):raise RuntimeError('geometry/IR mismatch')
    proof=read(root/'publications'/(case+'.json'))
    if proof['authorization_sha256']!=sha(root/'authorization.json') or proof['freeze_sha256']!=sha(w/'input/freeze.json'):raise RuntimeError('publication binding')
    files={**cfg['code_hashes'],**cfg['frozen_hashes'],(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix():sha(w/'input/freeze.json')}
    from validation_gate import validation_files
    files.update(validation_files(root,case,cfg))
    published_blobs(proof,files)
    return cfg,f
