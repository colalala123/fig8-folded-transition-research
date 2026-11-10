"""R2 offline single-run extractor. Input NPZ: f_GHz, S[n,4,4], propagating[n,4].

Modes in order [port1:1,port1:2,port2:1,port2:2], S[output,input].
Full-mode power requires explicit power-wave normalization and propagation flags.
Archive replay uses ONLY the two actual stored fundamental responses; missing
mode channels stay missing, never padded with zero or invented.
"""
import argparse
import csv
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
import chain
from common import HERE, OLD, R1, REPO, load, read, write, csvwrite, sha

legacy = load('r1_legacy_comparator', REPO/'experiments/fold_bandwidth_20261110/offline_fold_analysis.py')
from lib import assess, TARGET


def basin_audit(starts):
    valid=[i for i,s in enumerate(starts) if s['success'] and np.isfinite(s['cost'])]
    if not valid:raise ValueError('No converged starts')
    order=sorted(valid,key=lambda i:starts[i]['cost']);best=starts[order[0]]
    bp=np.asarray(best['parameters']);bc=best['cost']
    if not np.all(np.isfinite(bp)) or np.any(bp<=0):raise ValueError('Positive finite best parameters required')
    representatives=[];other=[]
    for i in order:
        s=starts[i];p=np.asarray(s['parameters'])
        relative=float(np.max(abs(p-bp)/abs(bp)))
        s['max_relative_difference_to_best']=relative
        s['distinct_from_best']=relative>.01
        s['cost_ratio_to_best']=s['cost']/bc if bc>0 else (1. if s['cost']==0 else None)
        s['cost_ratio_infinite']=bc==0 and s['cost']>0
        if s['distinct_from_best']:other.append(i)
        group=next((j for j,r in enumerate(representatives) if np.max(abs(p-r)/abs(r))<=.01),None)
        if group is None:
            group=len(representatives);representatives.append(p)
        s['basin_id']=f'basin_{group:02d}'
    for i,s in enumerate(starts):
        if i not in valid:
            s.update(basin_id=None,distinct_from_best=None,max_relative_difference_to_best=None,
                     cost_ratio_to_best=None,cost_ratio_infinite=False)
    finite_ratios=[starts[i]['cost_ratio_to_best'] for i in other if starts[i]['cost_ratio_to_best'] is not None]
    return dict(best_start=order[0],extraction_nonunique=any(starts[i]['cost']<=bc*1.05 for i in other),
                distinct_other_start_count=len(other),minimum_other_basin_cost_ratio=min(finite_ratios) if finite_ratios else None,
                minimum_other_basin_ratio_infinite=bool(other) and not finite_ratios,
                basin_count=len(representatives),
                uniqueness_rule='R2: any parameter relative-to-best difference >1%; another solution cost <=1.05*best',
                basin_label_rule='cost-ordered representatives, max componentwise relative difference <=1%; descriptive labels; decision always compares each start directly with best')


def grid(f, s):
    f, s = np.asarray(f, float), np.asarray(s, complex)
    if f.ndim != 1 or len(f)<8 or not np.isfinite(f).all() or not np.all(np.diff(f)>0):
        raise ValueError('Finite strictly increasing frequency grid, at least 8 points required')
    if s.shape != (len(f), 2) or not np.isfinite(s).all():
        raise ValueError('Finite paired fundamental responses required')
    if f[0]>2 or f[-1]<11.5:
        raise ValueError('Extraction requires coverage of 2-11.5GHz')
    return f, s


