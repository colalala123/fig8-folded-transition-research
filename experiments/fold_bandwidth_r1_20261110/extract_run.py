"""R1-3 offline single-run extractor. Input NPZ: f_GHz, S[n,4,4], propagating[n,4].

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
from common import HERE, OLD, REPO, load, read, write, csvwrite, sha

legacy = load('r1_legacy_comparator', REPO/'experiments/fold_bandwidth_20261110/offline_fold_analysis.py')
from lib import assess, TARGET


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
    # Literal R1 second-start criterion: repeated convergence to the same
    # basin still triggers the conservative flag. Do not silently substitute
    # an undocumented basin-deduplication decision rule.
    return dict(parameters=dict(zip(('zm_eff','zs_eff','fm_GHz','fs_GHz'), map(float,best.x))),
                rms_linear=float(np.sqrt(2*best.cost/len(fr))), best_start=order[0],
                extraction_nonunique=len(near)>=2, nonunique_rule='second converged start cost <= 1.05 * minimum cost; no basin deduplication',
                near_best_start_indices=near,
                near_best_parameter_ptp=np.ptp([sols[i].x for i in near], axis=0).tolist(),
                global_uniqueness_proven=False, fit_target='abs(S11),2-11.5GHz; phase and S21 not fitted',
                starts=[dict(initial=list(map(float,p)), success=bool(q.success), cost=float(q.cost),
                             nfev=q.nfev, parameters=q.x.tolist()) for p,q in zip(starts,sols)],
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
    band = chain.bands(f, z[:,0], z[:,1])
    return dict(schema_version='R1-extracted-run-v1', case=metadata['case'], geometry_mm=g,
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
    for i,r in enumerate(rows):
        q=extract(f,data['Z'][i],r)
        row=legacy_row(f,data['Z'][i],r,q);table.append(row)
        # Avoid copying 80 redundant full grids: retain sampled fundamental
        # power plus source hash. No full-mode power claimed for archive.
        q['power']={k:v for k,v in q['power'].items() if k not in ('f_GHz','fundamental_unaccounted')}
        q['fundamental_power_samples']={k:row[k] for k in row if k.startswith('residual_power_')}
        details.append(q)
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
    write(out/'EXTRACTED_80.json',details)
    audit=dict(cases=80,numeric_comparisons=len(diffs),legacy_compatible_pass=not comparisons,
               max_abs_legacy_difference=max(diffs),mismatches=comparisons,
               max_selected_multistart_parameter_difference=max(fitdiff),
               selected_fit_not_bitwise_legacy=True,
               R1_BW20_null_count=sum(q['bandwidths']['BW20']['BW_GHz'] is None for q in details),
               literal_nonunique_flags=sum(q['circuit']['extraction_nonunique'] for q in details),
               archive_full_mode_available=False,source_hashes={p.relative_to(REPO).as_posix():sha(p) for p in [REPO/'model/dataset.npz',REPO/'model/DATASET.json',OLD/'reproduction/fold_table.csv']},
               note='Legacy columns preserve original single-start/root convention ONLY for audit. Production uses multistart best and R1 null BW20 rule. Never fabricate missing modal S.')
    write(out/'REPLAY_CHECK.json',audit)
    print(audit)
    if comparisons:raise AssertionError('Archive compatibility failed')


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
