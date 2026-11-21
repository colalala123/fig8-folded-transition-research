"""Immutable terminal selection and gating. Imported only after manage.measurement exists."""
from prepare_r10 import *
def persist(root,d):
    for dest in [root/'decisions'/(d['parent_id']+'_FINAL.json'),HERE/'decisions'/(d['parent_id']+'_FINAL.json')]:write(dest,d)
    return d
def choose(h,req):
    if not h:return None
    return min(h,key=lambda r:stage8.check(r['q'],req,r['measurement'].get('S21_min_dB'))['error_e'])
def decision(root,case,mode):
    from manage import measurement
    cfg=read(root/'authorization.json')
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stop/pause')
    p=cfg['case_specs'][case]['parent_id'];n=p.removeprefix(PREFIX);i=cfg['case_specs'][case]['attempt_ordinal'];w=case_dir(root,case,cfg)
    base=dict(at=now(),parent_id=p,complete=True,selected_case=None,passed=False,measurement=None,numerical_valid=False,attempt_ordinal=i)
    ok,why=eligibility(root,p,cfg)
    if mode=='skip':
        if w.exists():raise RuntimeError('never skip existing work')
        if ok and not (i==1 and not spec(root,p,cfg)['screen']['can_submit']):raise RuntimeError('not an eligible skip')
        return persist(root,{**base,'skipped':True,'reason':why if not ok else 'geometry conflict; no replacement'})
    if not ok:raise RuntimeError('ineligible parent')
    nominal=n in ('W5R','W6R');req=read(HERE/'freeze/R16_R8.json')['margin']['P_req_dB']
    if mode=='missing':
        if not (w/'NUMERICAL_MISSING.json').exists() or read(w/'RUN_RECORD.json')['numerical_pass'] is not False:raise RuntimeError('not numerical missing')
        best=choose(histories(root,p,cfg),req) if nominal else None
        return persist(root,{**base,'missing':True,'selected_case':best['case'] if best else None,'measurement':best['measurement'] if best else None,'reason':'numerical missing; no retry; no fabricated measurement'})
    m=measurement(w)
    if not nominal:return persist(root,{**base,'selected_case':case,'passed':None,'measurement':m,'numerical_valid':True,'corner_test':stage8.corner_test(m,n in ('C2W','C3W'))})
    h=histories(root,p,cfg);best=choose(h,req);r=read(w/'review/REVIEW_STAGE3.json');passed=r['tuning_status']['tuned'];reason='tuned' if passed else 'finite budget exhausted'
    if not passed and i<SLOTS[n]:
        sg=suggestion(root,p,cfg)
        if sg['needs_solve']:return dict(complete=False,next_ordinal=i+1)
        reason=sg['reason']
    sel=case if passed else best['case'] if best else None
    return persist(root,{**base,'selected_case':sel,'passed':bool(passed),'measurement':m if passed else best['measurement'] if best else None,'numerical_valid':True,'reason':reason})
