"""R12 finite continuation: Gamma-margin, measured-J T1 and immutable R4 setup.

Pure offline functions. No AEDT import, solver dispatch, hook or old file write.
"""
import argparse,copy,math,shutil
import numpy as np
from common_stage2 import *
import cad_ir, native_control as nc, geometry_gate as gg
import prepare_r10 as prep, tolerance_analysis as ta
from tuning import coordinate,inverse,state

PRIOR_H=REPO/'experiments/fold_bandwidth_r11_stage6_r3_final_20261115'
PRIOR_R=Path('F:/2026-1/circuit/test/output/fig8_r11_stage6_r3_final_20261115')
H0=.813
TOL_H=.038
GAMMA=lambda x:10.**(x/20.)

def source_measurements():
    st=read(PRIOR_H/'CURRENT_STATUS.json')
    if (st['geometry_total'],st['actual_Analyze_total'],st['R10_geometries'],st['R10_actual_Analyze'])!=(189,1807,16,174):raise RuntimeError('R3 cost mismatch')
    ms={d['parent_id'].removeprefix('S6R10_'):d['measurement'] for d in st['completed_parents']}
    from manage import baseline
    return baseline(),ms

def margin(base,ms,h0=H0,tol_h=TOL_H):
    ta.valid(base)
    if not math.isfinite(h0) or h0<=0 or not 0<tol_h<h0:raise ValueError('invalid board thickness inputs')
    gb=GAMMA(ta.highest(base));dg={};worst={}
    for src in ('etch','er','h'):
        ids=ta.PAIRS[src]
        for n in ids:ta.valid(ms[n])
        worst[src]=max(ids,key=lambda n:ta.highest(ms[n]))
        dg[src]=max(0.,GAMMA(ta.highest(ms[worst[src]]))-gb)*(tol_h/.038 if src=='h' else 1.)
    rss=math.sqrt(sum(v*v for v in dg.values()))
    mesh=GAMMA(ta.highest(base)+.256)-gb;tune=GAMMA(ta.highest(base)+.1)-gb
    req=.1-rss-mesh-tune
    if req<=0:raise RuntimeError('nonpositive reflection budget')
    noise=abs(ta.highest(ms['N0'])-ta.highest(base))
    if noise>.1:raise RuntimeError('R12 frozen source N0 assumption changed')
    return dict(h0_mm=h0,tol_h_mm=tol_h,Gamma_B=gb,dGamma=dg,rss=rss,mesh=mesh,tune=tune,Gamma_req=req,
        P_req_dB=20*math.log10(req),statistical_dense_Gamma_limit=.1-rss,
        statistical_dense_dB_limit=20*math.log10(.1-rss),corner_worst_sides=worst,
        noise_dB=noise,noise_added=False,conditional_dense_cancelled=True,C1_cancelled=True,
        stage6B_decision='try_B1R_max_three',
        caveat='Plan-prescribed RSS simulation margin, not a probabilistic yield or connector certificate; B1 sensitivities transferred to B1R are tested by C1R.')

def response(m):return np.array([m['center_GHz'],m['low_peak_dB'],m['high_peak_dB']])

