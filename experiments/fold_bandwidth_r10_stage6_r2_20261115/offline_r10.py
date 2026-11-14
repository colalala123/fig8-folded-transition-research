"""R10-1 pure offline proposals. No solver import, IPC, process launch or auth.

The draft output is deliberately NOT a release/freeze. Explicit CAD policies are
required to promote the proposals after the two modeling questions are settled.
"""
import copy, hashlib, importlib.util, json, sys
from collections import Counter
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent; REPO=H.parents[1]
OLD=REPO/'experiments/fold_bandwidth_r9_stage5_20261114'
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
import chain
from presubmit import presubmit
import tuning, cad_ir
TARGET=np.array([6.72,0.,-20.3])

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def source_module():
    sp=importlib.util.spec_from_file_location('r9_frozen_laws_readonly',OLD/'laws.py')
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def features(w,a,g,expanded=True):
    u=w-1.81;v=g-.55
    b=[1.,u,u*u,a,a*a,max(a-2.1,0),v]
    return np.array(b+([v*v,u*v,(a-1.8)*v] if expanded else []))
NAMES=['1','Wm-1.81','(Wm-1.81)^2','a','a^2','max(a-2.1,0)','g-.55','(g-.55)^2','(Wm-1.81)*(g-.55)','(a-1.8)*(g-.55)']

def histories(parent):
    out=[]
    if parent in ('S5R9_D1c','S5R9_D3c'):
        oldid='S4R8_D1' if parent.endswith('D1c') else 'S4R8_D3'
        for p in sorted((REPO/'experiments/fold_bandwidth_r8_stage4_20261114/results').glob(oldid+'__T*')):
            out.append(dict(case=p.name,q=read(p/'review/extraction_R2.json'),tuning=None))
    for p in sorted((OLD/'results').glob(parent+'__T*')):
        q=read(p/'review/extraction_R2.json');f=read(p/'INPUT.json')
        out.append(dict(case=p.name,q=q,tuning=f['design'].get('tuning')))
    return out

def latest_J(hist):
    J=tuning.J0.copy();updates=[]
    for r in hist:
        t=r.get('tuning')
        if not t or tuning.state(r['q']) is None:continue
        base=next(x for x in hist if x['case']==t['base_case'])
        dx=tuning.coordinate(r['q']['geometry_mm'],'folded')-tuning.coordinate(base['q']['geometry_mm'],'folded')
        J,log=tuning.broyden(np.array(t['J']),dx,tuning.state(r['q'])-tuning.state(base['q']))
        updates.append(dict(case=r['case'],**log))
    return J,updates

def regroup(r):
    # Numeric Wm rather than free-form family spelling: Wm2.350 == Wm2.35.
    old=r['group'];kind='Ws' if '_Ws_' in old else 'g' if '_g_' in old else 'a'
    r['legacy_group']=old;r['group']=f"wm{r['Wm']:.6f}_{kind}_ladder"
    return r

def training():
    rows=copy.deepcopy(read(OLD/'offline/TRAINING.json')['rows']);added=[]
    selected=read(OLD/'final/SELECTED.json')
    for s in selected:
        if s['parent'].endswith('dense'):continue
        # W3 T3 is near balanced but center off by 40 MHz: usable for the local
        # parameter-target refit only, not a usable bandwidth/platform datum.
        if not s.get('usable') and s['parent']!='S5R9_W3':continue
        q=read(OLD/'results'/s['case']/'review/extraction_R2.json');y=tuning.state(q)
        if y is None:continue
        g=q['geometry_mm'];d=chain.dimensions(g);hist=histories(s['parent']);J,updates=latest_J(hist)
        x=tuning.coordinate(g,'folded');dx=np.linalg.solve(J.T,TARGET-y)
        r=dict(case=s['case'],source=(OLD/'results'/s['case']/'review/extraction_R2.json').relative_to(REPO).as_posix(),
            family=f"Wm{g['Wm']:.6f}",group='stage5_g_ladder' if abs(d['g_mm']-.55)>1e-6 else 'stage5_a_ladder',
            geometry_mm=g,Wm=g['Wm'],a=d['a_mm'],g=d['g_mm'],Lc=d['L_centerline_mm'],y=y.tolist(),
            target_x=(x+dx).tolist(),local_target_correction=dx.tolist(),local_J=J.tolist(),broyden_updates=updates,
            balanced_for_bandwidth=bool(s.get('usable')),BW15=s['BW15'],BW15_star=s['BW15_star'],
            tip_clearance=s['tip_line_clearance_mm'],data_role='retrospective_J_corrected_parameter_label_not_new_HFSS_truth',
            unbalanced_W3_parameter_only=s['parent']=='S5R9_W3')
        rows.append(r);added.append(s['case'])
    return [regroup(r) for r in rows],added

