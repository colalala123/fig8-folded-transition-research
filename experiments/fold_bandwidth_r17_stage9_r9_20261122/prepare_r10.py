"""R17 append-only release design, width-dependent appendices and terminal decisions; no native API."""
import argparse,copy,subprocess
import numpy as np
from common_stage2 import *
import stage8,stage9 as s
from stage9 import ROOT,PREFIX,ORD,WIDTHS,TARGET,REQ,check,archive_hist,build,T4
from tuning import seq_j,propose_history,J0,state
from fingerprint import inspect
def path(root,n,i,cfg):return case_dir(root,PREFIX+n+f'__T{i}',cfg)
def name(n,i):return PREFIX+n+f'__T{i}'
def dec(root,n):return read(root/'decisions'/(PREFIX+n+'_FINAL.json'))
def history_for(root,n,cfg):
    hist=s.seed() if n=='W5R' else []
    for i in ORD[n]:
        c=name(n,i);w=path(root,n,i,cfg)
        if (w/'review/visual_ack.json').exists():
            from manage import measurement
            q=read(w/'review/extraction_R2.json')
            hist.append(dict(case=c,q=q,tuning=read(w/'input/freeze.json')['design'].get('tuning'),measurement=measurement(w)))
    return hist
def initial(root,n):return np.array(read(HERE/'appendices'/(n+'.json'))['J_initial'],float)
def parent_run(root,n,cfg):
    d=dec(root,n)
    if not d.get('selected_case') or not d.get('measurement'):raise RuntimeError('no selected measurement '+n)
    w=case_dir(root,d['selected_case'],cfg)
    from manage import measurement
    if d['measurement']!=measurement(w):raise RuntimeError('selected measurement changed')
    return w
def hist_run(root,n,cfg):
    w=parent_run(root,n,cfg);return next(r for r in history_for(root,n,cfg) if r['case']==read(w/'input/freeze.json')['logical_case'])
def sel_candidates(root,cfg):
    o={'W4R':(s.W4,s.W4RUNS['C1W'],s.W4)}
    w5=s.H8/'results/S8R16_W5R__T1';cw5=s.H8/'results/S8R16_C1W5__T1'
    from manage import measurement
    if dec(root,'W5R')['passed'] and s.corner_pass(measurement(cw5))['passed']:o['W5R']=(parent_run(root,'W5R',cfg),cw5,w5)
    for w,c in [('W6R','C1W6'),('W7R','C1W7')]:
        if dec(root,w)['passed'] and (dec(root,c).get('corner_test') or {}).get('passed'):
            b=parent_run(root,w,cfg);o[w]=(b,parent_run(root,c,cfg),b)
    return o
def selection(root,cfg):
    candidates=sel_candidates(root,cfg);out=s.selection(candidates)
    # Runtime folder names are ordinal folders; publish logical identities instead.
    def logical(w):return read(w/'input/freeze.json')['logical_case'] if (w/'input/freeze.json').is_file() else w.name
    for k,(w,c,cr) in candidates.items():out['candidates'][k].update(nominal=logical(w),C1=logical(c),C1_reference=logical(cr))
    return out
def appendix(root,k,cfg):
    if k=='9D':return selection(root,cfg)
    if k=='W5R':return dict(J_initial=J0.tolist(),source='B1 measured J0; W5R T1-T3 chronological historical trials')
    prev={'W6R':'W5R','W7R':'W6R'}[k];hist=history_for(root,prev,cfg)
    J,log=seq_j(hist,'folded',initial(root,prev))
    prim=(read(HERE/'appendices/W6R.json')['previous_prime'] if k=='W7R' else None)
    return dict(**s.width_t1(k,J,hist_run(root,prev,cfg),archive_hist(s.W4)['q'] if k=='W6R' else None,prim),J_source=prev,source_secants=log)
