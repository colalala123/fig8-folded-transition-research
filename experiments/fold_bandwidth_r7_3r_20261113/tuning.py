"""R7纯离线调参；直接内峰反馈，不用电路反解。"""
import json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
import chain,geometry
from presubmit import presubmit
TARGET=np.array([6.72,0.,-20.3]);CAP=np.array([.06,.40,.13])
J0=np.array(json.loads((HERE/'offline/SENSITIVITY.json').read_text())['J0'])

def state(q):
    sh=q['shape'];p=sh.get('inner_peaks',[])
    if not sh.get('shape_valid') or len(p)!=2:return None
    low,high=sorted(p,key=lambda r:r['GHz'])
    return np.array([sh['central_valley_GHz'],high['S11_dB']-low['S11_dB'],(high['S11_dB']+low['S11_dB'])/2])

def error(y):return float(np.max(abs(np.asarray(y)-TARGET)/[.03,.5,.6])) if y is not None else float('inf')
def classify(q):
    y=state(q);ok=y is not None and error(y)<=1+1e-10
    return dict(tuned=bool(ok),usable_for_law=bool(ok),error_e=error(y) if y is not None else None,
       mean_inner_peak_dB=float(y[2]) if y is not None else None,
       signed_D_dB=float(y[1]) if y is not None else None,
       hard_design_peaks_pass=bool(y is not None and max(p['S11_dB'] for p in q['shape']['inner_peaks'])<=-20))

def coordinate(g,top):return np.array([g['Lm'],chain.dimensions(g,top)['L_centerline_mm'],g['Ws']])
def inverse(g,x,top,a,gap):
    c={**g,'Lm':round(float(x[0]),3),'Ws':round(float(x[2]),3)}
    c.update(Ls2=0. if top=='straight_control' else 2*c['Ws']+gap,Ls3=0. if top=='straight_control' else a+c['Ws'])
    offset=chain.dimensions({**c,'Ls1':.01},top)['L_centerline_mm']-.01
    c['Ls1']=round(float(x[1])-offset,3)
    if abs(chain.dimensions(c,top)['L_centerline_mm']-x[1])>.000500001:raise AssertionError('中心线反解恒等式失败')
    return c

def broyden(J,dx,dy):
    dx=np.array(dx,float);dy=np.array(dy,float);pred=dx@J
    triggers=[j for j in (1,2) if abs(pred[j])>.3 and abs(dy[j]-pred[j])>.5*abs(pred[j])]
    if triggers and dx@dx>0:
        return J+np.outer(dx,dy-pred)/(dx@dx),dict(triggered=True,components=triggers,predicted=pred.tolist(),actual=dy.tolist())
    return J,dict(triggered=False,components=[],predicted=pred.tolist(),actual=dy.tolist())

def propose_history(history,a,top):
    valid=[r for r in history if state(r['q']) is not None]
    if not valid:return dict(needs_solve=False,reason='no_three_valley_seed')
    best=min(valid,key=lambda r:error(state(r['q'])))
    if classify(best['q'])['tuned']:return dict(needs_solve=False,reason='already_R7_usable',selected=best['case'])
    J=J0.copy();updates=[]
    # Each completed trial is bound to the exact base/J used to predict it.
    for r in history:
        t=r.get('tuning')
        if t:
            base=next(z for z in history if z['case']==t['base_case'])
            dx=coordinate(r['q']['geometry_mm'],top)-coordinate(base['q']['geometry_mm'],top)
            J,log=broyden(np.array(t['J']),dx,state(r['q'])-state(base['q']))
            updates.append(dict(case=r['case'],**log))
    q=best['q'];g=q['geometry_mm'];dim=chain.dimensions(g,top)
    dx=np.linalg.solve(J.T,TARGET-state(q));scale=min(1.,float(np.min(CAP/np.maximum(abs(dx),1e-30))))
    dx=dx*scale;x=coordinate(g,top);rejected=[]
    # R7 forbids presubmit's optional arm shortening. Only shrink delta-Ws.
    dw=float(dx[2])
    for _ in range(28):
        trial=dx.copy();trial[2]=dw
        c=inverse(g,x+trial,top,a,.55)
        sc=presubmit(c,a,tuning_changed=False,topology=top)
        if sc['can_submit']:
            if abs(chain.dimensions(c,top)['a_mm']-a)>1e-8:raise AssertionError('a改变')
            actual=coordinate(c,top)-x
            if np.any(abs(actual)>CAP+.000500001):raise AssertionError('取整步长超限')
            return dict(needs_solve=True,geometry_mm=c,base_case=best['case'],base_y=state(q).tolist(),
                 J=J.tolist(),broyden_updates=updates,raw_step=(dx/scale).tolist(),step_scale=scale,
                 actual_step=actual.tolist(),predicted_change=(actual@J).tolist(),predicted_y=(state(q)+actual@J).tolist(),
                 screen=sc,width_backoffs=rejected,nominal_a_mm=a,actual_a_mm=a,
                 reason='R7_direct_peak_feedback',data_role='prospective_tuning_attempt_not_blind_test')
        rejected.append(dict(delta_Ws=dw,screen=sc))
        if abs(dw)<1e-12:break
        dw=float(np.sign(dw)*max(0,abs(dw)-.005))
    return dict(needs_solve=False,reason='clearance_limited_no_arm_change',width_backoffs=rejected)

def propose(q,nominal_a,topology='folded'):
    return propose_history([dict(case='current',q=q)],nominal_a,topology)

def new_prediction(g,top):
    return dict(level='R7_direct_peak_feedback_not_circuit_inverse',geometry_mm=g,topology=top)
