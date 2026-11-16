"""R15 scientific policy: pure offline; no dispatch or native imports."""
import math,copy
import numpy as np
from common_stage2 import *
import cad_ir
from tuning import coordinate,inverse,state,broyden
PRIOR_H=REPO/'experiments/fold_bandwidth_r14_stage6_r6_20261116'
PRIOR_R=Path('F:/2026-1/circuit/test/output/fig8_r14_stage6_r6_20261116')
PLAN='docs/PLAN_20261116_FOLD_BANDWIDTH_R15.md'
GAMMA=lambda x:10.**(x/20.)
H0=.813; TOL_H=.038

def margin(tol_h=TOL_H,h0=H0,statistical=False):
    if not math.isfinite(h0) or not math.isfinite(tol_h) or not 0<tol_h<h0:raise ValueError('invalid thickness')
    # Use R15's explicitly tabulated constants, not rounded dB arithmetic.
    corner=.026838-.020355+.020355*tol_h/.038
    source=read(PRIOR_H/'final/RESULTS.json')['margin']['dGamma']
    rss=math.sqrt(source['etch']**2+source['er']**2+(.020355*tol_h/.038)**2)
    mesh=.002538;tune=.001070;residual=.0023507
    req=.1-(rss+residual if statistical else corner)-mesh-tune
    if req<=0:raise ValueError('nonpositive Gamma budget')
    return dict(h0_mm=h0,tol_h_mm=tol_h,mode='statistical' if statistical else 'corner',
        corner_dGamma=corner,RSS=rss,mesh=mesh,tune=tune,assumed_residual=residual,
        Gamma_req=req,P_req_dB=20*math.log10(req),Gamma_stat=.1-rss,
        hypothesis='B1R sensitivities transferred to W4R; C1W independently checks this, not assumed certified')

def margin_table():
    table=[(.038,-23.15,-22.70),(.025,-22.33,-21.93),(.051,-24.07,-23.55),(.005,-21.19,-21.00)]
    return [dict(tol_h_mm=h,mode=mode,computed_dB=margin(h,statistical=stat)['P_req_dB'],
        plan_dB=expected,error_dB=margin(h,statistical=stat)['P_req_dB']-expected,
        within_0p005=abs(margin(h,statistical=stat)['P_req_dB']-expected)<=.005)
        for h,c,s in table for stat,mode,expected in [(False,'corner',c),(True,'statistical',s)]]

def nominal_check(q,req,s21_min=None):
    y=state(q);pk=q['shape'].get('inner_peaks',[])
    bw=q['bandwidths']['BW20'].get('BW_GHz')
    # R12/R15 S21 is the minimum native sample inside the complete BW20 main window.
    s21=s21_min
    ok_y=y is not None and 6.72-1e-10<=y[0]<=6.75+1e-10 and abs(y[1])<=.2+1e-10 and all(req-.2-1e-10<=p['S11_dB']<=req+1e-10 for p in pk)
    error=float(np.max(abs(y-np.array([6.735,0,req-.1]))/[.015,.2,.1])) if y is not None else None
    return dict(tuned=bool(ok_y and bw is not None and s21 is not None and s21>=-2),usable_for_law=bool(ok_y and bw is not None and s21 is not None and s21>=-2),
        error_e=error,mean_inner_peak_dB=float(y[2]) if y is not None else None,signed_D_dB=float(y[1]) if y is not None else None,
        hard_design_peaks_pass=bool(y is not None and max(p['S11_dB'] for p in pk)<=-20),
        center_window_GHz=[6.72,6.75],peak_window_dB=[req-.2,req],S21_dB=s21,BW20_GHz=bw)