def fit_circuit(f, s11, g):
    n = chain.nominal(g['Wm'], g['Ws'])
    win = (f>=2)&(f<=11.5)
    fr, target = f[win], abs(s11[win])
    bounds = ([.3,.5,4,4], [3,6,10,10])
    objective = lambda p: abs(chain.circuit(fr, *p)[0])-target
    # Exact original solver settings kept as a named retrospective comparator.
    first = least_squares(objective, [n['Zm_ohm']/50,n['Zs_ohm']/50,6.72,6.72], bounds=bounds)
    starts = [[n['Zm_ohm']/50,n['Zs_ohm']/50,6.72,6.72],first.x.tolist(),
              [.7,2.2,5.8,7.5],[1.3,1.3,7.5,5.8],[1.7,4.,8.2,8.2],[.5,3.5,5.,5.]]
    sols = [least_squares(objective, p, bounds=bounds, max_nfev=2000,
                          ftol=1e-10, xtol=1e-10, gtol=1e-10) for p in starts]
    valid = [i for i,q in enumerate(sols) if q.success and np.isfinite(q.cost)]
    if not valid:
        raise ValueError('No converged circuit fit')
    order = sorted(valid, key=lambda i: sols[i].cost)
    best = sols[order[0]]
    near = [i for i in order if sols[i].cost <= 1.05*best.cost]
    start_records=[dict(initial=list(map(float,p)),success=bool(q.success),cost=float(q.cost),
                        nfev=q.nfev,parameters=q.x.tolist(),
                        start_kind='refinement' if i==1 else 'independent',
                        independent_start_id=None if i==1 else f'seed_{i}',
                        initialization_source='legacy first-fit converged parameters' if i==1 else 'fixed a-priori seed; nominal geometry seed for index0')
                   for i,(p,q) in enumerate(zip(starts,sols))]
    audit=basin_audit(start_records)
    return dict(parameters=dict(zip(('zm_eff','zs_eff','fm_GHz','fs_GHz'), map(float,best.x))),
                rms_linear=float(np.sqrt(2*best.cost/len(fr))), **audit,
                independent_start_count=5,refinement_start_count=1,
                initialization_policy='Five independent seeds; legacy seed fit may additionally initialize one refinement and is not a sixth independent seed.',
                near_best_start_indices=near,
                near_best_parameter_ptp=np.ptp([sols[i].x for i in near], axis=0).tolist(),
                global_uniqueness_proven=False, fit_target='abs(S11),2-11.5GHz; phase and S21 not fitted',
                starts=start_records,
                legacy_single_start=dict(parameters=first.x.tolist(), rms_linear=float(np.sqrt(np.mean(first.fun**2))),
                                         success=bool(first.success)))


def power_metrics(f, fundamental, S=None, propagating=None, normalization=None):
    base_unaccounted = 1-np.sum(abs(fundamental)**2, axis=1)
    result = dict(f_GHz=f.tolist(), fundamental_unaccounted=base_unaccounted.tolist(),
                  all_mode_remaining=None, all_mode_raw_coefficient_remainder=None,
                  mode2_propagating=None, incident_mode_propagating=None,
                  interpretation='Fundamental unaccounted includes mode conversion, loss, radiation and numerical error; not radiation alone.')
    if S is None:
        result['missing_reason'] = 'archive has only S11/S21 fundamentals'
        return result
    S = np.asarray(S, complex)
    p = np.asarray(propagating)
    if S.shape != (len(f),4,4) or not np.isfinite(S).all():
        raise ValueError('Finite full 4x4 modal S required')
    if p.shape != (len(f),4) or p.dtype != np.dtype(bool):
        raise ValueError('Explicit boolean propagation status for every mode/frequency required')
    if normalization != 'power_waves':
        raise ValueError('Do not interpret voltage/pseudo-wave/unknown coefficients as power')
    if not np.allclose(S[:,[0,2],0], fundamental, atol=0, rtol=0):
        raise ValueError('Fundamental indexing disagrees with full S')
    raw = 1-np.sum(abs(S[:,:,0])**2, axis=1)
    remaining = 1-np.sum(abs(S[:,:,0])**2*p, axis=1)
    result.update(all_mode_raw_coefficient_remainder=raw.tolist(),
                  all_mode_remaining=[float(x) if valid else None for x,valid in zip(remaining,p[:,0])],
                  mode2_propagating=dict(port1=p[:,1].tolist(), port2=p[:,3].tolist()),
                  incident_mode_propagating=p[:,0].tolist(),
                  mode_order=['1:1','1:2','2:1','2:2'], normalization=normalization,
                  evanescent_policy='Nonpropagating channels carry no outgoing real power; raw squared-coefficient remainder is also retained but is NOT physical power. Nonpropagating incident rows are null.',
                  interpretation='All-mode remainder: dissipation + radiation + numerical error; only in a verified lossless run is it radiation + numerical error. Not clipped to [0,1].')
    return result


def extract(f, fundamental, metadata, S=None, propagating=None, normalization=None):
    f, z = grid(f, fundamental)
    g = metadata['geometry']
    fit = fit_circuit(f, z[:,0], g)
    score = assess(f, z, TARGET)
    peak = score.get('inner_peaks', [])
    band = chain.bands(f, z[:,0], z[:,1],shape=score)
    return dict(schema_version='R2-extracted-run-v1', case=metadata['case'], geometry_mm=g,
                bandwidth_definition='R2 section2.1: central-valley component must include both inner peaks; external components separate',
                uniqueness_definition='R2 section2.2: >1% relative parameter difference AND <=1.05 cost ratio; >=5 independent seeds',
                evidence='offline extraction of supplied data; not solver/visual certification',
                circuit=fit, bandwidths=band, shape=score,
                inner_peak_mean_dB=float(np.mean([p['S11_dB'] for p in peak])) if peak else None,
                power=power_metrics(f,z,S,propagating,normalization),
                new_Analyze_requests=0, hook_messages=0)