def appendix_files(root,n,cfg):
    keys=(['W5R'] if n=='W5R' else ['W6R'] if n in ('W6R','C1W6') else ['W7R'] if n in ('W7R','C1W7') else ['9D'])
    files={}
    for k in keys:
        p=HERE/'appendices'/(k+'.json')
        if read(p)!=appendix(root,k,cfg):raise RuntimeError('appendix not reproducible '+k)
        files[p.relative_to(REPO).as_posix()]=sha(p)
    return files
def ensure_appendix(root,k,cfg):
    p=HERE/'appendices'/(k+'.json');d=appendix(root,k,cfg)
    if p.exists():
        if read(p)!=d:raise RuntimeError('appendix differs')
    else:write(p,d)
    return d
def eligibility(root,n,cfg):
    for k in list(ORD)[:list(ORD).index(n)]:
        if not dec(root,k)['complete']:raise RuntimeError('incomplete predecessor '+k)
    if n=='W5R':return True,'eligible'
    if not dec(root,'W5R')['passed']:return False,'W5R not tuned; end stage under 3.2'
    if n=='W6R':return True,'eligible'
    if n=='C1W6':return bool(dec(root,'W6R')['passed']),'requires tuned W6R'
    if n=='W7R':
        ok=dec(root,'W6R')['passed'] and (dec(root,'C1W6').get('corner_test') or {}).get('passed') and dec(root,'W6R')['measurement']['BW20_GHz']-dec(root,'W5R')['measurement']['BW20_GHz']>=.05-1e-12
        return bool(ok),'W7R requires W6R tune + robust C1W6 + 50 MHz'
    if n=='C1W7':return bool(dec(root,'W7R')['passed']),'requires tuned W7R'
    k=selection(root,cfg)['selected']
    return (k=='W5R' if n=='DC1' else k!='W4R'),'W4R already has all five; DC1 only for selected W5R'
def suggestion(root,n,cfg):
    return propose_history(history_for(root,n,cfg),1.8,'folded',target=TARGET,force_sequential=True,peak_window=[REQ-.2,REQ],J_initial=initial(root,n))
def design_for(root,n,i,cfg):
    if n in WIDTHS:
        if i==1:
            a=read(HERE/'appendices'/(n+'.json'));d=build(a['geometry_mm'],n,target_y=TARGET,prediction=dict(response_y=TARGET,method='target-corrected tuning-path extrapolation'))
            d['data_role']='prospective_tuned_path_extrapolation';return d
        sg=suggestion(root,n,cfg)
        if not sg['needs_solve']:raise ValueError('controller: '+sg['reason'])
        if n=='W5R' and i==4 and (not np.allclose(sg['predicted_y'],[6.7404,-.019,-22.8001],atol=1e-4,rtol=0) or any(abs(sg['geometry_mm'][k]-v)>1e-9 for k,v in T4.items())):raise RuntimeError('T4 does not reproduce R9-2')
        d=build(sg['geometry_mm'],n,target_y=TARGET,prediction=dict(response_y=sg['predicted_y'],method='chronological Broyden from measured trials'));d.update(tuning=sg);return d
    par={'C1W6':'W6R','C1W7':'W7R'}.get(n) or read(HERE/'appendices/9D.json')['selected'];w=parent_run(root,par,cfg)
    g=read(w/'input/freeze.json')['design']['geometry_mm'];opts=dict(selected_nominal_case=dec(root,par)['selected_case'],nominal_tuned=True)
    if n=='Ddense':return build(g,n,'CONTROL',**opts)
    e,er,h={'DC2':(-.01,3.60,.851),'DC3':(-.01,3.50,.851)}.get(n,(.01,3.50,.775))
    return build(g,n,'CONTROL',e,er,h,**opts)
def prior_hash(root,n,i,cfg):
    if i==4 and n=='W5R':return sha(s.H8/'results/S8R16_W5R__T3/review/extraction_R2.json')
    if i==1:return None
    return sha(path(root,n,i-1,cfg)/'review/extraction_R2.json')