def t1(base,ms,a):
    src=prep.OLD/'results/S5R9_B1__T2';g=read(src/'INPUT.json')['design']['geometry_mm'];q=read(src/'review/extraction_R2.json')
    y0=state(q);req=a['P_req_dB'];target=np.array([6.72,req-.1,req-.1])
    # Rows: physical [Lm,Ls1,Ws], columns: [center,low,high].
    K=np.array([(response(ms[p])-response(ms[m]))/.04 for p,m in [('P3','P4'),('P5','P6'),('P1','P2')]])
    dx=np.linalg.solve(K.T,target-response(base))
    proposed=copy.deepcopy(g)
    for k,d in zip(('Lm','Ls1','Ws'),dx):proposed[k]=round(g[k]+float(d),3)
    proposed.update(Ls2=round(2*proposed['Ws']+.55,3),Ls3=round(1.8+proposed['Ws'],3))
    physical=np.array([proposed[k]-g[k] for k in ('Lm','Ls1','Ws')])
    fy=response(base)+physical@K
    # Convert to fixed [Lm,Lc,Ws] -> [center,D,L] for finite Broyden follow-up.
    Jy=np.c_[K[:,0],K[:,2]-K[:,1],(K[:,1]+K[:,2])/2]
    J=np.array([Jy[0],Jy[1],Jy[2]-2*Jy[1]])
    from tuning import J0
    oldstep=np.linalg.solve(J0.T,np.array([6.72,0,req-.1])-y0)
    oldproposal=inverse(g,coordinate(g,'folded')+oldstep,'folded',1.8,.55)
    # Independent two-parameter-law estimate from the review's equivalent parameters.
    r=read(REPO/'experiments/fold_bandwidth_review_r12_20261115/out/S6R3_RECOMPUTED.json')
    rb=r['points']['B1'];law=r['laws']
    ev=lambda n:np.array([r['points'][n]['eq']['P_eff'],1000*(r['points'][n]['eq']['fm_GHz']-r['points'][n]['eq']['fs_GHz']),r['points'][n]['valley_GHz']])
    E=np.array([(ev(p)-ev(m))/.04 for p,m in [('P3','P4'),('P5','P6'),('P1','P2')]])
    eqdelta=np.array([(req-.1-y0[2])/law['mean_vs_Peff']['slope_dB_per_unit'],
                     -y0[1]/law['tilt_vs_detune']['slope_dB_per_MHz'],6.72-y0[0]])
    edx=np.linalg.solve(E.T,eqdelta);eg=copy.deepcopy(g)
    for k,d in zip(('Lm','Ls1','Ws'),edx):eg[k]=round(g[k]+float(d),3)
    eg.update(Ls2=round(2*eg['Ws']+.55,3),Ls3=round(1.8+eg['Ws'],3))
    from presubmit import presubmit
    sc=presubmit(proposed,1.8,tuning_changed=False)
    if not sc['can_submit']:raise RuntimeError('R12 T1 geometry conflict; no alternate point')
    predy=[float(fy[0]),float(fy[2]-fy[1]),float((fy[1]+fy[2])/2)]
    tuning=dict(needs_solve=True,geometry_mm=proposed,base_case='S5R9_B1__T2',base_y=y0.tolist(),J=J.tolist(),
        actual_step=(coordinate(proposed,'folded')-coordinate(g,'folded')).tolist(),predicted_y=predy,
        reason='R12 measured central-difference J T1, not blind inference',broyden_updates=[],
        raw_physical_step=dx.tolist(),T1_extrapolation_step_limit_note='R12 explicit T1 extrapolation; subsequent corrections retain R7 caps .06/.40/.13 mm')
    d=dict(id='S6R10_B1R',design='B1R',geometry_mm=proposed,nominal_a_mm=1.8,g_mm=.55,
        target_y=[6.72,0.,req-.1],prediction=dict(response_y=predy,method='B1 measured central-difference physical J',
        extrapolation='approximately 4-5 tolerance steps; not HFSS truth'),tuning=tuning,screen=sc,
        data_role='prospective_finite_tuning_T1_not_blind_test')
    d=prep.decorate(d,'EQ')
    reference=dict(Ws=.462,Lm=6.587,Ls1=12.543)
    return d,dict(base_geometry_mm=g,physical_rows=['Lm','Ls1','Ws'],response_columns=['center_GHz','low_peak_dB','high_peak_dB'],
        measured_K=K.tolist(),target_response=target.tolist(),rounded_prediction=fy.tolist(),
        two_parameter_law_geometry_mm=eg,two_parameter_delta=eqdelta.tolist(),two_parameter_physical_step=edx.tolist(),
        original_frozen_J_alternative=oldproposal,original_J_step=oldstep.tolist(),
        reviewer_reference=reference,reference_differences_mm={k:proposed[k]-v for k,v in reference.items()},
        choice='Measured central differences give direct peak and center response; equivalent-parameter law is a cross-check. Target is P_req-0.1 (middle of authorized window), not exactly P_req. Historical tuning J alternative retained, not selected post hoc.')