def legacy_row(f, z, r, q):
    """R0-compatible columns, explicitly not the new R1 bandwidth/fit semantics."""
    g = r['geometry']
    zm,zs,fm,fs = q['circuit']['legacy_single_start']['parameters']
    n = chain.nominal(g['Wm'],g['Ws'])
    zm0,zs0 = n['Zm_ohm']/50,n['Zs_ohm']/50
    db = 20*np.log10(abs(z))
    l = g['Ls1']+2*g['Ls2']+2*g['Ls3']
    fold=2*(g['Ls2']+g['Ls3']); half=chain.wave_length(g['Ws'],fs,False)
    lo15,hi15 = legacy.band_at(f,db[:,0],-15)
    lo20,hi20 = legacy.band_at(f,db[:,0],-20)
    tlo,thi = legacy.band_at(f,-db[:,1],2)
    rem = 1-np.sum(abs(z)**2,axis=1)
    row = dict(case=r['case'],family=r['family'],source=r['source'],a_mm=round(r['a'],6),
               g_mm=round(g['Ls2']-2*g['Ws'],6),**g,mesh=r['mesh'],Lpath=l,rho=fold/l,
               eta=g['Ls2']/(g['Ls2']+g['Ls3']),zm_nominal=zm0,zs_nominal=zs0,
               zm_eff=zm,zs_eff=zs,fm_GHz=fm,fs_GHz=fs,
               fit_rms_linear=q['circuit']['legacy_single_start']['rms_linear'],
               N1=np.sqrt(zm/zm0),N2=np.sqrt(zs/zs0),P_eff=zm*zs,R_eff=zm/zs,
               slot_half_wave_mm=half,slot_length_correction_mm=half-l,path_phase_deg_at_fs=180*l/half,
               inner_peak_mean_dB=q['inner_peak_mean_dB'],bw_S11_15dB=hi15-lo15,
               lo_S11_15dB=lo15,hi_S11_15dB=hi15,bw_S11_20dB=hi20-lo20,
               bw_S21_2dB=thi-tlo,hi_S21_2dB=thi,
               bw15_circuit=legacy.bw_closed(zm*zs,zm,(fm+fs)/2,-15),
               bw20_circuit=legacy.bw_closed(zm*zs,zm,(fm+fs)/2,-20),
               residual_power_6p72=float(np.interp(6.72,f,rem)),
               residual_power_8p5=float(np.interp(8.5,f,rem)),residual_power_9p5=float(np.interp(9.5,f,rem)),
               min_S21_dB=q['shape']['min_S21_dB'])
    return row