def fit(rows,expanded=True):
    ns=Counter(r['group'] for r in rows);wt=np.array([1/np.sqrt(ns[r['group']]) for r in rows])
    X=np.array([features(r['Wm'],r['a'],r['g'],expanded) for r in rows]);Y=np.array([r['target_x'] for r in rows])
    # Fixed unregularized least squares, matching prior fitting convention.
    # Rank/conditioning are disclosed, not silently filled with invented data.
    A=X*wt[:,None];B=Y*wt[:,None];coef=np.linalg.lstsq(A,B,rcond=None)[0]
    return dict(features=NAMES if expanded else NAMES[:7],expanded=expanded,coefficients=coef.tolist(),
        rank=int(np.linalg.matrix_rank(A)),condition_number=float(np.linalg.cond(A)),
        training_n=len(rows),group_count=len(ns),group_weight='equal total weight per numeric-Wm whole ladder',
        RMSE_mm=np.sqrt(np.mean((X@coef-Y)**2,axis=0)).tolist())

def cross_validation(rows):
    out=[]
    for group in sorted(set(r['group'] for r in rows)):
        tr=[r for r in rows if r['group']!=group];te=[r for r in rows if r['group']==group];score={}
        for expanded in (False,True):
            m=fit(tr,expanded);err=[];response=[]
            for r in te:
                dx=features(r['Wm'],r['a'],r['g'],expanded)@np.array(m['coefficients'])-r['target_x']
                err.append(dx);response.append(dx@np.array(r.get('local_J',tuning.J0)))
            score['expanded' if expanded else 'old_feature_baseline']=dict(rank=m['rank'],condition_number=m['condition_number'],
                RMSE_mm=np.sqrt(np.mean(np.square(err),axis=0)).tolist(),
                J_linearized_response_RMSE=np.sqrt(np.mean(np.square(response),axis=0)).tolist())
        out.append(dict(held_out_whole_numeric_Wm_ladder=group,n=len(te),case_ids=[r['case'] for r in te],models=score))
    return dict(folds=out,limitations=['Retrospective target labels are locally J-corrected; this is not blind HFSS validation.',
        'Same physical width and ladder stay together even when family strings differ.',
        'No CV model selection: expanded features fixed before stage6; rank/condition and baseline disclosed.'])

def candidate(m,w,a,gap,target=TARGET,name='W4'):
    xx=features(w,a,gap)@np.array(m['coefficients'])+np.linalg.solve(tuning.J0.T,np.array(target)-TARGET)
    lm,lc,ws=map(float,xx);ws=round(ws,3)
    g=dict(Wm=w,Ws=ws,Lm=round(lm,3),Ls1=round(lc-2*a-2*gap-2*ws,3),Ls2=round(2*ws+gap,3),Ls3=round(a+ws,3))
    sc=presubmit(g,a,tuning_changed=False);rounded_y=np.array(target)+(tuning.coordinate(g,'folded')-xx)@tuning.J0
    return dict(id='S6R10_'+name,design=name,geometry_mm=g,nominal_a_mm=a,g_mm=gap,screen=sc,
        unrounded_target_x=xx.tolist(),target_y=list(map(float,target)),data_role='prospective_T1_not_HFSS_truth',
        prediction=dict(central_valley_GHz=float(rounded_y[0]),D_dB=float(rounded_y[1]),L_dB=float(rounded_y[2]),
            method='R10 expanded retrospective target-parameter fit plus J rounding correction',
            limitations='Target-based prediction, not an independent response surrogate; model discrepancy remains.'))

