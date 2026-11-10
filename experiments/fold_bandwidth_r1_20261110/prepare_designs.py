"""R1-1/R1-5 offline registry and slot boxes. Never releases solver work."""
import argparse
import copy
import numpy as np
from scipy.optimize import brentq
import chain
from common import HERE, REPO, OLD, read, write, sha, csvwrite
from geometry import slot_boxes


def build():
    old = read(OLD/'freeze/predictions_frozen.json')
    records = copy.deepcopy(old['designs'])
    ptarget = brentq(lambda p: chain.ripple_db(p)+21, 1.01, 3)
    for r in records:
        r['batch'] = ('1a' if r['experiment'] == 'baseline' else '1b') if r['stage'] == 1 else (
            ('2a' if r['family'] == 'N14' else '2b') if r['stage'] == 2 else str(r['stage']))
        g = r['geometry_mm']
        if r['topology'] == 'straight_control':
            if r['stage'] == 3:
                wm = g['Wm']
                def fun(ws):
                    n = chain.nominal(wm, ws)
                    n1, n2 = chain.ratios(n['Zm_ohm'], n['Zs_ohm'], 0)
                    return n['P']*n1*n1*n2*n2-ptarget
                ws = round(brentq(fun, .1, 1), 3)
            else:
                ws = g['Ws']
            g = chain.straight(g['Wm'], ws)
            r['geometry_mm'] = g
            r['straight_prior'] = dict(pure_half_wave_mm=chain.wave_length(ws, 6.588, False),
                                       correction_mm=chain.corrections(g['Wm'], ws, 0)[1],
                                       target_inner_peak_dB=-21 if r['stage'] == 3 else None,
                                       label='a=0 extrapolation; not calibrated')
        r['boundary_half_x_mm'] = 15.
        r['material_role'] = 'PEC_tandelta0' if r['experiment'] == 'lossless_control' else 'archived_lossy'
        r['first_attempt_role'] = 'prospective_test' if r['batch'] == '2b' or r['stage'] == 4 else r['data_role']
        r['subsequent_attempt_role'] = 'tuned_data' if r['stage'] in (2, 3) and not r['parent'] else None
        r['future_prospective_freeze_required'] = r['batch'] == '2b' or r['stage'] == 4
        r['first_attempt_role_immutable'] = True
        r['initial_prediction_stage'] = 'R1_prior_not_prospective_prediction'
        r['rounding'] = 'Fixed archived widths exact; new Lm/Ls1 and stage3 new Ws rounded to .001mm; dependent a/g exact; exact stage1 replay exception.'
        # Stale R0 fields must not masquerade as an R1 initial guess.
        r.pop('unrounded_initial_geometry_mm', None)
        r.pop('max_geometry_attempts', None)
        r['max_Analyze_requests_proposed'] = 3 if r['stage'] in (2, 3) and not r['parent'] else 1
    byid = {r['id']: r for r in records}
    # Boundary comparisons reuse their parent's geometry/material. The E0
    # parent's final lengths are still unknown: these are conditional priors.
    for label, parent in [('STRAIGHT', 'S2_E0_N14'), ('A18', 'S1_BASE_N14')]:
        r = copy.deepcopy(byid[parent])
        r.update(id='S3_BOUNDARY_N14_'+label, stage=3, batch='3', experiment='boundary_control',
                 data_role='boundary_control', first_attempt_role='boundary_control',
                 subsequent_attempt_role=None, parent=parent, boundary_half_x_mm=20.,
                 future_prospective_freeze_required=False, max_Analyze_requests_proposed=1,
                 boundary_change='substrate AND airbox x half-width 15 -> 20mm; all else identical to parent')
        r['future_run_directory'] = ('uniform_control/' if r['topology']=='straight_control' else 'runs/')+r['id']+'/attempt_001'
        records.append(r)
    freq = np.arange(.01, 15.0001, .01)
    for r in records:
        g = r['geometry_mm']
        r['screen'] = chain.geometry_screen(g, r['topology'], r['boundary_half_x_mm'])
        c = chain.forward(g, r['topology'])
        s, t = chain.circuit(freq, *[c[k] for k in ('zm_eff', 'zs_eff', 'fm_GHz', 'fs_GHz')])
        r['prediction'] = dict(parameters=c, lossless_circuit_bandwidths=chain.bands(freq, s, t),
                               equal_frequency_inner_peak_dB=chain.ripple_db(c['P_eff']),
                               BW_S21_HFSS_prediction_GHz=None,
                               caveat='Uncalibrated prior; g extra effect set to zero. Ideal circuit S21 is not a lossy-HFSS prediction.')
        r['blocking_reasons'] = ['human_batch_authorization_required', 'native_generated_CAD_box_comparison_required',
                                 'solver_resource_and_Analyze_budget_preflight_required']
        if r['parent']:
            r['prediction']['conditional_on_parent_final_geometry'] = True
            r['blocking_reasons'].append('rebind_and_freeze_parent_final_geometry_before_release')
        if r['future_prospective_freeze_required']:
            r['blocking_reasons'].append('post_2a_model_freeze_required' if r['batch']=='2b' else 'post_stage2_3_model_freeze_required')
        r['release_status'] = 'review_only_not_authorized'
        r['solver_authorized'] = False
    return records


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    records = build()
    budget = {'1a':3, '1b':9, '2a':45, '2b':66, '3':42, '4':8, '5':12}
    source = [HERE/p for p in ('chain.py', 'geometry.py', 'prepare_designs.py', 'common.py')]
    source += [OLD/'chain.py', OLD/'freeze/predictions_frozen.json',
               REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R1.md', REPO/'analysis/line_models.py',
               REPO/'model/DATASET.json', REPO/'model/dataset.npz', REPO/'hfss/INV01_A14.aedt']
    hashes = {p.relative_to(REPO).as_posix(): sha(p) for p in source}
    core = records[:77]
    summary = dict(schema_version='R1-offline-prior-v1', solver_authorized=False,
                   new_Analyze_requests=0, hook_messages=0, source_hashes=hashes,
                   coefficients=chain.COEFFICIENTS, prior_only=True,
                   counts=dict(original_registry=77, original_folded=70,
                               original_folded_pass=sum(r['topology']=='folded' and r['screen']['screen_pass'] for r in core),
                               boundary_controls=2, total=len(records),
                               by_batch={b:sum(r['batch']==b for r in records) for b in budget}),
                   proposed_batch_Analyze_caps=budget, proposed_total_Analyze_cap=sum(budget.values()),
                   stage5_not_registered_yet=True, budgets_authorized=False,
                   prospective_policy='2b first attempts retain prospective identity forever; refreeze after 2a. Stage4 refreeze after stages2/3. R1 prior is NOT that freeze.',
                   designs=records)
    write(out/'predictions_frozen.json', summary)
    flat = [dict(id=r['id'], batch=r['batch'], family=r['family'], topology=r['topology'],
                 first_attempt_role=r['first_attempt_role'], parent=r['parent'], **r['geometry_mm'],
                 **r['screen'], solver_authorized=False) for r in records]
    csvwrite(out/'design_list.csv', flat)
    boxes = [dict(id=r['id'], topology=r['topology'], geometry_mm=r['geometry_mm'],
                  conditional_parent=r['parent'], board_half_x_mm=r['boundary_half_x_mm'],
                  boxes=slot_boxes(r['geometry_mm'], r['topology'])) for r in records]
    write(out/'SLOT_BOXES.json', boxes)
    csvwrite(out/'slot_boxes.csv', [dict(id=r['id'], name=b['name'], **b['parameters_mm']) for r in boxes for b in r['boxes']])
    write(out/'EXCLUSIONS.json', [r['id'] for r in records if not r['screen']['screen_pass']])
    write(out/'FREEZE_HASHES.json', dict(source_hashes=hashes, artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}))
    print(summary['counts'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=__import__('pathlib').Path, required=True)
    main(ap.parse_args().out)
