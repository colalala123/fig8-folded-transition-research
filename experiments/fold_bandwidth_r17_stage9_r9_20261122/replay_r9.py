"""Mandatory data-driven replay; no AEDT, no worker/charge and never changes a historical file."""
import copy,importlib.util,tempfile
import numpy as np
import stage9 as s
from fingerprint import lookup,identity,old_index
from tuning import seq_j,propose_history,delivery_error
def run():
    hs=s.seed();ds=[s.read(s.H8/'results'/r['case']/'INPUT.json')['design'] for r in hs]
    sp=importlib.util.spec_from_file_location('original_r8_tuning',s.H8/'tuning.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
    kw=dict(a=1.8,top='folded',target=s.TARGET,peak_window=[s.REQ-.2,s.REQ])
    bug=old.propose_history(hs[:2],force_sequential=False,**kw)
    r2=propose_history(hs[:2],J_initial=s.J0,**kw);r3=propose_history(hs,J_initial=s.J0,**kw)
    eq=lambda a,b: set(a)==set(b) and all(abs(a[k]-b[k])<1e-10 for k in b)
    yref=np.array([6.7404,-.0190,-22.8001]);rr={}
    rr['R9-1']=dict(passed=eq(bug['geometry_mm'],ds[1]['geometry_mm']),proposed=bug['geometry_mm'],T2=ds[1]['geometry_mm'],rule='unaltered R8')
    rr['R9-2']=dict(passed=eq(r2['geometry_mm'],s.T4) and r2['base_case']==hs[0]['case'] and bool(np.max(abs(np.array(r2['predicted_y'])-yref))<=.0001),base=r2['base_case'],geometry=r2['geometry_mm'],y=r2['predicted_y'],residual_to_printed_target=(np.array(r2['predicted_y'])-yref).tolist(),J=r2['J'])
    rr['R9-3']=dict(passed=eq(r3['geometry_mm'],r2['geometry_mm']) and r3['base_case']==r2['base_case'] and r3['predicted_y']==r2['predicted_y'] and r3['J']==r2['J'] and not r3['broyden_updates'][-1]['triggered'],updates=r3['broyden_updates'],y=r3['predicted_y'])
    rows=old_index();duplicate=copy.deepcopy(ds[1]);duplicate.update(id='renamed',design='fake-alias',tuning={'timestamp':'irrelevant'})
    from prepare_r10 import make_input
    from common_stage2 import Path,write
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as tmp:
        rt=Path(tmp);(rt/'ledger').mkdir();c='S9R17_W5R__T4'
        write(rt/'authorization.json',dict(case_specs={c:dict(parent_id='S9R17_W5R',attempt_ordinal=4,numerical_retry=False)},case_paths={c:'runs/test'}))
        from fingerprint import inspect
        with patch('prepare_r10.appendix_files',return_value={}),patch('prepare_r10.suggestion',return_value={'needs_solve':True}),patch('prepare_r10.design_for',return_value=duplicate),patch('fingerprint.read',return_value={'rows':rows}):
            block=make_input(rt,'W5R',4)
        intact=not list((rt/'ledger').iterdir()) and not (rt/'runs').exists()
    rr['R9-4']=dict(passed=not block['needs_solve'] and block['reason']=='controller_stalled' and all(r['case'] in block['fingerprint']['duplicates'] for r in hs[1:]) and intact,refusal=block,no_run_or_ledger=bool(intact),historical_completed=len(rows))
    init=s.J0.copy();init[0,0]+=.125
    z=propose_history(hs[:1],J_initial=init,**kw)
    J2,_=seq_j(hs[:2],'folded',init)
    dx=s.coordinate(hs[1]['q']['geometry_mm'],'folded')-s.coordinate(hs[0]['q']['geometry_mm'],'folded')
    dy=s.state(hs[1]['q'])-s.state(hs[0]['q']);ref=init+np.outer(dx,dy-dx@init)/(dx@dx)
    rr['R9-5']=dict(passed=np.array_equal(z['J'],init) and not np.array_equal(init,s.J0) and np.allclose(J2,ref,atol=1e-12,rtol=0),J_in=init.tolist(),J_used=z['J'],rank_one_all_outputs=bool(np.allclose(dx@J2,dy)))
    return dict(passed=all(bool(r['passed']) for r in rr.values()),replays=rr,base_errors=[delivery_error(r['q'],s.TARGET) for r in hs],T3='same input as T2, charged historically; zero displacement skipped')
if __name__=='__main__':
    import json
    r=run();print(json.dumps(r,indent=2));raise SystemExit(not r['passed'])