def replay(out):
    out.mkdir(parents=True,exist_ok=False)
    data=np.load(REPO/'model/dataset.npz',allow_pickle=False)
    rows=read(REPO/'model/DATASET.json')['rows'];f=data['f']
    old=list(csv.DictReader((OLD/'reproduction/fold_table.csv').open(encoding='utf8')))
    comparisons=[]; table=[]; details=[]; diffs=[]; fitdiff=[]
    reviewer=read(REPO/'experiments/fold_bandwidth_review_r2_20261110/out/REVIEW_CHECKS.json')
    ref={r['case']:r for r in reviewer['rows']};checks=[];newtable=[]
    for i,r in enumerate(rows):
        q=extract(f,data['Z'][i],r)
        row=legacy_row(f,data['Z'][i],r,q);table.append(row)
        # Avoid copying 80 redundant full grids: retain sampled fundamental
        # power plus source hash. No full-mode power claimed for archive.
        q['power']={k:v for k,v in q['power'].items() if k not in ('f_GHz','fundamental_unaccounted')}
        q['fundamental_power_samples']={k:row[k] for k in row if k.startswith('residual_power_')}
        details.append(q)
        b=q['bandwidths']['BW20'];u=q['circuit'];rr=ref[r['case']]
        main=None if b['BW_GHz'] is None else {k:b[k] for k in ('low_GHz','high_GHz','BW_GHz')}
        check=dict(case=r['case'],main_band_matches=(main is None)==(rr['main_band'] is None),
                   nonunique_matches=u['extraction_nonunique']==rr['nonunique'],
                   other_start_count_matches=u['distinct_other_start_count']==rr['other_basins'])
        if main is not None and rr['main_band'] is not None:
            check['main_band_matches']=all(np.isclose(main[k],rr['main_band'][k],rtol=1e-9,atol=1e-12) for k in main)
        ratio=u['minimum_other_basin_cost_ratio'];ref_ratio=rr['min_cost_ratio']
        check['cost_ratio_matches']=bool(np.isclose(ratio,ref_ratio,rtol=1e-9,atol=1e-12)) if ratio is not None and ref_ratio is not None else ratio==ref_ratio
        checks.append(check)
        newtable.append(dict(case=r['case'],a_mm=r['a'],BW15_GHz=q['bandwidths']['BW15']['BW_GHz'],
                             BW20_GHz=b['BW_GHz'],BW_joint_GHz=q['bandwidths']['BW_joint']['BW_GHz'],
                             low20_GHz=b['low_GHz'],high20_GHz=b['high_GHz'],
                             full_sweep_components=b['components'],secondary_components=b['secondary_component_count'],
                             edge_censored=b['edge_censored'],main_valid=b['main_band_valid'],
                             restored=rr['r1_BW20_GHz'] is None and main is not None,
                             exclusion_reason=b['exclusion_reason'],extraction_nonunique=u['extraction_nonunique'],
                             minimum_other_basin_cost_ratio=ratio,independent_starts=u['independent_start_count']))
        for k in old[i]:
            if k in ('case','family','source'):
                if row[k]!=old[i][k]:raise AssertionError(k)
            else:
                x,y=float(row[k]),float(old[i][k]); diff=abs(x-y)
                diffs.append(diff)
                if not np.isclose(x,y,rtol=1e-7,atol=1e-8,equal_nan=True):
                    comparisons.append(dict(case=r['case'],field=k,new=x,old=y,difference=diff))
        fitdiff.append(max(abs(q['circuit']['parameters'][k]-float(old[i][k])) for k in ('zm_eff','zs_eff','fm_GHz','fs_GHz')))
    csvwrite(out/'fold_table_legacy_compatible.csv',table)
    csvwrite(out/'fold_table_r2.csv',newtable)
    write(out/'EXTRACTED_80.json',details)
    audit=dict(cases=80,numeric_comparisons=len(diffs),legacy_compatible_pass=not comparisons,
               max_abs_legacy_difference=max(diffs),mismatches=comparisons,
               max_selected_multistart_parameter_difference=max(fitdiff),
               selected_fit_not_bitwise_legacy=True,
               R2_BW20_valid_count=sum(q['bandwidths']['BW20']['BW_GHz'] is not None for q in details),
               R2_BW20_null_count=sum(q['bandwidths']['BW20']['BW_GHz'] is None for q in details),
               nonunique_flags=sum(q['circuit']['extraction_nonunique'] for q in details),
               minimum_other_basin_cost_ratio=min(q['circuit']['minimum_other_basin_cost_ratio'] for q in details),
               restored_cases=sorted(r['case'] for r in newtable if r['restored']),
               archive_full_mode_available=False,source_hashes={p.relative_to(REPO).as_posix():sha(p) for p in [REPO/'model/dataset.npz',REPO/'model/DATASET.json',OLD/'reproduction/fold_table.csv']},
               note='Legacy columns preserve original single-start/root convention ONLY for audit. Production uses R2 main-band and distinct-basin rules. Never fabricate missing modal S.')
    write(out/'REPLAY_CHECK.json',audit)
    comparison=dict(reviewer_sha256=sha(REPO/'experiments/fold_bandwidth_review_r2_20261110/out/REVIEW_CHECKS.json'),
                    tolerances=dict(rtol=1e-9,atol=1e-12),all_80_passed=all(all(v for k,v in c.items() if k!='case') for c in checks),rows=checks)
    write(out/'REVIEWER_COMPARISON.json',comparison)
    print(audit)
    if comparisons:raise AssertionError('Archive compatibility failed')
    if not comparison['all_80_passed']:raise AssertionError('R2 reviewer per-case comparison failed')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--archive-replay',action='store_true')
    ap.add_argument('--input',type=Path);ap.add_argument('--metadata',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    if args.archive_replay:
        if args.input or args.metadata:ap.error('Choose replay OR one run')
        replay(args.out)
    else:
        if not args.input or not args.metadata:ap.error('--input and --metadata required')
        d=np.load(args.input,allow_pickle=False);m=read(args.metadata)
        if m.get('mode_order') != ['1:1','1:2','2:1','2:2'] or m.get('matrix_convention') != 'output,input':
            raise ValueError('Explicit mode_order and matrix_convention required; no inferred HFSS indexing')
        q=extract(d['f_GHz'],d['S'][:,[0,2],0],m,d['S'],d['propagating'],m.get('normalization'))
        q['input_sha256']=sha(args.input);q['metadata_sha256']=sha(args.metadata)
        write(args.out,q)


if __name__=='__main__':main()
