"""R16 input and eligibility; no native API."""
import argparse,copy
from common_stage2 import *
import stage8
from stage8 import PREFIX,SLOTS,ORDER
from tuning import propose_history,state
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r16_stage8_r8_20261121')
INITIAL=[]
def histories(root,p,cfg):
    out=[]
    for c,s in cfg['case_specs'].items():
        if s['parent_id']!=p:continue
        w=case_dir(root,c,cfg)
        if (w/'review/visual_ack.json').exists():
            from manage import measurement
            m=measurement(w);q=read(w/'review/extraction_R2.json')
            if state(q) is not None:out.append(dict(case=c,q=q,tuning=read(w/'input/freeze.json')['design'].get('tuning'),measurement=m))
    return out
def eligibility(root,p,cfg):
    n=p.removeprefix(PREFIX);i=ORDER.index(n);prev={}
    for k in ORDER[:i]:
        d=read(root/'decisions'/(PREFIX+k+'_FINAL.json'))
        if not d['complete']:raise RuntimeError('prior parent incomplete '+k)
        prev[k]=d
    return stage8.permission(n,prev)
def spec(root,p,cfg):
    ok,reason=eligibility(root,p,cfg)
    if not ok:raise RuntimeError('condition not met: '+reason)
    n=p.removeprefix(PREFIX)
    if p in cfg['designs']:return copy.deepcopy(cfg['designs'][p])
    base={'C1W5':'W5R','C1W6':'W6R'}[n];decision=read(root/'decisions'/(PREFIX+base+'_FINAL.json'))
    c=decision['selected_case'];w=case_dir(root,c,cfg)
    from manage import measurement
    if measurement(w)!=decision['measurement']:raise RuntimeError('selected predecessor measurement changed')
    g=read(w/'input/freeze.json')['design']['geometry_mm'];m=read(HERE/'freeze/R16_R8.json')['margin']
    return stage8.build(g,n,'CONTROL',**stage8.corners(n,m),selected_nominal_case=c,nominal_tuned=decision['passed'])
def suggestion(root,p,cfg):
    assert p in (PREFIX+'W5R',PREFIX+'W6R')
    s=spec(root,p,cfg);m=read(HERE/'freeze/R16_R8.json')['margin'];hist=histories(root,p,cfg)
    return propose_history(hist,1.8,'folded',target=s['target_y'],peak_window=[m['P_req_dB']-.2,m['P_req_dB']],allow_width_backoff=p!=PREFIX+'W6R')
def make_input(root,p,i):
    cfg=read(root/'authorization.json');n=p.removeprefix(PREFIX);c=p+f'__T{i}';w=case_dir(root,c,cfg)
    if any((root/z).exists() for z in ('STOP.json','PAUSE.json')) or w.exists():raise RuntimeError('stopped/paused/existing input')
    if (root/'decisions'/(p+'_FINAL.json')).exists():raise RuntimeError('parent already closed')
    ok,why=eligibility(root,p,cfg)
    if not ok:return dict(needs_solve=False,reason=why)
    d=spec(root,p,cfg);previous=None
    if i>1:
        prior=case_dir(root,p+f'__T{i-1}',cfg)
        if not (prior/'review/visual_ack.json').exists():raise RuntimeError('unreviewed predecessor')
        sg=suggestion(root,p,cfg)
        if not sg['needs_solve']:return sg
        d=stage8.build(sg['geometry_mm'],n,target_y=d['target_y'],prediction=dict(response_y=sg['predicted_y']))
        d.update(tuning=sg,data_role='tuned_not_independent_test');previous=sha(prior/'review/extraction_R2.json')
    if not d['screen']['can_submit']:return dict(needs_solve=False,reason='geometry gate failed, no replacement')
    for z in ('input','native','evidence'):(w/z).mkdir(parents=True)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,logical_case=c,numerical_retry=False,design=d,nominal_a_mm=d['nominal_a_mm'],expected_boxes=d['cad_ir']['expected_slot_boxes'],source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,previous_extraction_sha256=previous,solver_started=False)
    for dest in (w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')):write(dest,f)
    return dict(needs_solve=True,case=c)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('parent');ap.add_argument('ordinal',type=int);a=ap.parse_args();print(make_input(ROOT,a.parent,a.ordinal))
