"""R10 fail-closed dispatch: immutable/published inputs, finite stage gates."""
import hashlib,subprocess
from common_stage2 import *
from solve_block import solve_stage
from prepare_r10 import design_for, prior_hash, appendix_files
from fingerprint import inspect
import cad_ir,numpy as np

def published_blobs(proof,files):
    if not proof['remote_verified']:raise RuntimeError('publication not verified')
    from publication_check import verify_blobs
    verify_blobs(proof['commit'],files)

def verify_release(root,case):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stop/pause')
    cfg=read(root/'authorization.json')
    if not cfg['human_authorized'] or cfg['execution_revision']!='R17_STAGE9_R9':raise RuntimeError('R10 authorization')
    if (cfg['cores'],cfg['tasks'],cfg['serial'],cfg['no_hook'])!=(14,1,True,True):raise RuntimeError('resources')
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen file changed '+rel)
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('historical evidence changed '+p)
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed']:raise RuntimeError('offline tests not passed')
    # R11 seven-point evidence is inherited, hash-bound and not replayed.
    from validation_gate import verify_one
    if case!=cfg['cache_case']:verify_one(root,case,cfg)
    w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id'];n=p.removeprefix('S9R17_');i=f['attempt_ordinal']
    if any((w/z).exists() for z in ('worker_started.json','done.json','failure.txt')):raise RuntimeError('duplicate dispatch')
    if f['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('input authorization mismatch')
    if f['resume'] or f['inherited_Analyze']:raise RuntimeError('R15 new geometry only; no cache resume')
    if cfg['case_specs'][case]!=dict(parent_id=p,attempt_ordinal=i,numerical_retry=f['numerical_retry']):raise RuntimeError('unregistered attempt')
    for prev in cfg['parent_order'][:cfg['parent_order'].index(p)]:
        if not read(root/'decisions'/(prev+'_FINAL.json'))['complete']:raise RuntimeError('prior incomplete '+prev)
    # All R15 freeze and validation files are publication-bound below. Independent steps only require prior terminal decision.
    if (root/'decisions'/(p+'_FINAL.json')).exists():raise RuntimeError('parent closed')
    pred=f['design']
    from prepare_r10 import eligibility
    ok,reason=eligibility(root,n,cfg)
    if not ok:raise RuntimeError(reason)
    expected=design_for(root,n,i,cfg)
    if pred!=expected or f['numerical_retry']:raise RuntimeError('not frozen R9 geometry or tuning')
    if f['previous_extraction_sha256']!=prior_hash(root,n,i,cfg):raise RuntimeError('history binding')
    uq=inspect(root,cfg,pred)
    if not uq['allowed'] or f['fingerprint']!=uq:raise RuntimeError('duplicate or physical fingerprint mismatch')
    ir=pred['cad_ir'];rebuilt=cad_ir.build(ir['base_geometry_mm'],ir['etch_e_mm'],ir['er'],ir['h_mm'],port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed')
    from geometry_gate import check_ir
    check_ir(ir)
    if ir!=cad_ir.json_value(rebuilt) or f['expected_boxes']!=ir['expected_slot_boxes']:raise RuntimeError('CAD IR not reproducible')
    if not pred['screen']['can_submit'] or not np.allclose([pred['geometry_mm'][k] for k in ir['geometry_mm']],[ir['geometry_mm'][k] for k in ir['geometry_mm']],atol=1e-9,rtol=0):raise RuntimeError('geometry/IR mismatch')
    proof=read(root/'publications'/(case+'.json'))
    if proof['authorization_sha256']!=sha(root/'authorization.json') or proof['freeze_sha256']!=sha(w/'input/freeze.json'):raise RuntimeError('publication binding')
    files={**cfg['code_hashes'],**cfg['frozen_hashes'],(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix():sha(w/'input/freeze.json')}
    from validation_gate import validation_files
    files.update(validation_files(root,case,cfg));files.update(appendix_files(root,n,cfg))
    published_blobs(proof,files)
    return cfg,f
