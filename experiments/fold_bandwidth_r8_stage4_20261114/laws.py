"""R8-1: independent retrospective fits and leave-whole-ladder-out CV.

Pure offline. No stage4 result is an input; coefficient selection is fixed here.
"""
import json,sys,hashlib
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent; REPO=H.parents[1]
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
import chain
from presubmit import presubmit
KEYS=['Wm','Ws','Lm','Ls1','Ls2','Ls3']
TARGET=np.array([6.72,0.,-20.3])
J=np.array(json.loads((H/'offline/SENSITIVITY.json').read_text())['J0'])
SOURCES=['experiments/fold_bandwidth_review_r7_20261113/out/ALL_GEOMETRIES.json',
 'experiments/fold_bandwidth_review_r8_20261113/out/R7_3R_RECOMPUTED.json']
DESIGNS=[('D1','N04',1.936496,1.,2.),('D2','N04',1.936496,2.4,.25),
 ('D3','N14',1.810636,1.,2.),('D4','N14',1.810636,2.4,.25),
 ('D5','N08',1.711610,1.,.55),('D6','Wm1.874',1.874,1.8,.55),
 ('D7','N04',1.936496,2.4,.55),('D8','Wm2.060',2.060,1.8,.55)]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def features(w,a,g):
    u=w-1.81
    return np.array([1.,u,u*u,a,a*a,max(a-2.1,0),g-.55])
FEATURES=['1','Wm-1.81','(Wm-1.81)^2','a','a^2','max(a-2.1,0)','g-.55']
def collect():
    rows=[];excluded=[];seen=set()
    for rel in SOURCES:
        for r in read(REPO/rel):
            if r['case'] in seen:continue
            if 'kind' in r and (r['kind']!='EQ' or r['material']!='archived_lossy'):continue
            seen.add(r['case'])
            g={k:r[k] for k in KEYS};top='folded' if g['Ls3'] else 'straight_control';d=chain.dimensions(g,top)
            if top!='folded':
                excluded.append(dict(case=r['case'],reason='straight_not_in_folded_law_fit'));continue
            y=np.array([r.get('valley_GHz',0),r.get('D_dB',0),r.get('peak_mean_dB',0)])
            good=r.get('three_valley') and r.get('BW15') and abs(y[0]-6.72)<=.25 and abs(y[1])<=6 and abs(y[2]+20.3)<=4
            if not good:
                excluded.append(dict(case=r['case'],reason='outside_local_three_valley_response_domain'));continue
            a=round(d['a_mm'],6);gap=round(d['g_mm'],6)
            group=r['family']+('_Ws_ladder' if r['case'].startswith('S1_WS') else '_g_ladder' if abs(gap-.55)>1e-5 or '_E2_' in r['case'] else '_a_ladder')
            x=np.array([g['Lm'],d['L_centerline_mm'],g['Ws']]);dx=np.linalg.solve(J.T,TARGET-y)
            balanced=abs(y[0]-6.72)<=.035 and abs(y[1])<=.6 and abs(y[2]+20.3)<=1.
            rows.append(dict(case=r['case'],source=rel,family=r['family'],group=group,geometry_mm=g,
                 Wm=g['Wm'],a=a,g=gap,Lc=d['L_centerline_mm'],y=y.tolist(),target_x=(x+dx).tolist(),
                 local_target_correction=dx.tolist(),balanced_for_bandwidth=bool(balanced),
                 BW15=r['BW15'],BW15_star=r['BW15']-.125*(y[2]+20.3),
                 tip_clearance=(g['Ls1']-2*g['Ls3']-max(g['Wm'],1.82))/2))
    return rows,excluded
def plateaus(rows):
    out=[]
    for fam in sorted(set(r['family'] for r in rows)):
        rr=[r for r in rows if r['family']==fam and r['balanced_for_bandwidth'] and abs(r['g']-.55)<1e-5 and .6<=r['a']<=2.2]
        if rr:out.append(dict(family=fam,Wm=float(np.median([r['Wm'] for r in rr])),F=float(np.median([r['BW15_star'] for r in rr])),cases=[r['case'] for r in rr]))
    return out