def perturbations(port_policy,h_port_policy):
    selected=next(r for r in read(OLD/'final/SELECTED.json') if r['parent']=='S5R9_B1')
    b=selected['geometry_mm'];y0=np.array([selected['center'],selected['D'],selected['L']])
    K=np.array(read(OLD/'final/TOLERANCE.json')['designs']['S5R9_B1']['J_Lm_Ls1_Ws_fixed_a_g'])
    out=[]
    definitions=[('Ws',.02),('Lm',.02),('Ls1',.02),('Wm',.02),('etch_e_mm',.01),('er',.05),('h_mm',.038)]
    for j,(key,step) in enumerate(definitions):
        for side in (1,-1):
            i=j*2+(1 if side==1 else 2);name=f'P{i}';g=copy.deepcopy(b);e=0.;er=3.55;h=.813
            if key in ('Ws','Lm','Ls1','Wm'):g[key]=round(g[key]+side*step,10)
            if key=='Ws':g.update(Ls2=round(2*g['Ws']+.55,10),Ls3=round(1.8+g['Ws'],10))
            if key=='etch_e_mm':e=side*step
            # Plan orders er and h low first (P11/P13), high second.
            if key=='er':er=round(3.55-side*step,10)
            if key=='h_mm':h=round(.813-side*step,10)
            ir=cad_ir.build(g,e,er,h,port_policy=port_policy,h_port_policy=h_port_policy)
            prediction=dict(status='无预测',reason='B1 tuning J has no derivative for this perturbation')
            if i<=6:
                idx={'Lm':0,'Ls1':1,'Ws':2}[key];dy=side*step*K[idx];y=y0+dy
                prediction=dict(status='J局部预测',central_valley_GHz=float(y[0]),low_peak_dB=float(y[2]-y[1]/2),
                    high_peak_dB=float(y[2]+y[1]/2),D_dB=float(y[1]),L_dB=float(y[2]),delta_y=dy.tolist())
            out.append(dict(id='S6R10_'+name,design=name,perturbation=key,signed_change=side*step if key not in ('er','h_mm') else -side*step,
                base_case=selected['case'],base_geometry_mm=b,cad_ir=ir,geometry_mm=ir['geometry_mm'],prediction=prediction,
                nominal_a_mm=chain.dimensions(ir['geometry_mm'])['a_mm'],data_role='tolerance_single_geometry_no_tuning',
                screen=presubmit(ir['geometry_mm'],chain.dimensions(ir['geometry_mm'])['a_mm'],tuning_changed=False)))
    g=copy.deepcopy(b);g['Ws']=round(g['Ws']+.001,10);g.update(Ls2=round(2*g['Ws']+.55,10),Ls3=round(1.8+g['Ws'],10))
    ir=cad_ir.build(g,port_policy=port_policy,h_port_policy=h_port_policy)
    out.append(dict(id='S6R10_N0',design='N0',base_case=selected['case'],base_geometry_mm=b,cad_ir=ir,geometry_mm=ir['geometry_mm'],
        perturbation='Ws',signed_change=.001,nominal_a_mm=1.8,prediction=dict(status='网格噪声对照，不作独立J检验'),
        screen=presubmit(g,1.8,tuning_changed=False),data_role='mesh_noise_control_no_tuning'))
    return out

