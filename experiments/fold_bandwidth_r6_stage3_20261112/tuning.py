"""阶段3有限等纹波调参：固定Wm/a/g；每设计最多三几何。离线，无派发。"""
import sys,math,json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
REPO=Path(__file__).resolve().parents[2]
for folder in ('fold_bandwidth_r2_20261110','fold_bandwidth_r3_20261110','fold_bandwidth_r6_stage2_model_20261112'):
    sys.path.insert(0,str(REPO/'experiments'/folder))
import chain,geometry
from presubmit import presubmit
from stage3_metrics import tuned
from fit_model import forward
from freeze_2b import predict
MODEL=REPO/'experiments/fold_bandwidth_r6_stage2_model_20261112/fit_complete/MODEL.json'
FM_TARGET,FS_TARGET=6.622,6.588
def new_prediction(g,topology):
    return predict(g,topology,json.loads(MODEL.read_text(encoding='utf-8-sig')))
def classify(q):
    r=tuned(q)
    return dict(**r,length_calibrated=bool(q['shape'].get('shape_valid') and
        abs((q['shape'].get('central_valley_GHz') or 0)-6.72)<=.03000000001 and
        (q['shape'].get('peak_difference_dB') is not None and q['shape']['peak_difference_dB']<=.5)),
        equivalent_fit_unique_under_R2=q['circuit'].get('extraction_nonunique') is False,
        usable_for_law=r['tuned'] and q['circuit'].get('extraction_nonunique') is False)
def propose(q,nominal_a,topology='folded'):
    st=classify(q);g=dict(q['geometry_mm'])
    no=lambda reason:dict(status=st,needs_solve=False,reason=reason)
    if st['tuned']:return no('already_R3_tuned')
    if not st['equivalent_fit_unique_under_R2']:return no('nonunique_no_unjustified_tuning')
    p=q['circuit']['parameters'];fm,fs=p['fm_GHz'],p['fs_GHz']
    if not all(math.isfinite(x) and x>0 for x in (fm,fs,p['zm_eff'],p['zs_eff'])):return no('invalid_extraction')
    a=geometry.slot_boxes # ensure R2 geometry module is loaded; no native operation
    dim=chain.dimensions(g,topology);arm=dim['a_mm'];gap=dim['g_mm']
    model=json.loads(MODEL.read_text(encoding='utf-8-sig'))
    old=forward(g,topology,model)
    # Use extracted P to calibrate local width sensitivity, not as a new global fit.
    P=p['zm_eff']*p['zs_eff']
    if P<=1:return no('not_three_valley_P')
    mean=st['mean_inner_peak_dB']
    target_db=-20.3
    # When peaks already balanced, preserve observed-to-circuit ripple offset.
    ripple_target=chain.ripple_db(P)+(target_db-mean) if st['length_calibrated'] else target_db
    if not -60<ripple_target<-1:return no('invalid_local_ripple_target')
    targetP=brentq(lambda x:chain.ripple_db(x)-ripple_target,1.000001,20.)
    factor=P/old['P_eff']
    def candidate_width(w):
        return {**g,'Ws':w,'Ls2':0. if topology=='straight_control' else 2*w+gap,
                'Ls3':0. if topology=='straight_control' else arm+w}
    # Bounded local step; no implicit geometry-budget expansion.
    low=max(.05,g['Ws']*.7);high=min(.8,g['Ws']*1.3)
    def delta(w):return forward(candidate_width(w),topology,model)['P_eff']*factor-targetP
    vals=[delta(low),delta(high)]
    if vals[0]*vals[1]>0:
        ws=min((low,high),key=lambda w:abs(delta(w)))
        limited=True
    else:ws=brentq(delta,low,high);limited=False
    ws=round(ws,3)
    # Preserve observed end corrections; carry only published local width slopes.
    old_dm=chain.wave_length(g['Wm'],fm)-g['Lm']
    old_ds=chain.wave_length(g['Ws'],fs,False)-dim['L_centerline_mm']
    dm=old_dm+.3751*(ws-g['Ws'])
    ds=old_ds-1.2118*(ws-g['Ws'])
    c=candidate_width(ws)
    subtract=0 if topology=='straight_control' else 2*arm+2*gap+4*ws
    c.update(Lm=round(chain.wave_length(g['Wm'],FM_TARGET)-dm,3),
             Ls1=round(chain.wave_length(ws,FS_TARGET,False)-ds-subtract,3))
    sc=presubmit(c,nominal_a,tuning_changed=True,topology=topology)
    if not sc['can_submit']:return dict(**no('updated_geometry_screen_failed'),screen=sc)
    n=sc['geometry_mm']
    if n==g:return no('no_change_after_rounding')
    assert n['Wm']==g['Wm']
    return dict(status=st,needs_solve=True,reason='local_P_ripple_and_extracted_end_correction',
       geometry_mm=n,previous_geometry_mm=g,screen=sc,actual_a_mm=sc['actual_a_mm'],
       target_mean_dB=-20.3,target_P=targetP,width_step_clamped=limited,
       observed_to_frozen_P_factor=factor,targets_GHz=dict(fm=FM_TARGET,fs=FS_TARGET),
       prediction=new_prediction(n,topology),data_role='tuned_data',
       caveat='局部等效模型建议，不保证达标；R2净距失败仅按R2规则减折臂，记录实际a。')
