"""R6阶段1离线报告：沿用R2噪声算法，仅替换已取消的基准门槛。"""
import argparse
import sys
import numpy as np
from common_r6 import *
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
from analyze_stage1 import analyze as legacy_analyze,metrics_from_extraction,finite
from extract_run import extract

def analyze(data,gates):
    legacy=legacy_analyze(data)
    complete=len(gates)==3 and {x['case'] for x in gates}==set(BASES)
    baseline_ok=complete and all(x.get('numerical_pass') is True and x.get('baseline_pass') is True for x in gates)
    final_delta=[]
    for row in data['baseline']+data['perturbations']:
        v=row.get('final_delta_s')
        final_delta.append(dict(id=row['id'],value=v,passed=bool(finite(v) and 0<=v<=.005)))
    numerical_ok=legacy['numerical_checks_passed'] and all(r['passed'] for r in final_delta)
    required=tuple(legacy['criteria']['baseline_max_abs_difference'])
    noise_ok=all(legacy['perturbation_noise'][key]['available'] for key in required)
    return dict(schema_version='R6-stage1-analysis-v1',at=now(),
         baseline_comparability_passed=bool(baseline_ok),baseline_comparisons_R5=gates,
         numerical_checks_passed=bool(numerical_ok),numerical_checks=legacy['numerical_checks'],
         final_delta_checks=final_delta,perturbation_noise=legacy['perturbation_noise'],
         zero_repeat_minus_baseline=legacy['zero_repeat_minus_baseline'],
         required_noise_metrics_available=noise_ok,batch1b_outputs_complete=bool(baseline_ok and numerical_ok and noise_ok),
         legacy_inner_peak_gate_ignored=True,
         superseded_baseline_comparisons_information_only=legacy['baseline_comparisons'],
         noise_threshold_added=False,noise_algorithm_sha256=sha(REPO/'experiments/fold_bandwidth_r2_20261110/analyze_stage1.py'),
         baseline_criteria_sha256=sha(R4/'STAGE1_CRITERIA_R5.json'),
         solver_started=False,new_Analyze_requests=0,
         interpretation='基准可比性用R5/R6；线性/二次残差标准差、微小对差分分别报告。内峰0.1dB旧门槛仅留作被替代的历史说明，不控制接续；不添加噪声限值。')

def build(root):
    gate=read(root/'gate_1a.json')
    if gate['passed'] is not True:raise RuntimeError('1a未通过')
    frozen={r['id']:r for r in read(REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json')['designs']}
    data=dict(archive=[],baseline=[],perturbations=[])
    provenance={}
    for case in (*BASES,*STEPS):
        g=frozen[case]['geometry_mm']
        if case==BASES[0]:
            folder=root/'baseline_ref'/case
            qp=folder/'extraction_R2.json'
            record=read(folder/'RUN_RECORD.json')
            native=folder/'full_modes.npz'
        else:
            folder=root/'runs'/case
            qp=folder/'review/extraction_R2.json'
            record=read(folder/'RUN_RECORD.json')
            native=folder/'native/full_modes.npz'
            if not (folder/'done.json').exists() or (folder/'failure.txt').exists():raise RuntimeError(case+'未完成')
        q=read(qp)
        if q['geometry_mm']!=g:raise RuntimeError(case+'几何与冻结输入不一致')
        envelope=dict(id=case,geometry_mm=g,metrics=metrics_from_extraction(q),
             mesh_cells=record['mesh_cells'],MaxDeltaS=.005,final_delta_s=record['delta_s'],sweep_low_GHz=.01,sweep_high_GHz=15.)
        data['baseline' if case in BASES else 'perturbations'].append(envelope)
        provenance[case]=dict(extraction_sha256=sha(qp),native_sha256=sha(native))
        if case in BASES:
            source=frozen[case]['source_case'];p=REPO/'data/raw'/source
            st=read(p/'state.json')
            if st['geometry']!=g:raise RuntimeError('归档几何不匹配')
            a=np.genfromtxt(p/'sparams.csv',delimiter=',',names=True,encoding='utf-8')
            z=np.column_stack([a[k+'_real']+1j*a[k+'_imag'] for k in ('S11','S21')])
            q0=extract(a['Freq_GHz'],z,dict(case=source,geometry=g))
            data['archive'].append(dict(id=case,geometry_mm=g,metrics=metrics_from_extraction(q0)))
            provenance[case]['archive_curve_sha256']=sha(p/'sparams.csv')
    result=analyze(data,gate['baselines'])
    result['input_evidence']=provenance
    return data,result

def report(root,out):
    if out.exists():raise RuntimeError('报告目录已存在，不覆盖')
    data,result=build(root)
    out.mkdir(parents=True)
    write(out/'input.json',data);write(out/'analysis.json',result)
    lines=['# R6 阶段1：基准可比性与微扰噪声','',
       '已分别计算基准差、九点阶梯的线性/二次残差标准差、以及±0.002 mm微小对的扣斜率差分。三者不合并为一个噪声估计。没有增加求解、改变阈值或把空值补成带宽。','',
       '|指标|线性残差SD|二次残差SD|微小对原始差|扣斜率差|','|---|---:|---:|---:|---:|']
    for key,v in result['perturbation_noise'].items():
        if not v['available']:
            lines.append('|'+key+'|不可用|不可用|不可用|不插补|')
        else:
            lines.append('|'+key+'|'+ '|'.join(f"{v[k]:.8g}" for k in ('linear_residual_sd','quadratic_residual_sd','small_pair_raw_difference','small_pair_slope_corrected_difference'))+'|')
    lines+=['','GHz量的差乘1000为MHz。幅度为dB。两种残差SD描述此尺寸阶梯的残差，不自动等同于独立重复求解的随机噪声。','',
       '完整基准逐项差（包括内峰差、中央谷、BW15和复数S参数）见 analysis.json。R1的内峰0.1dB限值已被R5取消，不作放行条件。',
       '1b规定的输出完整性：'+str(result['batch1b_outputs_complete'])+'。后续2a仍须先核对最新计划、预算和新批次输入，不由此脚本直接启动。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(__import__('json').dumps({k:v for k,v in result.items() if isinstance(v,(bool,int,str))},ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();report(a.root.resolve(),a.out.resolve())