def fit_platform(rows,degree):
    p=plateaus(rows);X=np.array([[r['Wm']**i for i in range(degree+1)] for r in p]);y=np.array([r['F'] for r in p])
    rank=int(np.linalg.matrix_rank(X)) if len(p) else 0
    return dict(degree=degree,identified=rank==degree+1,rank=rank,plateaus=p,
        coefficients=np.linalg.lstsq(X,y,rcond=None)[0].tolist() if rank==degree+1 else None)
def platform(m,w):return float(sum(c*w**i for i,c in enumerate(m['coefficients'])))
def fit_cost(rows,mode):
    pp={r['family']:r['F'] for r in plateaus(rows)}
    rr=[r for r in rows if r['balanced_for_bandwidth'] and r['family'] in pp]
    X=np.array([r['tip_clearance'] if mode=='tip' else -r['a']-r['g'] if mode=='sum' else -r['a'] for r in rr]);y=np.array([pp[r['family']]-r['BW15_star'] for r in rr])
    grid=np.arange(1.5,4.001,.05) if mode=='tip' else -np.arange(1.5,3.501,.05) if mode=='sum' else -np.arange(.6,2.801,.05)
    best=None
    for t in grid:
        h=np.maximum(t-X,0);small=np.array([max(1.-r['a'],0) for r in rr])
        A=np.array([h,small]).T;coef=np.linalg.lstsq(A,y,rcond=None)[0]
        # Both branches represent nonnegative costs, constrained by enumeration.
        options=[np.maximum(coef,0),np.array([max(float(h@y/(h@h)),0) if h@h else 0,0]),np.array([0,max(float(small@y/(small@small)),0) if small@small else 0])]
        for c in options:
            mse=float(np.mean((y-A@c)**2))
            if best is None or mse<best['mse_GHz2']:best=dict(mode=mode,threshold=float(t),slope_GHz_per_mm=float(c[0]),small_a_slope=float(c[1]),mse_GHz2=mse,n=len(rr))
    return best
def cost(m,w,a,g,c):
    x=c if m['mode']=='tip' else -a-g if m['mode']=='sum' else -a
    return m['slope_GHz_per_mm']*max(m['threshold']-x,0)+m['small_a_slope']*max(1.-a,0)
def fit_params(rows):
    # Equal total weight per entire ladder: repeated Ws perturbations do not dominate.
    from collections import Counter
    ns=Counter(r['group'] for r in rows);wt=np.array([1/np.sqrt(ns[r['group']]) for r in rows])
    X=np.array([features(r['Wm'],r['a'],r['g']) for r in rows]);Y=np.array([r['target_x'] for r in rows])
    coef=np.linalg.lstsq(X*wt[:,None],Y*wt[:,None],rcond=None)[0]
    return dict(features=FEATURES,outputs=['Lm','Lc','Ws'],coefficients=coef.tolist(),rank=int(np.linalg.matrix_rank(X)),
        training_RMSE_mm=np.sqrt(np.mean((X@coef-Y)**2,axis=0)).tolist(),group_weight='equal ladder total weight')
