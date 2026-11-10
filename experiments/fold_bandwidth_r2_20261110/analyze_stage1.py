"""R2 reuse of R1-4 fixed pre-data stage1 analysis. Offline; no adjustable CLI thresholds.

Input: {archive:[3 envelopes], baseline:[3 envelopes], perturbations:[9 envelopes]}.
Envelope: id, geometry_mm, metrics; new-run envelopes additionally mesh_cells,
MaxDeltaS, sweep_low_GHz, sweep_high_GHz. No automatic dispatch follows a pass.
"""
import argparse
from pathlib import Path
import numpy as np
import chain
from common import HERE, R1, read, write, sha


def metrics_from_extraction(q):
    if q.get('schema_version')!='R2-extracted-run-v1':
        raise ValueError('Re-extract with R2 before stage1 metric conversion; do not mix bandwidth definitions')
    shape, p, b = q['shape'], q['circuit']['parameters'], q['bandwidths']
    peaks = shape.get('inner_peaks', [])
    n = chain.nominal(q['geometry_mm']['Wm'],q['geometry_mm']['Ws'])
    return dict(inner_peak_low_dB=peaks[0]['S11_dB'] if len(peaks)==2 else None,
                inner_peak_high_dB=peaks[1]['S11_dB'] if len(peaks)==2 else None,
                inner_peak_mean_dB=q['inner_peak_mean_dB'],central_valley_GHz=shape.get('central_valley_GHz'),
                **{key+'_GHz':b[key]['BW_GHz'] for key in ('BW15','BW20','BW_S21','BW_joint')},
                N1=float(np.sqrt(p['zm_eff']/(n['Zm_ohm']/50))),
                N2=float(np.sqrt(p['zs_eff']/(n['Zs_ohm']/50))),
                P_eff=p['zm_eff']*p['zs_eff'],R_eff=p['zm_eff']/p['zs_eff'],
                fm_GHz=p['fm_GHz'],fs_GHz=p['fs_GHz'])


def finite(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and np.isfinite(v)


def indexed(rows, ids):
    if len(rows)!=len(ids) or {r['id'] for r in rows}!=set(ids):
        raise ValueError('Missing, duplicate or unexpected run ids')
    return {r['id']:r for r in rows}


def analyze(data):
    path=R1/'STAGE1_CRITERIA.json'; c=read(path)
    frozen={r['id']:r for r in read(R1/'freeze_r1/predictions_frozen.json')['designs']}
    bases=c['baseline_ids'];steps=[f'S1_WS_{j:02d}' for j in range(9)]
    old=indexed(data['archive'],bases);new=indexed(data['baseline'],bases)
    stair=indexed(data['perturbations'],steps)
    numerical=[]
    for id,r in {**new,**stair}.items():
        expected=frozen[id]['geometry_mm']
        if set(r['geometry_mm'])!=set(expected) or any(not finite(r['geometry_mm'][k]) or abs(r['geometry_mm'][k]-expected[k])>1e-10 for k in expected):
            raise ValueError('Input geometry not frozen stage1 geometry: '+id)
        reasons=[]
        mesh=r.get('mesh_cells')
        if not isinstance(mesh,int) or isinstance(mesh,bool) or not c['mesh_cells_min']<=mesh<=c['mesh_cells_max']:
            reasons.append('mesh_out_of_range_or_unknown')
        for key in ('MaxDeltaS','sweep_low_GHz','sweep_high_GHz'):
            if not finite(r.get(key)) or abs(r[key]-c[key])>1e-12:reasons.append(key+'_mismatch_or_unknown')
        numerical.append(dict(id=id,passed=not reasons,reasons=reasons))
    comparisons=[]
    for id in bases:
        # The archive comparator must be the same geometry, not merely family.
        if old[id]['geometry_mm'] != frozen[id]['geometry_mm']:
            raise ValueError('Wrong archive baseline geometry: '+id)
        metrics={}
        for k,limit in c['baseline_max_abs_difference'].items():
            a,b=old[id]['metrics'].get(k),new[id]['metrics'].get(k)
            delta=b-a if finite(a) and finite(b) else None
            metrics[k]=dict(delta=delta,limit=limit,passed=delta is not None and abs(delta)<=limit+1e-12)
        comparisons.append(dict(id=id,metrics=metrics,passed=all(v['passed'] for v in metrics.values())))
    x=np.array(c['width_delta_mm'])
    noises={}; determinism={}
    for key in c['noise_metrics']:
        values=[stair[id]['metrics'].get(key) for id in steps]
        if not all(finite(v) for v in values):
            noises[key]=dict(available=False,reason='one or more metric samples null/missing; no imputation')
        else:
            y=np.array(values); lin=np.polynomial.polynomial.polyfit(x,y,1);quad=np.polynomial.polynomial.polyfit(x,y,2)
            rlin=y-np.polynomial.polynomial.polyval(x,lin);rquad=y-np.polynomial.polynomial.polyval(x,quad)
            corrected=float(y[5]-y[3]-lin[1]*(x[5]-x[3]))
            corrected_q=float(y[5]-y[3]-quad[1]*(x[5]-x[3]))
            noises[key]=dict(available=True,linear_coefficients=lin.tolist(),quadratic_coefficients=quad.tolist(),
                             linear_residuals=rlin.tolist(),quadratic_residuals=rquad.tolist(),
                             linear_residual_sd=float(np.sqrt(rlin@rlin/c['linear_residual_dof'])),
                             quadratic_residual_sd=float(np.sqrt(rquad@rquad/c['quadratic_residual_dof'])),
                             small_pair_raw_difference=float(y[5]-y[3]),
                             small_pair_slope_corrected_difference=corrected,
                             small_pair_quadratic_slope_corrected_difference=corrected_q,
                             small_pair_absolute_difference=abs(corrected))
        a,b=new['S1_BASE_N14']['metrics'].get(key),stair['S1_WS_04']['metrics'].get(key)
        determinism[key]=b-a if finite(a) and finite(b) else None
    baseline_ok=all(v['passed'] for v in comparisons)
    numerical_ok=all(v['passed'] for v in numerical)
    required_noise=all(noises[k]['available'] for k in c['baseline_max_abs_difference'])
    return dict(schema_version='R2-stage1-analysis-v1',bandwidth_semantics='R2 main passband for BW15/BW20/BW_joint; R1 null policy unchanged',
                criteria_sha256=sha(path),criteria=c,baseline_comparisons=comparisons,numerical_checks=numerical,
                perturbation_noise=noises,zero_repeat_minus_baseline=determinism,
                baseline_comparability_passed=baseline_ok,numerical_checks_passed=numerical_ok,
                offline_ready_for_review=baseline_ok and numerical_ok and required_noise,
                noise_threshold_added=False,solver_authorized=False,new_Analyze_requests=0,hook_messages=0,
                interpretation='Three separate reports: baseline comparability, linear/quadratic residual SD, and corrected tiny-pair difference. Not pooled into one noise estimate. No noise cutoff invented; no dispatch on pass.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();result=analyze(read(args.input));result['input_sha256']=sha(args.input);write(args.out,result)
