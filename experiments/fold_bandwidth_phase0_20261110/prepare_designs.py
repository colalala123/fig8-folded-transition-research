"""Freeze OFFLINE proposals for review; never dispatch a simulation.

Off-gap numbers are a declared null-effect prior, not learned g predictions.
Stage-4 prior predictions must not be confused with the future post-stage-3 freeze.
"""
import argparse
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
import chain
from audit import read,write,csvwrite,sha,HERE,REPO


def quantize(g, tune_width=False):
    d=chain.derived(g)
    # Preserve archived fixed-width factors exactly. Changing them to a rounded
    # absolute grid would quietly confound the a/g treatment with width changes.
    wm=g['Wm'];ws=round(g['Ws'],3) if tune_width else g['Ws']
    lm,l1=[round(g[k],3) for k in ('Lm','Ls1')]
    return dict(Wm=wm,Ws=ws,Lm=lm,Ls1=l1,
                Ls2=d['g_mm']+2*ws,Ls3=d['a_mm']+ws)


def straight(wm,ws):
    # Separate topology, no folded calibration masquerading as a=0 evidence.
    return dict(Wm=wm,Ws=ws,Lm=round(chain.wave_length(wm,6.622),3),
                Ls1=round(chain.wave_length(ws,6.588,False),3),Ls2=0.,Ls3=0.)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    out=ap.parse_args().out;out.mkdir(parents=True,exist_ok=False)
    rows=read(REPO/'model/DATASET.json')['rows']
    bases=sorted([r for r in rows if r['source']=='original48' and abs(r['a']-1.8)<1e-8],key=lambda r:(r['R'],r['family']))
    assert len(bases)==24
    selected=[bases[0],bases[len(bases)//2],bases[-1]]
    selection=dict(rule='Original48 a=1.8 only, sort (R,family), indices [0,12,23]; upper median for even count',
                   bases=[dict(case=r['case'],family=r['family'],P=r['P'],R=r['R'],geometry=r['geometry']) for r in selected])
    write(out/'BASE_FAMILIES.json',selection)
    records=[];f=np.arange(.01,15.0001,.01)
    hashes={str(p.relative_to(REPO)).replace('\\','/'):sha(p) for p in [HERE/'chain.py',HERE/'prepare_designs.py',REPO/'analysis/line_models.py',REPO/'model/DATASET.json',REPO/'model/dataset.npz',REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH.md',REPO/'hfss/INV01_A14.aedt']}
    def add(id,stage,experiment,base,g,role='planned_training',parent=None,exact=False,uniform=False):
        gg=g if exact or uniform else quantize(g,tune_width=stage==3)
        result=None;reason=[];screen=None
        if uniform:
            reason=['separate_straight_topology_not_built_or_calibrated']
        elif parent:
            reason=['conditional_on_parent_final_tuned_geometry_and_loss_model']
            screen=chain.geometry_screen(gg)
        else:
            screen=chain.geometry_screen(gg)
            try:
                c=chain.forward(gg,exploratory=True)
                s11,s21=chain.circuit(f,*[c[k] for k in ('zm_eff','zs_eff','fm_GHz','fs_GHz')])
                bb=chain.bands(f,s11,s21)
                result=dict(parameters=c,lossless_circuit_bandwidths=bb,
                            equal_frequency_inner_peak_dB=chain.ripple_db(c['P_eff']),
                            BW_S21_HFSS_prediction_GHz=None,
                            caveat='Ideal lossless S21 bandwidth above is not a calibrated lossy-HFSS prediction; unknown gap effect is set to zero ONLY as a prior.')
                reason+=c['warnings']
            except ValueError as e:
                reason.append('chain_not_evaluable:'+str(e))
        if stage==4:
            reason.append('final_post_stage3_model_and_prospective_prediction_not_available')
        status='excluded_from_proposed_runlist' if screen and not screen['screen_pass'] else 'review_only_not_authorized'
        if screen:reason+=screen['reasons']
        rec=dict(id=id,stage=stage,experiment=experiment,family=base['family'],source_case=base['case'],
                 data_role=role,parent=parent,geometry_mm=gg,unrounded_initial_geometry_mm=g,
                 rounding='archived exact baseline / relative width perturbation' if exact else 'Fixed archived widths exact; new Lm/Ls1 and tuned Ws on 0.001mm grid; dependent a/g exact. Baseline-grid exception requires review.',
                 topology='straight_control' if uniform else 'folded',screen=screen,
                 prediction=result,validity='exploratory_prior_not_validated',blocking_reasons=reason,
                 release_status=status,solver_authorized=False,
                 future_run_directory=('uniform_control/' if uniform else 'runs/')+id+'/attempt_001',
                 initial_prediction_stage='phase0_prior',future_prospective_freeze_required=stage==4,
                 max_geometry_attempts=3 if stage in (2,3) and not parent else 1)
        records.append(rec)
    # Stage1: 3 exact replays plus 9 perturbations, including an independent zero repeat.
    for r in selected:add('S1_BASE_'+r['family'],1,'baseline',r,r['geometry'],exact=True)
    mid=selected[1]
    for j,delta in enumerate([-.02,-.01,-.005,-.002,0,.002,.005,.01,.02]):
        g=dict(mid['geometry']);g['Ws']+=delta;g['Ls2']=.55+2*g['Ws'];g['Ls3']=1.8+g['Ws']
        add(f'S1_WS_{j:02d}',1,'width_perturbation',mid,g,exact=True)
    # Stage2: 37 new designs, no duplicate archive a1.4/a1.8 or g.55 jobs.
    for r in selected:
        wm,ws=r['geometry']['Wm'],r['geometry']['Ws']
        add('S2_E0_'+r['family'],2,'E0',r,straight(wm,ws),'uniform_control',uniform=True)
        for a in (.6,1.,2.2,2.6,3.):
            add(f'S2_E1_{r["family"]}_a{a:.1f}',2,'E1',r,chain.lengths(wm,ws,a,.55))
        for gap in (.25,.4,.8,1.2,2.):
            add(f'S2_E2_{r["family"]}_g{gap:.2f}',2,'E2',r,chain.lengths(wm,ws,1.8,gap))
    for j,(a,gap) in enumerate([(1.,.25),(1.,1.2),(2.6,.25),(2.6,1.2)]):
        add(f'S2_E3_{j:02d}',2,'E3',mid,chain.lengths(mid['geometry']['Wm'],mid['geometry']['Ws'],a,gap))
    # Stage3: 10 equal-ripple initial guesses and 10 conditional lossless jobs.
    ptarget=brentq(lambda p:chain.ripple_db(p)+21,1.01,3)
    for r in selected[:2]:
        wm=r['geometry']['Wm']
        for j,a in enumerate((0,.6,1.4,2.2,3.)):
            if a==0:g=straight(wm,r['geometry']['Ws'])
            else:
                def fun(ws):
                    n=chain.nominal(wm,ws);n1,n2=chain.ratios(n['Zm_ohm'],n['Zs_ohm'],a)
                    return n['P']*n1*n1*n2*n2-ptarget
                ws=brentq(fun,.1,1.)
                g=chain.lengths(wm,ws,a,.55)
            id=f'S3_EQ_{r["family"]}_{j:02d}'
            add(id,3,'equal_ripple',r,g,'uniform_control' if a==0 else 'planned_tuning',uniform=a==0)
            add(id+'_LOSSLESS',3,'lossless_control',r,g,'lossless_control',parent=id,uniform=a==0)
    # Stage4: reserved exact combinations; do NOT claim a trained gap model exists now.
    combos=[(0,2.,.70),(1,.8,.40),(2,2.4,.90),(0,1.2,.65),(1,2.8,.95),(2,1.6,1.50),(0,2.4,.35),(2,.8,1.)]
    for j,(i,a,gap) in enumerate(combos):
        r=selected[i]
        add(f'S4_RESERVED_{j:02d}',4,'prospective_reservation',r,
            chain.lengths(r['geometry']['Wm'],r['geometry']['Ws'],a,gap),'prospective_reserved')
    assert len({r['id'] for r in records})==len(records)==77
    manifest=dict(schema_version='phase0-proposals-v2',solver_authorized=False,new_Analyze_requests=0,
          status='OFFLINE_PRIOR_FREEZE_ONLY; not launch-ready; no final prospective freeze yet',
          known_gap_training_levels_mm=[.55],coefficients=chain.COEFFICIENTS,source_hashes=hashes,
          stage4_rules='Reserved points stay out of stage2/3; freeze post-stage3 model before first solve. A failed prospective result keeps its original identity forever.',
          proposal_counts={str(k):sum(r['stage']==k for r in records) for k in (1,2,3,4)},
          archived_anchor_cases=[r['case'] for r in rows if r['source']=='original48' and r['family'] in {v['family'] for v in selected}],
          max_design_attempts_before_exclusions=sum(r['max_geometry_attempts'] for r in records),
          analyze_budget='NOT APPROVED; design attempts are not Analyze calls. New per-run stage budget must be approved separately; never borrow old batch budget.',
          designs=records)
    write(out/'predictions_frozen.json',manifest)
    flat=[]
    for r in records:
        check=r['screen'] or {}
        flat.append(dict(id=r['id'],stage=r['stage'],experiment=r['experiment'],family=r['family'],
                         data_role=r['data_role'],topology=r['topology'],**r['geometry_mm'],
                         a_mm=check.get('a_mm'),g_mm=check.get('g_mm'),rho=check.get('rho_parameter_sum'),
                         tip_microstrip_x_mm=check.get('arm_tip_to_microstrip_x_mm'),
                         tip_tip_x_mm=check.get('arm_tip_to_arm_tip_x_mm'),screen_pass=check.get('screen_pass'),
                         release_status=r['release_status'],reasons='; '.join(r['blocking_reasons']),
                         max_geometry_attempts=r['max_geometry_attempts']))
    csvwrite(out/'design_list.csv',flat)
    write(out/'EXCLUSIONS.json',[r for r in records if r['release_status']=='excluded_from_proposed_runlist'])
    write(out/'FREEZE_HASHES.json',dict(source_hashes=hashes,
          artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()},
          change_policy='Any edit requires a new revision and new hash; this manifest is not a solver authorization.'))
    print('counts',manifest['proposal_counts'],'max design attempts',manifest['max_design_attempts_before_exclusions'])
    print('baselines',[(r['family'],r['R']) for r in selected])
    print('excluded',[r['id'] for r in records if r['release_status']=='excluded_from_proposed_runlist'])


if __name__=='__main__':main()
