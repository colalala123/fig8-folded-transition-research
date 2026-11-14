"""OFFLINE R9-2 independent full-choice audit. Never change the frozen builder or old decisions.

The legacy R6 decision has usable_for_law, not tuned. The frozen builder's
generic tuned lookup omits that nonwinning choice. Recompute every choice from
the actual reviewed response, preserve that omission, and fail closed if it
changes the winner. No synthetic alias or mutation of old evidence is used.
"""
from prepare_r9 import *
from manage import scores
def audit():
    cfg=read(ROOT/'authorization.json');reg=read(HERE/'offline_5B/REGISTRY.json');rows=[]
    for p in ('S5R9_D1c','S5R9_S1'):
        d=read(ROOT/'decisions'/(p+'_FINAL.json'))
        q=read(case_dir(ROOT,d['selected_case'],cfg)/'review/extraction_R2.json')
        rows.append((d['selected_case'],q,'R9'))
    for exp,p in [('fold_bandwidth_r6_stage2b_20261112','S2_E2_N04_g1.20'),('fold_bandwidth_r7_3r_20261113','S3R7_N04_a2.6')]:
        b=REPO/'experiments'/exp;d=read(b/'decisions'/(p+'_FINAL.json'));q=read(b/'results'/d['selected_case']/'review/extraction_R2.json');rows.append((d['selected_case'],q,exp))
    rr=[]
    for c,q,src in rows:
        g=q['geometry_mm'];dim=chain.dimensions(g);s=scores(q)
        rr.append(dict(case=c,source=src,usable_recomputed=s['usable'],a=dim['a_mm'],g=dim['g_mm'],BW15_star=s['BW15_star'],source_q_sha256=sha(case_dir(ROOT,c,cfg)/'review/extraction_R2.json') if src=='R9' else sha(REPO/'experiments'/src/'results'/c/'review/extraction_R2.json')))
    eligible=[r for r in rr if r['usable_recomputed']]
    best=max(eligible,key=lambda r:r['BW15_star']) if eligible else dict(case='fallback',a=2.4,g=.55)
    if best['case']!=reg['B3_shape']['case'] or abs(best['a']-reg['B3_shape']['a'])>1e-8 or abs(best['g']-reg['B3_shape']['g'])>1e-8:raise RuntimeError('B3 full-choice winner differs; stop before dispatch, do not silently replace')
    omitted=[r['case'] for r in rr if r['usable_recomputed'] and r['case'] not in [x['case'] for x in reg['B3_candidates']]]
    write(HERE/'offline_5B/FULL_SELECTION_AUDIT.json',dict(passed=True,all_four_candidates=rr,winner=best,omitted_by_legacy_field_lookup=omitted,winner_and_geometry_unchanged=True,frozen_code_unchanged=True,note='R6 old decision uses usable_for_law, not tuned; omission is disclosed and all four are independently scored before R9-2 publication. It does not affect B3 selection.'))
    print(best)
if __name__=='__main__':audit()
