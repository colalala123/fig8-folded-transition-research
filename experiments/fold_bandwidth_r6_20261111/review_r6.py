"""R6离线验收与双线图；不连接求解器、不隐式派发。"""
import argparse
from pathlib import Path
import sys
import numpy as np
from common_r6 import *
from review_r5 import compare_complex

def review(root,case):
    w=root/'runs'/case
    if not (w/'done.json').exists() or (w/'failure.txt').exists():raise RuntimeError('缺少完整终态导出')
    cfg=read(root/'authorization.json');freeze=read(w/'input/freeze.json')
    if freeze['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('授权不符')
    for rel,h in {**cfg['code_hashes'],**freeze['source_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('冻结文件变化:'+rel)
    if read(w/'done.json')['native_sha256']!=sha(w/'native/full_modes.npz'):raise RuntimeError('原生曲线哈希不符')
    sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
    from extract_run import extract
    from analyze_stage1 import metrics_from_extraction
    out=w/'review';out.mkdir(exist_ok=False)
    data=np.load(w/'native/full_modes.npz',allow_pickle=False);f,S=data['f_GHz'],data['S']
    q=extract(f,S[:,[0,2],0],read(w/'native/metadata.json'))
    q['full_modal_power_certified']=False;q['input_sha256']=sha(w/'native/full_modes.npz')
    write(out/'extraction_R2.json',q)
    metrics=metrics_from_extraction(q)
    record=read(w/'RUN_RECORD.json')
    num=bool(record['numerical_pass'] and 100000<=record['mesh_cells']<=112000 and record['delta_s']<=.005)
    comparisons=None;baseline=None
    if case in BASES:
        source=freeze['design']['source_case'];old=REPO/'data/raw'/source
        st=read(old/'state.json')
        if st['geometry']!=freeze['design']['geometry_mm'] or st['reference_treatment']['treatment']!='native_fundamental' or not st['reference_treatment']['no_conversion']:
            raise RuntimeError('归档几何或基模定义不一致')
        a=np.genfromtxt(old/'sparams.csv',delimiter=',',names=True,encoding='utf-8')
        z0=np.column_stack([a[k+'_real']+1j*a[k+'_imag'] for k in ('S11','S21')])
        q0=extract(a['Freq_GHz'],z0,dict(case=source,geometry=st['geometry']))
        old_metrics=metrics_from_extraction(q0)
        limits=read(R4/'STAGE1_CRITERIA_R5.json')
        lo,hi=q0['bandwidths']['BW15']['main_component_GHz']
        d11,d21=compare_complex(f,S[:,[0,2],0],a['Freq_GHz'],z0,lo,hi)
        diffs={}
        for k in ('central_valley_GHz','BW15_GHz','BW20_GHz','inner_peak_low_dB','inner_peak_high_dB'):
            delta=None if old_metrics[k] is None or metrics[k] is None else metrics[k]-old_metrics[k]
            limit=limits.get(k)
            diffs[k]=dict(archive=old_metrics[k],new=metrics[k],delta=delta,limit=limit,passed=None if limit is None else delta is not None and abs(delta)<=limit+1e-12)
        comparisons=dict(max_abs_dS11=d11,max_abs_dS21=d21,archive_BW15_band_GHz=[lo,hi],metrics=diffs)
        baseline=bool(num and read(w/'evidence/slot_comparison.json')['passed'] and d11<=.005 and d21<=.005 and all(v['passed'] is not False for v in diffs.values()))
    summary=dict(at=now(),case=case,solve_completed=record['solve_completed'],numerical_pass=num,
                 design_pass=q['shape'].get('passed'),baseline_pass=baseline,metrics=metrics,comparisons=comparisons,
                 mesh_cells=record['mesh_cells'],delta_s=record['delta_s'],Analyze_requests=record['Analyze_requested'],
                 new_Analyze_requests=record['new_Analyze_requested'],native_sha256=sha(w/'native/full_modes.npz'),
                 result_level='名义插值结果，不是直接频点或制造公差认证')
    write(out/'REVIEW_R6.json',summary)
    write(out/'envelope.json',dict(id=case,geometry_mm=freeze['design']['geometry_mm'],metrics=metrics,mesh_cells=record['mesh_cells'],
           MaxDeltaS=.005,final_delta_s=record['delta_s'],sweep_low_GHz=.01,sweep_high_GHz=15))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,5))
    for v,label in ((S[:,0,0],'S11'),(S[:,2,0],'S21')):ax.plot(f,20*np.log10(np.maximum(abs(v),1e-15)),label=label)
    ax.axhline(-20,color='gray',ls='--',lw=.8);ax.axhline(-2,color='gray',ls=':',lw=.8)
    ax.axvspan(3.92,9.52,color='green',alpha=.07)
    ax.set(xlim=(.01,15),ylim=(-60,3),xlabel='Frequency (GHz)',ylabel='Magnitude (dB)',title=case+' | R6 staged solve')
    ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(out/'S11_S21.png',dpi=150);plt.close(fig)
    if not num or baseline is False:
        write(root/'STOP.json',dict(at=now(),case=case,reason='数值验收或R5基准比较不通过，按R4停止，不放宽判据。',review=summary))
    print(__import__('json').dumps(summary,ensure_ascii=False,indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('case')
    a=p.parse_args();r=review(a.runtime.resolve(),a.case)
    sys.exit(2 if not r['numerical_pass'] or r['baseline_pass'] is False else 0)
