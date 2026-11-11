"""阶段1报告的独立数值复算及零扰动全模式检查，不连接HFSS。"""
import argparse
import json
from pathlib import Path
import numpy as np
from common_r6 import read,write,sha,now

def audit(root,folder):
    d=read(folder/'input.json');a=read(folder/'analysis.json')
    base=next(r for r in d['baseline'] if r['id']=='S1_BASE_N14')
    x=np.array([r['geometry_mm']['Ws']-base['geometry_mm']['Ws'] for r in d['perturbations']])
    checks=[]
    for key,n in a['perturbation_noise'].items():
        vals=[r['metrics'][key] for r in d['perturbations']]
        if any(v is None for v in vals):
            checks.append(dict(metric=key,null_preserved=not n['available']))
            continue
        y=np.array(vals);delta={}
        coeff={}
        for degree in (1,2):
            X=np.stack([x**j for j in range(degree+1)],axis=1)
            b=np.linalg.lstsq(X,y,rcond=None)[0];coeff[degree]=b
            residual=y-X@b
            sd=np.sqrt(residual@residual/(len(x)-degree-1))
            name='linear_residual_sd' if degree==1 else 'quadratic_residual_sd'
            delta[name]=float(abs(sd-n[name]))
        corrected=y[5]-y[3]-coeff[1][1]*(x[5]-x[3])
        delta['small_pair_slope_corrected_difference']=float(abs(corrected-n['small_pair_slope_corrected_difference']))
        checks.append(dict(metric=key,absolute_recalculation_difference=delta,passed=max(delta.values())<1e-10))
    n14=root/'runs/S1_BASE_N14';zero=root/'runs/S1_WS_04'
    A=np.load(n14/'native/full_modes.npz',allow_pickle=False);B=np.load(zero/'native/full_modes.npz',allow_pickle=False)
    repeat={}
    for key in ('f_GHz','S','Zo','Gamma'):
        if A[key].shape!=B[key].shape:raise RuntimeError('零扰动数组维度不同')
        repeat[key]=dict(exact_equal=bool(np.array_equal(A[key],B[key])),max_abs_difference=float(np.max(abs(A[key]-B[key]))))
    records=[read(root/'runs'/r['id']/'RUN_RECORD.json') for r in d['perturbations']]
    cfg=read(root/'authorization.json')
    observed_counts=dict(batch1b_geometry_count=len(records),batch1b_Analyze_requests=sum(r['Analyze_requested'] for r in records),
       total_geometry=cfg['prior_geometry_total']+len(list((root/'ledger').glob('geometry_*.json'))),
       total_actual_Analyze_requests=cfg['prior_Analyze_total']+len(list((root/'ledger').glob('Analyze_*.json'))),
       mesh_min=min(r['mesh_cells'] for r in records),mesh_max=max(r['mesh_cells'] for r in records),
       delta_s_min=min(r['delta_s'] for r in records),delta_s_max=max(r['delta_s'] for r in records))
    report=dict(at=now(),checks=checks,all_recalculations_passed=all(r.get('passed',r.get('null_preserved',False)) for r in checks),
       zero_repeat_full_native_arrays=repeat,zero_and_baseline_independent_workers=[read(p/'worker_started.json') for p in (n14,zero)],
       zero_repeat_is_fresh_cold_solve=all(read(p/'input/freeze.json')['resume'] is False for p in (n14,zero)),
       counts=observed_counts,input_sha256=sha(folder/'input.json'),analysis_sha256=sha(folder/'analysis.json'),
       result='独立lstsq复算；两个相同几何只检查确定性，不据此把微扰噪声判成零。')
    write(folder/'INDEPENDENT_AUDIT.json',report)
    if not report['all_recalculations_passed']:raise RuntimeError('报告独立复算不一致')
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','zero_and_baseline_independent_workers')},ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('folder',type=Path);a=p.parse_args();audit(a.root,a.folder)
