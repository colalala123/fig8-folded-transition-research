"""R3-2 fixed tuning criteria and within-family ripple normalization."""
import math
import numpy as np


def tuned(q):
    if q.get('schema_version')!='R2-extracted-run-v1':raise ValueError('R2 extraction required')
    shape=q['shape'];peaks=shape.get('inner_peaks',[]);center=shape.get('central_valley_GHz')
    good=len(peaks)==2 and center is not None and math.isfinite(center)
    values=[p.get('S11_dB') for p in peaks]
    good=good and all(isinstance(v,(int,float)) and math.isfinite(v) for v in values)
    if not good:return dict(tuned=False,mean_inner_peak_dB=None,reasons=['missing_or_invalid_shape'])
    mean=float(np.mean(values));gap=abs(values[0]-values[1]);checks=dict(
        both_peaks_at_or_below_minus20=max(values)<=-20.,mean_at_or_above_minus20p6=mean>=-20.6,
        center_within_30MHz=abs(center-6.72)<=.03000000001,peak_gap_within_0p5dB=gap<=.5,
        three_valley_shape=bool(shape.get('shape_valid')))
    return dict(tuned=all(checks.values()),mean_inner_peak_dB=mean,peak_difference_dB=gap,checks=checks,
                reasons=[k for k,v in checks.items() if not v])


def slope_for_family(family, final_records):
    """One final selected run per design, same family; never pool families.

    OLS with intercept, >=2 distinct finite ripple values, rank 2. Report the
    sample count and limitations. Fall back ONLY if that fit cannot be formed.
    These are descriptive same-family slopes; a varies and can confound them.
    """
    selected=[r for r in final_records if r['family']==family]
    if len({r['design_id'] for r in selected})!=len(selected):raise ValueError('Duplicate final design records; select final attempts explicitly')
    pairs=[];used=[]
    for r in selected:
        q=r['extraction'];t=tuned(q);b=q['bandwidths']['BW20']
        bw=b['BW_GHz']
        if t['tuned'] and bw is not None and math.isfinite(bw) and not b.get('edge_censored',False):
            pairs.append([t['mean_inner_peak_dB'],bw]);used.append(r['design_id'])
    if len(pairs)>=2:
        v=np.array(pairs);x=v[:,0]-v[:,0].mean();X=np.c_[np.ones(len(x)),x]
        coef,_,rank,_=np.linalg.lstsq(X,v[:,1],rcond=None)
        if rank==2:
            residual=v[:,1]-X@coef
            return dict(source='stage3_same_family_OLS',slope_GHz_per_dB=float(coef[1]),n=len(pairs),used_design_ids=used,
                        intercept_at_mean_ripple_GHz=float(coef[0]),mean_ripple_dB=float(v[:,0].mean()),
                        residual_RMS_GHz=float(np.sqrt(np.mean(residual**2))),degrees_of_freedom=len(pairs)-2,
                        caveat='Descriptive within-family fit; small sample and varying a can confound ripple slope; not causal.')
    return dict(source='prior_150MHz_per_dB',slope_GHz_per_dB=.150,n=len(pairs),used_design_ids=used,
                reason='insufficient distinct finite usable same-family ripple values for rank-2 regression')


def evaluate(q,family,final_records=()):
    criteria=tuned(q);b=q['bandwidths']['BW20'];actual=b['BW_GHz']
    slope=slope_for_family(family,final_records)
    mean=criteria['mean_inner_peak_dB']
    valid=actual is not None and mean is not None and math.isfinite(actual) and not b.get('edge_censored',False)
    normalized=actual+slope['slope_GHz_per_dB']*(-20.3-mean) if valid else None
    return dict(schema_version='R3-stage3-metrics-v1',**criteria,family=family,actual_BW20_GHz=actual,
                normalized_BW20_at_minus20p3_GHz=normalized,normalization_target_dB=-20.3,slope=slope,
                usable_in_stage3_conclusion=criteria['tuned'] and normalized is not None,
                normalization_formula='BW_actual + slope*(-20.3 - mean_inner_peak_dB)',
                edge_censored=b.get('edge_censored',False))
