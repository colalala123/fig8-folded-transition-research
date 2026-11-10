"""Read frozen archive, write new phase-0 evidence. No HFSS/network/process calls."""
import argparse
import csv
import hashlib
import json
import platform
import re
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import least_squares
from scipy.signal import find_peaks
import chain

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p,obj):
    with Path(p).open('x',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)


def csvwrite(p,rows):
    with Path(p).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def stats(v):
    v=np.asarray(v,float)
    return dict(n=len(v),mean=float(v.mean()),sd=float(v.std(ddof=1)),
                min=float(v.min()),max=float(v.max()))


def errors(v):
    v=np.asarray(v,float)
    return dict(n=len(v),MAE=float(np.mean(abs(v))),max_abs=float(max(abs(v))),
                bias=float(v.mean()),RMSE=float(np.sqrt(np.mean(v*v))))


def peak_mean(f,s):
    r=20*np.log10(np.maximum(abs(s),1e-15))
    return float(np.mean([max(r[(f>lo)&(f<hi)]) for lo,hi in [(4.4,5.8),(7.6,8.9)]]))


def numeric_compare(a,b):
    diffs=[];fail=[]
    def walk(x,y,p):
        if isinstance(x,dict) and isinstance(y,dict):
            if x.keys()!=y.keys(): fail.append(p+':keys');return
            for k in x:walk(x[k],y[k],p+'/'+k)
        elif isinstance(x,list) and isinstance(y,list):
            if len(x)!=len(y):fail.append(p+':length');return
            for i,(xx,yy) in enumerate(zip(x,y)):walk(xx,yy,p+'/'+str(i))
        elif isinstance(x,(int,float)) and isinstance(y,(int,float)):
            diffs.append((abs(x-y),p))
            if not np.isclose(x,y,rtol=1e-7,atol=1e-8):fail.append(p)
        elif x!=y:fail.append(p+':value')
    walk(a,b,'')
    return dict(passed=not fail,rtol=1e-7,atol=1e-8,n_numeric=len(diffs),
                max_abs_difference=max(diffs)[0],max_difference_path=max(diffs)[1],failures=fail)