def generate(port_policy,h_port_policy):
    rows,added=training();m=fit(rows);oldfit=fit(rows,False);cv=cross_validation(rows)
    hist=histories('S5R9_W3');sg=tuning.propose_history(hist,1.8,'folded')
    if not sg['needs_solve']:raise RuntimeError('W3 T4 proposal unavailable: '+str(sg))
    w3=dict(id='S6R10_W3',design='W3',geometry_mm=sg['geometry_mm'],nominal_a_mm=1.8,g_mm=.55,
        screen=sg['screen'],tuning=sg,prediction=sg['predicted_y'],data_role='R9_T1_T3_Broyden_continuation_T4_not_blind')
    w4=candidate(m,2.65,1.8,.55)
    ps=perturbations(port_policy,h_port_policy)
    # Reviewer platform already independently reconstructed from stage5 results.
    platform=read(REPO/'experiments/fold_bandwidth_review_r10_20261114/out/S5_RULES.json')['wm_platform']
    xx=np.array(platform['points']);pcoef=np.linalg.lstsq(np.c_[np.ones(len(xx)),xx[:,0]],xx[:,1],rcond=None)[0]
    w4['prediction']['BW15_star_primary_linear_GHz']=float(pcoef@[1,2.65])
    quad=np.polyfit(xx[:,0],xx[:,1],2)
    w4['prediction']['BW15_star_quadratic_alternative_GHz']=float(np.polyval(quad,2.65))
    w4['prediction']['BW15_star_warning']='Outside measured usable Wm<=2.35; linear vs quadratic are frozen alternatives, not post-hoc selection.'
    plan=REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R10.md'
    sources=[OLD/'offline/TRAINING.json',OLD/'offline/SENSITIVITY.json',OLD/'final/SELECTED.json',OLD/'final/TOLERANCE.json',OLD/'FINAL_MANIFEST.json',plan,
        REPO/'experiments/fold_bandwidth_review_r10_20261114/out/S5_RULES.json',H/'offline/SOURCE_NATIVE_B1.json']
    for r in rows:
        if r['case'] in added:
            sources.extend([REPO/r['source'],OLD/'results'/r['case']/'INPUT.json'])
    for p in sorted((OLD/'results').glob('S5R9_W3__T*')):
        sources.extend([p/'review/extraction_R2.json',p/'INPUT.json'])
    return dict(status='DRAFT_NOT_RELEASED',policies=dict(port_cut_faces=port_policy,thickness_ports=h_port_policy,
        human_confirmation_received=False),training=dict(rows=rows,stage5_added=added),parameter_model=m,old_feature_refit=oldfit,
        cross_validation=cv,stage6A=ps,W3_T4=w3,W4_T1=w4,
        Q11_Q16_verbatim=plan.read_text(encoding='utf-8').split('## 4. 审核方登记的预测')[1].split('## 5.')[0],
        source_sha256={p.relative_to(REPO).as_posix():sha(p) for p in sources},
        budget=dict(previous_geometry=173,previous_Analyze=1633,new_geometry_cap=27,cumulative_cap=200,
            ordinary_per_geometry_Analyze_cap=14,dense_per_geometry_Analyze_cap=20,unused_slots_not_transferable=True),
        authorizes_solver=False,limitations=['Nominal interpolation is not direct-frequency or manufacturing certification.',
            'Per-side measured tolerance values override J for nonlinear responses.',
            'No stage7, no hooks, no old uniform data or frozen inputs modified.'])

if __name__=='__main__':
    # Draft only: this command cannot promote a freeze or authorize a solver.
    d=generate('clip_cut_faces','height_8h_width_fixed');put(H/'draft/OFFLINE_PROPOSAL.json',d)
    print('rows',len(d['training']['rows']),'new',len(d['training']['stage5_added']),'rank',d['parameter_model']['rank'])
    for c in d['stage6A']+[d['W3_T4'],d['W4_T1']]:print(c['id'],c['geometry_mm'],c['screen']['can_submit'])