def statistical_pass(dense,a):
    ta.valid(dense)
    return all(GAMMA(dense[k])<=a['statistical_dense_Gamma_limit']+1e-14 for k in ('low_peak_dB','high_peak_dB'))

def confirmation(nominal,dense,corner,a):
    for m in (nominal,dense,corner):ta.valid(m)
    signed=[dense[k]-nominal[k] for k in ('low_peak_dB','high_peak_dB')];bias=max(0.,*signed)
    stat=statistical_pass(dense,a);cp=ta.highest(corner)+bias<=-20.
    return dict(statistical_RSS_robust=stat,worst_corner_robust=cp,both_passed=stat and cp,
        dense_pass=stat,corner_with_mesh_pass=cp,own_upward_mesh_bias_dB=bias,dense_peak_changes_dB=signed,
        corrected_corner_highest_dB=ta.highest(corner)+bias,
        measured_corner_dGamma=GAMMA(ta.highest(corner))-GAMMA(ta.highest(nominal)),
        statistical_Gamma_limit=a['statistical_dense_Gamma_limit'],statistical_dB_limit=a['statistical_dense_dB_limit'],
        labels=[s for s,ok in [('统计稳健（平方和根）',stat),('最坏角点稳健',cp)] if ok],
        not_manufacturing_or_connector_certified=True)

def offline():
    b,ms=source_measurements();a=margin(b,ms);br,t=t1(b,ms,a)
    ref=read(REPO/'experiments/fold_bandwidth_review_r12_20261115/out/S6R3_RECOMPUTED.json')['margin_gamma']
    diff=abs(a['P_req_dB']-ref['P_req_dB'])
    if diff>.005:raise RuntimeError('review Gamma-margin mismatch')
    plan=(REPO/'docs/PLAN_20261115_FOLD_BANDWIDTH_R12.md').read_text(encoding='utf-8')
    predictions=plan.split('## 4. 新登记的预测')[1].split('## 5.')[0]
    o=dict(at=now(),status='R12_R4_PRE_SOLVE_FREEZE',analysis=a,peak_window_dB=[a['P_req_dB']-.2,a['P_req_dB']],
        corner_changes=dict(e=.01,er=3.50,h=H0-TOL_H),designs={'S6R10_B1R':br},T1_comparison=t,
        reviewer_margin_difference_dB=diff,Q21_Q24_verbatim=predictions,source_measurements=ms,baseline=b,
        cancelled=['P1dense','P2dense','C1'],stage7_authorized=False,
        budget=dict(prior_geometry=189,prior_Analyze=1807,new_geometry_max=8,cumulative_this_round_max=197,
                    cumulative_cap=200,ordinary_Analyze_cap=14,dense_Analyze_cap=20,new_Analyze_max=118))
    (HERE/'freeze_6B').mkdir();write(HERE/'freeze_6B/R10_2.json',o)
    write(HERE/'freeze/R12_R4.json',o)
    return dict(P_req_dB=a['P_req_dB'],T1=br['geometry_mm'],comparison=t)