def build_design(g,name,kind='EQ',e=0.,er=3.55,h=.813,**extra):
    from presubmit import presubmit
    import chain
    ir=cad_ir.json_value(cad_ir.build(g,e,er,h,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'))
    a=chain.dimensions(ir['geometry_mm'])['a_mm']
    screen=presubmit(ir['geometry_mm'],a,tuning_changed=False,topology='folded')
    from geometry_gate import check_ir
    check_ir(ir)
    return dict(id='S7R15_'+name,design=name,geometry_mm=ir['geometry_mm'],base_geometry_mm=g,cad_ir=ir,
        nominal_a_mm=a,g_mm=.55,topology='folded',material_role='archived_lossy',board_half_x_mm=15.,kind=kind,
        family='W4R',dense_confirmation=name=='W4Rdense',tuning=None,screen=screen,
        data_role='prospective_finite_tuning_not_independent_blind_test' if kind=='EQ' else 'W4R_'+name+'_control',**extra)

def t1(m):
    result=read(PRIOR_H/'final/RESULTS.json');ms=result['stage6A']
    w4=PRIOR_H/'results/S6R10_W4__T1';g=read(w4/'INPUT.json')['design']['geometry_mm'];q=read(w4/'review/extraction_R2.json');y0=state(q)
    response=lambda d:np.array([d['center_GHz'],d['low_peak_dB'],d['high_peak_dB']])
    K=np.array([(response(ms[p])-response(ms[n]))/.04 for p,n in [('P3','P4'),('P5','P6'),('P1','P2')]])
    target=np.array([6.735,m['P_req_dB']-.1,m['P_req_dB']-.1])
    base=response(result['platform']['W4']['measurement']);dx=np.linalg.solve(K.T,target-base)
    proposed={**g,**{k:round(g[k]+float(d),3) for k,d in zip(('Lm','Ls1','Ws'),dx)}}
    proposed.update(Ls2=round(2*proposed['Ws']+.55,3),Ls3=round(1.8+proposed['Ws'],3))
    actual=np.array([proposed[k]-g[k] for k in ('Lm','Ls1','Ws')]);pred=base+actual@K
    Jy=np.c_[K[:,0],K[:,2]-K[:,1],(K[:,1]+K[:,2])/2];J=np.array([Jy[0],Jy[1],Jy[2]-2*Jy[1]])
    near=PRIOR_H/'results/S6R10_W3__T4';nt=read(near/'INPUT.json')['design']['tuning'];nq=read(near/'review/extraction_R2.json')
    ng=REPO/'experiments/fold_bandwidth_r9_stage5_20261114/results'/nt['base_case'];bq=read(ng/'review/extraction_R2.json')
    Jnear,upd=broyden(np.array(nt['J']),coordinate(nq['geometry_mm'],'folded')-coordinate(bq['geometry_mm'],'folded'),state(nq)-state(bq))
    dy=np.array([6.735,0,m['P_req_dB']-.1])-y0
    ndx=np.linalg.solve(Jnear.T,dy);ng=inverse(g,coordinate(g,'folded')+ndx,'folded',1.8,.55)
    predy=[float(pred[0]),float(pred[2]-pred[1]),float((pred[1]+pred[2])/2)]
    tuning=dict(needs_solve=True,geometry_mm=proposed,base_case='S6R10_W4__T1',base_y=y0.tolist(),J=J.tolist(),
        actual_step=(coordinate(proposed,'folded')-coordinate(g,'folded')).tolist(),predicted_y=predy,
        reason='R15 T1: B1 measured central-difference J, applied at W4; explicit large-step extrapolation',broyden_updates=[],raw_physical_step=dx.tolist())
    design=build_design(proposed,'W4R',target_y=[6.735,0,m['P_req_dB']-.1],prediction=dict(response_y=predy,method=tuning['reason']))
    design['tuning']=tuning
    from presubmit import presubmit
    ref=dict(Ws=.557,Lm=6.592,Ls1=12.779);diff={k:proposed[k]-v for k,v in ref.items()}
    proof=dict(base_case='S6R10_W4__T1',base_geometry_mm=g,target_response=target.tolist(),
        measured_B1_physical_J=K.tolist(),coordinate_J=J.tolist(),selected_geometry_mm=proposed,selected_prediction=predy,
        nearby_W3_Broyden_proxy_J=Jnear.tolist(),nearby_proxy_update=upd,nearby_proxy_geometry_mm=ng,nearby_proxy_prediction=(y0+(coordinate(ng,'folded')-coordinate(g,'folded'))@Jnear).tolist(),
        nearby_proxy_screen=presubmit(ng,1.8,tuning_changed=False),
        nearby_proxy_caveat='No independently perturbed W4 J exists. Nearest measured tuning seed is W3 (Wm2.50); its updated Broyden J is a transferred approximation, not a claimed W4-local measurement.',
        reviewer_reference=ref,differences_from_reference_mm=diff,exceeds_0p04={k:abs(v)>.04 for k,v in diff.items()},
        choice_reason='B1 direct central differences measure both peaks and valley, so they are chosen before solving. Reference scales one B1-to-B1R secant by mean only; our solve also corrects W4 signed peak difference and targets valley6.735 and P_req-0.1. Differences >.04 are disclosed, not silently clipped.',
        followup_caps_coordinate_mm=[.06,.40,.13],followup_algorithm='Same frozen selective Broyden and width-only clearance backoff as R6; tighter delivery center tolerance ±.015; max4 total attempts')
    return design,proof

def confirmation(nominal,dense,corner,residual,m):
    highest=lambda x:max(x['low_peak_dB'],x['high_peak_dB'])
    gn=GAMMA(highest(nominal)) if nominal else None;gd=GAMMA(highest(dense)) if dense else None;gc=GAMMA(highest(corner)) if corner else None
    own=max(0,gd-gn) if gd is not None and gn is not None else None;bias=m['mesh'] if own is None else own
    stat=None if gd is None else '统计稳健（含网格残差）' if gd+residual<=m['Gamma_stat'] else '统计稳健（不含网格残差，边缘）' if gd<=m['Gamma_stat'] else '不满足统计稳健'
    worst=None if gc is None else gc+bias<=.1
    return dict(statistical_label=stat,Gamma_dense=gd,DeltaS_residual=residual,Gamma_stat=m['Gamma_stat'],
        own_nonnegative_mesh_dGamma=own,corner_bias_used=bias,corner_bias_source='own_W4R' if own is not None else 'borrowed_B1R_unconfirmed',
        Gamma_C1W=gc,corner_Gamma_plus_bias=gc+bias if gc is not None else None,worst_corner_robust=worst,
        worst_corner_label=None if worst is None else ('最坏角点稳健'+('（借用B1R网格偏差，未经本设计确认）' if own is None else '') if worst else '最坏角点不满足'),
        corner_minus_nominal_dGamma=gc-gn if gc is not None and gn is not None else None,
        dense_center_shift_MHz=(dense['center_GHz']-nominal['center_GHz'])*1000 if dense and nominal else None,
        dense_peak_changes_dGamma={k:GAMMA(dense[k])-GAMMA(nominal[k]) for k in ('low_peak_dB','high_peak_dB')} if dense and nominal else None,
        not_connector_or_manufacturing_certificate=True)