def make_input(root,n,i):
    cfg=read(root/'authorization.json');p=PREFIX+n;c=name(n,i);w=case_dir(root,c,cfg)
    if any((root/z).exists() for z in ('STOP.json','PAUSE.json')) or w.exists() or (root/'decisions'/(p+'_FINAL.json')).exists():raise RuntimeError('paused/closed/existing input')
    ok,why=eligibility(root,n,cfg)
    if not ok:return dict(needs_solve=False,reason=why)
    if i!=ORD[n][0] and not (path(root,n,i-1,cfg)/'review/visual_ack.json').exists():raise RuntimeError('unreviewed predecessor')
    appendix_files(root,n,cfg)
    if n in WIDTHS and i!=1:
        sg=suggestion(root,n,cfg)
        if not sg['needs_solve']:return dict(needs_solve=False,reason=sg['reason'])
    d=design_for(root,n,i,cfg)
    if not d['screen']['can_submit']:return dict(needs_solve=False,reason='geometry_gate_no_replacement')
    fp=inspect(root,cfg,d)
    if not fp['allowed']:return dict(needs_solve=False,reason='controller_stalled',fingerprint=fp)
    for z in ('input','native','evidence'):(w/z).mkdir(parents=True,exist_ok=False)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,logical_case=c,numerical_retry=False,design=d,nominal_a_mm=d['nominal_a_mm'],expected_boxes=d['cad_ir']['expected_slot_boxes'],source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,previous_extraction_sha256=prior_hash(root,n,i,cfg),fingerprint=fp,solver_started=False)
    for dest in [w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')]:write(dest,f)
    return dict(needs_solve=True,case=c,fingerprint=fp['signature'])
def decision(root,case,mode):
    cfg=read(root/'authorization.json');sp=cfg['case_specs'][case];p=sp['parent_id'];n=p.removeprefix(PREFIX);i=sp['attempt_ordinal'];w=case_dir(root,case,cfg)
    if any((root/z).exists() for z in ('STOP.json','PAUSE.json')):raise RuntimeError('paused/stopped')
    d=dict(at=now(),parent_id=p,complete=True,selected_case=None,measurement=None,passed=False,ordinal=i)
    ok,why=eligibility(root,n,cfg)
    if mode=='skip':
        if w.exists():raise RuntimeError('started, cannot skip')
        if ok:
            output=make_input(root,n,i)
            if output['needs_solve']:raise RuntimeError('eligible novel point cannot skip')
            d.update(pre_submit=output);why=output['reason']
        d.update(skipped=True,reason=why)
    elif mode=='missing':
        if not (w/'NUMERICAL_MISSING.json').is_file() or read(w/'RUN_RECORD.json')['numerical_pass'] is not False:raise RuntimeError('not numerical missing')
        d.update(missing=True,reason='numerical missing; no re-solve')
    else:
        from manage import measurement
        m=measurement(w);d.update(selected_case=case,measurement=m,passed=None,reason='measured')
        if n in WIDTHS:
            c=check(read(w/'review/extraction_R2.json'),REQ,m.get('S21_min_dB'))
            if c['tuned']:d.update(passed=True,reason='nominal tuned')
            elif i!=ORD[n][-1]:return dict(complete=False,next_ordinal=i+1)
            else:d.update(passed=False,reason='finite budget exhausted, not proven infeasible')
        elif n!='Ddense':d.update(corner_test=s.corner_pass(m))
    for f in [root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')]:write(f,d)
    return d
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['input','appendix','eligible']);ap.add_argument('key');ap.add_argument('ordinal',type=int,nargs='?');a=ap.parse_args()
    cfg=read(ROOT/'authorization.json')
    print({'input':lambda:make_input(ROOT,a.key,a.ordinal),'appendix':lambda:ensure_appendix(ROOT,a.key,cfg),'eligible':lambda:eligibility(ROOT,a.key,cfg)}[a.action]())