def prepare_r4(root):
    if root.exists():raise RuntimeError('R4 already exists; never reset')
    import psutil
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('resources busy')
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed']:raise RuntimeError('offline tests failed')
    b,ms=source_measurements();cfg=copy.deepcopy(read(PRIOR_R/'authorization.json'))
    if (len(list((PRIOR_R/'ledger').glob('geometry_*.json'))),len(list((PRIOR_R/'ledger').glob('Analyze_*.json'))))!=(6,77):raise RuntimeError('R3 ledger mismatch')
    for rel,h in read(PRIOR_H/'STOP_MANIFEST.json').items():
        if sha(PRIOR_H/rel)!=h:raise RuntimeError('historical R3 closure mismatch '+rel)
        cfg['historical_hashes'][str(PRIOR_H/rel)]=h
    for p in [PRIOR_H/'STOP_MANIFEST.json',PRIOR_R/'STOP.json',PRIOR_R/'DENSE_COMPATIBILITY_FAILURE.json',PRIOR_R/'authorization.json']+list((PRIOR_R/'ledger').glob('*.json')):
        cfg['historical_hashes'][str(p)]=sha(p)
    st=read(PRIOR_H/'CURRENT_STATUS.json');closed=[d['parent_id'] for d in st['completed_parents']]
    paths=copy.deepcopy(cfg['inherited_public_result_paths'])
    for d in st['completed_parents']:
        c=d['selected_case']
        if (PRIOR_H/'results'/c).exists():paths[c]=(PRIOR_H/'results'/c).relative_to(REPO).as_posix()
    cfg.update(at=now(),execution_revision='R12_STAGE6_R4',plan_commit='ead3d02',human_authorized=True,
        user_authorization='Human accepts R12 section0: finite R4, cancel dense P1/P2 and C1, Gamma-margin B1R max3+dense+C1R, W3T4 and W4max2, then stop',
        prior_geometry_total=189,prior_Analyze_total=1807,batch_geometry_limit=8,total_geometry_limit=200,
        inherited_stage6_geometry=16,inherited_stage6_Analyze=174,full_stage6_geometry_limit=27,
        inherited_geometry_logicals=[],inherited_logical_Analyze={},inherited_closed_parents=closed,
        inherited_public_result_paths=paths,inherited_case_paths={},case_paths={},case_specs={},required_preflight_cases=[],
        parent_order=closed+['S6R10_'+n for n in ('B1R','B1Rdense','C1R','W3','W4')],
        cancelled_parents=['S6R10_'+n for n in ('P1dense','P2dense','C1')],
        technical_recovery_policy='R12 finite R4 only; any modeling/compatibility/native-validation error stops. No automatic R5.',
        continuation_basis='R12 Gamma-margin overrides R10 deep-target skip; corrected fixed outline; stage6 only',
        batch_max_Analyze_from_geometry_caps=118,full_stage6_max_Analyze_from_geometry_caps=292)
    f=read(HERE/'freeze_6B/R10_2.json')
    cfg['designs']['S6R10_B1R']=f['designs']['S6R10_B1R']
    # Every new spec() rebuilds IR too. Rebuilding here is not a field insertion.
    for n in ('B1R','W3','W4'):
        p='S6R10_'+n;cfg['designs'][p]=prep.decorate(cfg['designs'][p],'EQ')
    for n,ordinals in [('B1R',range(1,4)),('B1Rdense',[1]),('C1R',[1]),('W3',[4]),('W4',range(1,3))]:
        p='S6R10_'+n
        for i in ordinals:
            c=p+f'__T{i}';cfg['case_paths'][c]=f'runs/{p}/attempt_{i:03d}';cfg['case_specs'][c]=dict(parent_id=p,attempt_ordinal=i,numerical_retry=False)
    cfg['plan_hashes']['docs/PLAN_20261115_FOLD_BANDWIDTH_R12.md']=sha(REPO/'docs/PLAN_20261115_FOLD_BANDWIDTH_R12.md')
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline','freeze_6B') for p in (HERE/folder).glob('*.json')})
    root.mkdir();(HERE/'pre_solve').mkdir()
    for n in ('ledger','decisions','model_freeze','publications','preflights'):(root/n).mkdir()
    write(root/'authorization.json',cfg);shutil.copyfile(PRIOR_R/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    for p in closed:shutil.copyfile(PRIOR_R/'decisions'/(p+'_FINAL.json'),root/'decisions'/(p+'_FINAL.json'))
    return prep.make_input(root,'S6R10_B1R',1)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['offline','prepare']);a=ap.parse_args()
    print(offline() if a.command=='offline' else prepare_r4(prep.ROOT))