def fit(rows):return dict(platform={str(d):fit_platform(rows,d) for d in (1,2)},cost={m:fit_cost(rows,m) for m in ('tip','sum','a')},parameters=fit_params(rows))
def cv(rows):
    folds=[]
    for group in sorted(set(r['group'] for r in rows)):
        tr=[r for r in rows if r['group']!=group];te=[r for r in rows if r['group']==group];m=fit(tr)
        yp=[];paramres=[];bw={};pr={}
        for r in te:
            xp=features(r['Wm'],r['a'],r['g'])@np.array(m['parameters']['coefficients']);dx=np.array(r['target_x'])-xp
            paramres.append(dx.tolist());yp.append((dx@J).tolist())
        for deg,pm in m['platform'].items():
            if not pm['identified']:
                bw[deg]=dict(identified=False,reason='fewer independent Wm families than polynomial coefficients');continue
            for mode,cm in m['cost'].items():
                e=[platform(pm,r['Wm'])-cost(cm,r['Wm'],r['a'],r['g'],r['tip_clearance'])-r['BW15_star'] for r in te if r['balanced_for_bandwidth']]
                bw[deg+':'+mode]=dict(n=len(e),RMSE_MHz=float(np.sqrt(np.mean(np.square(e)))*1000) if e else None,errors_MHz=[x*1000 for x in e])
            ref={p['family']:p for p in plateaus(tr)}
            e=[platform(pm,p['Wm'])-p['F'] for p in plateaus(te)]
            pr[deg]=dict(n=len(e),RMSE_MHz=float(np.sqrt(np.mean(np.square(e)))*1000) if e else None)
        folds.append(dict(held_out_whole_ladder=group,training_n=len(tr),test_n=len(te),parameter_fit_rank=m['parameters']['rank'],
             parameter_errors_mm=paramres,parameter_RMSE_mm=np.sqrt(np.mean(np.square(paramres),axis=0)).tolist(),
             response_RMSE_GHz_dB_dB=np.sqrt(np.mean(np.square(yp),axis=0)).tolist(),bandwidth=bw,platform=pr))
    return dict(method='leave one entire family a / g / Ws ladder out; all attempts of that ladder together; no random rows',folds=folds,
        caveats=['Only three Wm families; quadratic CV may be unidentifiable after withholding N08. Such folds are reported, never imputed.',
                 'Target parameter labels are J-corrected retrospective simulations, not new solved designs; response CV is J-linearized, not a blind HFSS score.',
                 'g=2.0 is outside training g<=1.2; D8 Wm=2.060 is extrapolation.'])
def candidates(m):
    out=[]
    for name,fam,w,a,gap in DESIGNS:
        x=features(w,a,gap)@np.array(m['parameters']['coefficients']);lm,lc,ws=map(float,x)
        ws=round(ws,3);lm=round(lm,3);ls1=round(lc-2*a-2*gap-2*ws,3)
        geom=dict(Wm=w,Ws=ws,Lm=lm,Ls1=ls1,Ls2=round(2*ws+gap,3),Ls3=round(a+ws,3))
        sc=presubmit(geom,a,tuning_changed=False)
        c=(ls1-2*geom['Ls3']-max(w,1.82))/2
        actualx=np.array([lm,chain.dimensions(geom)['L_centerline_mm'],ws]); y=TARGET+(actualx-x)@J
        bws={f'F{d}_{mode}':platform(pm,w)-cost(cm,w,a,gap,c) for d,pm in m['platform'].items() for mode,cm in m['cost'].items()}
        out.append(dict(id='S4R8_'+name,design=name,family=fam,nominal_a_mm=a,g_mm=gap,geometry_mm=geom,unrounded_target_x=x.tolist(),
            prediction=dict(central_valley_GHz=float(y[0]),D_dB=float(y[1]),L_dB=float(y[2]),BW15_star_GHz=bws,
              BW15_GHz={k:v+.125*(float(y[2])+20.3) for k,v in bws.items()},primary_bandwidth_model='F2_tip',
              response_prediction_method='frozen target-parameter fit plus J-linear rounding correction; model discrepancy assessed by whole-ladder CV'),
            screen=sc,tip_clearance_mm=c,data_role='prospective_test_T1',extrapolation=(gap>1.2 or w>1.936496)))
    return out
def main():
    rows,ex=collect();m=fit(rows);cand=candidates(m)
    write(H/'offline/TRAINING.json',dict(rows=rows,exclusions=ex,source_sha256={s:digest(REPO/s) for s in SOURCES}))
    write(H/'offline/LAWS.json',m);write(H/'offline/CROSS_VALIDATION.json',cv(rows));write(H/'offline/T1_GEOMETRIES.json',cand)
    plan=(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R8.md').read_text(encoding='utf-8')
    write(H/'offline/REVIEWER_PREDICTIONS.json',dict(verbatim=plan.split('## 4. 审核方登记的预测')[1].split('## 5.')[0],plan_sha256=digest(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R8.md')))
    print('ROWS',len(rows),'BALANCED',sum(r['balanced_for_bandwidth'] for r in rows));print(json.dumps(m,ensure_ascii=False,indent=2))
    for c in cand:print(c['design'],c['geometry_mm'],c['screen']['can_submit'],c['prediction']['BW15_star_GHz'])
if __name__=='__main__':main()
