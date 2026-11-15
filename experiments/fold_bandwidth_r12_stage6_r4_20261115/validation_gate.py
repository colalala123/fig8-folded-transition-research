"""Fail closed unless every required zero-Analyze preflight was published."""
from common_stage2 import *

def verify_one(root,case,cfg):
    d=HERE/'validation'/case;p=read(d/'PASS.json');w=case_dir(root,case,cfg)
    if not p['passed'] or p['new_Analyze']!=0 or not p['cleanup']['released'] or not p['cleanup']['scratch_restored']:raise RuntimeError('preflight not safely closed '+case)
    if p['input_sha256']!=sha(w/'input/freeze.json') or p['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('preflight input/auth changed '+case)
    for rel,h in p['code_hashes'].items():
        if sha(REPO/rel)!=h or cfg['code_hashes'].get(rel)!=h:raise RuntimeError('preflight code changed '+rel)
    for rel,h in read(d/'MANIFEST.json').items():
        if sha(d/rel)!=h:raise RuntimeError('validation evidence changed '+rel)
    if not read(d/'design_validation/VERDICT.json')['passed']:raise RuntimeError('native validation failed')
    return {x.relative_to(REPO).as_posix():sha(x) for x in d.rglob('*') if x.is_file()}

def verify_all_seven(root,cfg):
    if len(cfg['required_preflight_cases'])!=7:raise RuntimeError('not all seven registered')
    for c in cfg['required_preflight_cases']:verify_one(root,c,cfg)
    gate=read(HERE/'validation/ALL_SEVEN.json')
    if not gate['passed'] or gate['new_Analyze']!=0 or gate['cases']!=cfg['required_preflight_cases']:raise RuntimeError('seven-point gate not complete')
    for c,h in gate['pass_hashes'].items():
        if sha(HERE/'validation'/c/'PASS.json')!=h:raise RuntimeError('aggregate gate changed')

def validation_files(root,case,cfg):
    # R12 requires pointwise native validation, including adaptive tuning attempts.
    return verify_one(root,case,cfg)