def geometry_evidence():
    p=REPO/'hfss/INV01_A14.aedt';s=p.read_text(encoding='utf-8',errors='strict')
    names=['StructureBSlot_'+side+'_'+part for side in ('top','bot') for part in ('main','right_v','right_h','left_v','left_h')]
    # Collect actual names, not guesses, limited to the existing StructureBSlot operands.
    blocks=[]
    for m in re.finditer(r"Name='(StructureBSlot_[^']+)'",s):
        q=re.search(r"\$begin 'BoxParameters'(.*?)\$end 'BoxParameters'",s[m.end():],re.S)
        if not q:continue
        vals=dict(re.findall(r"(\w+)='([^']+)'",q.group(1)))
        blocks.append(dict(name=m.group(1),name_line=s.count('\n',0,m.start())+1,
                           parameters=vals))
    top={b['name']:b for b in blocks if 'top' in b['name']}
    return dict(project='hfss/INV01_A14.aedt',sha256=sha(p),method='static AEDT operand records; no GUI/COM open',
                blocks=blocks,live_CAD_verified=False,
                formulas=dict(L_parameter_sum='Ls1+2*Ls2+2*Ls3',
                              L_polyline_center='L_parameter_sum-4*Ws',
                              g='Ls2-2*Ws',a='Ls3-Ws',
                              tip_microstrip_x='(Ls1-2*Ls3-Wm)/2',tips_x='Ls1-2*Ls3'),
                caveat='Operand geometry is not a live final-solid/topology verification. Centreline is a geometrical polyline, not electrical length.')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    out=ap.parse_args().out;out.mkdir(parents=True,exist_ok=False)
    old=REPO/'experiments/fold_bandwidth_20261110/out'
    rerun=HERE/'reproduction'
    comp=numeric_compare(read(old/'SUMMARY.json'),read(rerun/'SUMMARY.json'))
    comp['files']={k:dict(original_sha256=sha(old/k),rerun_sha256=sha(rerun/k)) for k in ('SUMMARY.json','fold_table.csv','fold_pairs.csv')}
    comp['environment']=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    write(out/'REPRODUCTION.json',comp)
    rows=read(REPO/'model/DATASET.json')['rows'];d=np.load(REPO/'model/dataset.npz',allow_pickle=False)
    f,z=d['f'],d['Z'];win=(f>=2)&(f<=11.5)
    table=list(csv.DictReader((rerun/'fold_table.csv').open(encoding='utf8')))
    pairs=list(csv.DictReader((rerun/'fold_pairs.csv').open(encoding='utf8')))
    fields=['d_bw_S11_15dB','d_bw_S21_2dB','d_N2','d_P_eff','d_inner_peak_mean_dB','d_residual_power_9p5']
    rng=np.random.default_rng(20261110)
    def paired(sel):
        fam=sorted({r['family'] for r in sel});ans={}
        for key in fields:
            raw=np.array([float(r[key]) for r in sel])
            means=np.array([np.mean([float(r[key]) for r in sel if r['family']==g]) for g in fam])
            boot=means[rng.integers(0,len(means),(4000,len(means)))].mean(axis=1)
            ans[key]=dict(pair_weighted=stats(raw),family_balanced=stats(means),
                          descriptive_family_bootstrap_95pct=np.quantile(boot,[.025,.975]).tolist(),
                          family_negative=int((means<0).sum()),family_positive=int((means>0).sum()))
        return dict(n_pairs=len(sel),n_families=len(fam),metrics=ans)
    write(out/'PAIRED_AUDIT.json',dict(all47=paired(pairs),original24=paired([p for p in pairs if p['source']=='original48']),
          pairing_warning='47 combinations reuse geometries; lengths differ; not independent randomized treatment effects.',
          seed=20261110,resamples=4000))
    # Reproduce plan rounded-law predictions, separately audit multistart extraction.
    detail=[];fits=[];allbands=[]
    for i,(r,t) in enumerate(zip(rows,table)):
        assert r['case']==t['case']
        g=r['geometry'];p0=np.array([float(t[k]) for k in ('zm_eff','zs_eff','fm_GHz','fs_GHz')])
        target=abs(z[i,win,0]);n=chain.nominal(g['Wm'],g['Ws'])
        starts=[[n['Zm_ohm']/50,n['Zs_ohm']/50,6.72,6.72],p0,
                [.7,2.2,5.8,7.5],[1.3,1.3,7.5,5.8],[1.7,4,8.2,8.2],[.5,3.5,5,5]]
        sols=[least_squares(lambda v:abs(chain.circuit(f[win],*v)[0])-target,s0,
                bounds=([.3,.5,4,4],[3,6,10,10]),max_nfev=2000,
                ftol=1e-10,xtol=1e-10,gtol=1e-10) for s0 in starts]
        best=min(sols,key=lambda v:v.cost)
        near=[s.x for s in sols if s.cost<=best.cost*1.0001+1e-10]
        sv=np.linalg.svd(best.jac,compute_uv=False)
        fits.append(dict(case=r['case'],successes=sum(bool(s.success) for s in sols),n_starts=len(starts),
                         costs=[float(s.cost) for s in sols],best_parameters=best.x.tolist(),
                         near_best_count=len(near),near_best_parameter_ptp=np.ptp(near,axis=0).tolist(),
                         original_fit_RMS=float(t['fit_rms_linear']),best_RMS=float(np.sqrt(2*best.cost/len(target))),
                         jacobian_singular_values=sv.tolist(),jacobian_condition=float(sv[0]/sv[-1]),
                         global_uniqueness_proven=False))
        pred=chain.forward(g,exploratory=True)
        s11,s21=chain.circuit(f,*[pred[k] for k in ('zm_eff','zs_eff','fm_GHz','fs_GHz')])
        # S21 amplitude is a secondary diagnostic, not part of the magnitude-only fit.
        fit11,fit21=chain.circuit(f,*p0)
        ip=np.mean([p['S11_dB'] for p in r['score']['inner_peaks']])
        pband=chain.bands(f,s11,s21);aband=chain.bands(f,z[i,:,0],z[i,:,1])
        circ15=chain.closed_band(float(t['P_eff']),float(t['zm_eff']),.5*(float(t['fm_GHz'])+float(t['fs_GHz'])),-15)
        circ20=chain.closed_band(float(t['P_eff']),float(t['zm_eff']),.5*(float(t['fm_GHz'])+float(t['fs_GHz'])),-20)
        allbands.append(dict(case=r['case'],source=r['source'],actual=aband,
                         rounded_law_lossless_circuit=pband,equal_frequency_approx=dict(BW15=circ15,BW20=circ20)))
        detail.append(dict(case=r['case'],family=r['family'],source=r['source'],
                 rounded_law_S11_abs_RMS=float(np.sqrt(np.mean((abs(s11[win])-target)**2))),
                 rounded_law_inner_peak_error_dB=peak_mean(f,s11)-ip,
                 rounded_law_eq_frequency_ripple_error_dB=chain.ripple_db(pred['P_eff'])-ip,
                 rounded_law_bw15_error_GHz=pband['BW15']['BW_GHz']-aband['BW15']['BW_GHz'],
                 fitted_circuit_S21_abs_RMS=float(np.sqrt(np.mean((abs(fit21[win])-abs(z[i,win,1]))**2))),
                 rounded_law_fm_error_GHz=pred['fm_GHz']-float(t['fm_GHz']),
                 rounded_law_fs_error_GHz=pred['fs_GHz']-float(t['fs_GHz']),
                 deltaLs_center_mm=float(t['slot_length_correction_mm'])+4*g['Ws']))
    csvwrite(out/'law_replay_80.csv',detail);write(out/'ALL_BANDWIDTHS.json',allbands)
    write(out/'MULTISTART.json',dict(n_cases=80,starts_per_case=6,fit_target='abs(S11),2-11.5GHz',
          threshold_for_near_best='cost <= best_cost*1.0001 + 1e-10',cases=fits,
          conclusion='Finite multistart and Jacobian rank cannot prove global/physical identifiability; S21 phase/loss were not fitted.'))
    # Explicit family-disjoint CV of N1/N2. 78 development only; diagnostic holdout kept out.
    X=np.array([[1,float(t['a_mm']),np.log(50*float(t['zs_nominal'])),np.log(50*float(t['zm_nominal']))] for t in table])
    Y=np.array([[float(t['N1']),float(t['N2'])] for t in table])
    zmnom=np.array([float(t['zm_nominal']) for t in table]);zsnom=np.array([float(t['zs_nominal']) for t in table])
    dev=np.array([i for i,r in enumerate(rows) if r['source']!='diagnostic_holdout'])
    groups=np.array([r['family'] for r in rows]);unique=sorted(set(groups[dev]))
    folds=[];cv=[]
    for k,testfam in enumerate(np.array_split(unique,6)):
        tr=dev[~np.isin(groups[dev],testfam)];te=dev[np.isin(groups[dev],testfam)]
        weights=np.array([1/np.sum(groups[tr]==groups[j]) for j in tr])
        coef=np.linalg.lstsq(X[tr]*np.sqrt(weights[:,None]),Y[tr]*np.sqrt(weights[:,None]),rcond=None)[0]
        y=X[te]@coef
        for j,yy in zip(te,y):
            pp=yy[0]**2*zmnom[j]*yy[1]**2*zsnom[j]
            actual=np.mean([p['S11_dB'] for p in rows[j]['score']['inner_peaks']])
            cv.append(dict(case=rows[j]['case'],family=rows[j]['family'],fold=k,
                           error_dB=chain.ripple_db(pp)-actual))
        folds.append(dict(fold=k,train_families=sorted(set(groups[tr])),test_families=list(testfam),
                          train_cases=[rows[j]['case'] for j in tr],test_cases=[rows[j]['case'] for j in te],coefficients=coef.tolist()))
    fammae=[np.mean([abs(r['error_dB']) for r in cv if r['family']==g]) for g in unique]
    # This is a fresh, specified CV audit, not a claim to reproduce unspecified author's splits.
    write(out/'GROUP_CV.json',dict(protocol='6 deterministic family-disjoint folds, family-balanced training, 78 development only; fixed coefficient form, no hyperparameter selection',
                 point_weighted=errors([r['error_dB'] for r in cv]),family_balanced_MAE_dB=float(np.mean(fammae)),
                 folds=folds,predictions=cv,not_prospective=True,
                 comparison='Plan 0.12/0.31dB claim lacks original folds; this protocol is independently specified.'))
    metrics={k:errors([r[k] for r in detail]) for k in detail[0] if k.endswith(('error_dB','error_GHz'))}
    metrics['rounded_law_S11_abs_RMS']=stats([r['rounded_law_S11_abs_RMS'] for r in detail])
    metrics['fitted_circuit_S21_abs_RMS']=stats([r['fitted_circuit_S21_abs_RMS'] for r in detail])
    metrics['deltaLs_center_mm']=stats([r['deltaLs_center_mm'] for r in detail])
    metrics['bw20_outer_envelope_not_continuous_count']=sum(r['equal_frequency_approx']['BW20']['components']==3 for r in allbands)
    metrics['plan_gate_status']='audit_only: original unspecified CV is not exactly reproducible; rounded coefficients are evaluated, not promoted to validated design law'
    write(out/'LAW_AUDIT.json',metrics)
    write(out/'GEOMETRY_EVIDENCE.json',geometry_evidence())
    print(json.dumps(dict(reproduction=comp,law_metrics=metrics,cv=errors([r['error_dB'] for r in cv])),indent=2))


if __name__=='__main__':main()
