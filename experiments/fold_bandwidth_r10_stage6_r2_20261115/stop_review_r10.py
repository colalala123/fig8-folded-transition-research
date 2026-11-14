"""Post-stop OFFLINE report/audit only. No AEDT import, launch, or IPC."""
import datetime,hashlib,json,sys,shutil
from pathlib import Path
import numpy as np
from manage import ROOT,HERE,REPO,read,write,sha,baseline,measurement,measured_case_path
import independent_response as independent
import native_control

def run():
    cfg=read(ROOT/'authorization.json');stop=read(ROOT/'STOP.json');failed=ROOT/'runs/S6R10_P10/attempt_001'
    out=HERE/'stop_review';out.mkdir()
    rows=[];replays=[];source={}
    for i in range(1,10):
        case=f'S6R10_P{i}__T1';w=measured_case_path(ROOT,case,cfg)
        if i==9:w=ROOT/'runs/S6R10_P9/attempt_001'
        m=measurement(w);z=independent.metrics(*independent.load_csv(w/'native/full_modes.csv'))
        diff={k:float(z[k]-m[v]) for k,v in [('valley_GHz','center_GHz'),('peak_lo_dB','low_peak_dB'),('peak_hi_dB','high_peak_dB'),('BW20','BW20_GHz')]}
        q=read(w/'review/extraction_R2.json');fz=read(w/'INPUT.json') if (w/'INPUT.json').exists() else read(w/'input/freeze.json')
        rr=read(w/'SUMMARY.json')['record'] if (w/'SUMMARY.json').exists() else read(w/'RUN_RECORD.json')
        rows.append(dict(case=case,geometry_mm=fz['design']['geometry_mm'],measurement=m,mesh=rr['mesh_cells'],delta_s=rr['delta_s'],actual_Analyze=rr['Analyze_requested']))
        replays.append(dict(case=case,independent=z,difference_from_review=diff,max_abs_difference=max(abs(v) for v in diff.values())))
        for rel in ('native/full_modes.csv','native/full_modes.npz','review/extraction_R2.json','review/visual_ack.json','review/S11_S21.png'):source[str(w/rel)]=sha(w/rel)
    if max(r['max_abs_difference'] for r in replays)>1e-10:raise RuntimeError('independent raw replay disagreement')
    b=baseline();bmax=max(b['low_peak_dB'],b['high_peak_dB']);tested_pairs={}
    for source_name,plus,minus in [('Ws',0,1),('Lm',2,3),('Ls1',4,5),('Wm',6,7)]:
        rr=[rows[plus],rows[minus]];worst=max(rr,key=lambda r:max(r['measurement']['low_peak_dB'],r['measurement']['high_peak_dB']))
        tested_pairs[source_name]=dict(worst_case=worst['case'],worst_highest_peak_rise_dB=max(0.,max(worst['measurement']['low_peak_dB'],worst['measurement']['high_peak_dB'])-bmax))
    geometry=read(failed/'evidence/geometry_build.json');objects=geometry['materials_and_boundary']['after'];air=objects['air_box']['bounding_box'];viol=[]
    for n in ('Substrate_7','Substrate_9'):
        box=objects[n]['bounding_box']
        for axis,k in zip(('x','y','z'),range(3)):
            if box[k]<air[k]-1e-8:viol.append(dict(object=n,axis=axis,side='low',excess_mm=air[k]-box[k]))
            if box[k+3]>air[k+3]+1e-8:viol.append(dict(object=n,axis=axis,side='high',excess_mm=box[k+3]-air[k+3]))
    log=(failed/'native/aedt_startup.log').read_text(encoding='utf-8',errors='replace')
    errors=[s for s in log.splitlines() if '[error]' in s.lower()]
    if not any('Substrate_9 and air_box intersect' in s for s in errors):raise RuntimeError('expected native root-cause evidence missing')
    (out/'NATIVE_ERRORS.txt').write_text('\n'.join(errors)+'\n',encoding='utf-8')
    for rel in ('failure.txt','RUN_RECORD.json','cleanup.json','owner.json','worker_started.json','launcher_claim.json','launcher_spawn.json'):
        shutil.copyfile(failed/rel,out/rel)
    evidence=out/'evidence';evidence.mkdir()
    for rel in ('geometry_build.json','materials_and_boundary.json','native_slot_boxes.json','ports.json','presubmit.json','slot_comparison.json','adaptive_00_solve_return.json','adaptive_00_solver.jsonl','adaptive_00_settings.json'):
        shutil.copyfile(failed/'evidence'/rel,evidence/rel)
    record=read(failed/'RUN_RECORD.json');g=list((ROOT/'ledger').glob('geometry_*.json'));a=list((ROOT/'ledger').glob('Analyze_*.json'))
    if (len(g),len(a),record['Analyze_requested'])!=(2,10,1):raise RuntimeError('budget mismatch')
    current=dict(stage6_geometry=8+len(g),stage6_Analyze=87+len(a),cumulative_geometry=181+len(g),cumulative_Analyze=1720+len(a),geometry_cap=200,
        valid_response_geometries=9,technical_failure_geometries=1,initial6A_not_started=['P11','P12','P13','P14','N0'])
    report=dict(at_JST=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),phase='technical_stopped_at_P10',
        all_R10_complete=False,stop=stop,budget=current,valid_results=rows,baseline_B1=b,tested_geometric_pairs=tested_pairs,
        independent_raw_replay=replays,max_abs_replay_difference=max(r['max_abs_difference'] for r in replays),
        failure=dict(kind='CAD_computational_domain_conflict_not_design_failure',case='S6R10_P10__T1',actual_Analyze_requests=1,
            hf3d_observations=0,actual14core_observed=False,requested_cores=14,copper_bbox={n:objects[n]['bounding_box'] for n in ('Substrate_7','Substrate_9')},
            air_bbox=air,bbox_excess=viol,native_errors=errors,cleanup=record['cleanup'],same_settings_retry_would_not_fix_geometry=True),
        M_computed=False,P_req_computed=False,R10_2_frozen=False,stage6B_started=False,stage6C_started=False,
        Q11_encoding_audit=read(REPO/'experiments/fold_bandwidth_r10_stage6_r1_20261115/analysis/P1_P6_PARTIAL.json')['Q11'],
        source_sha256=source,limitations=['CONTROL completed/pass means valid observation, not delivery/manufacturing pass.',
            'P9 alone is insufficient to score paired etch Q12 or compute realistic M.',
            'Zero-Analyze CAD preflights are not electromagnetic tolerance results.',
            'Vertex/bbox agreement with frozen CAD does not certify air-domain Boolean legality.'])
    write(out/'STOP_REVIEW.json',report);write(ROOT/'STOP_SUMMARY.json',{k:v for k,v in report.items() if k not in ('valid_results','source_sha256','independent_raw_replay')})
    lines=['# R10阶段6技术停止报告','',
        '**总结：阶段6未全部完成。P1–P9已取得有效原生结果并完成实看图审核；P10欠蚀刻点在首个Analyze失败，HFSS明确报告两层地铜与air_box相交。现按停止规则保留证据并停下，未创建R3，未开始6B/6C。**','',
        f"报告时间：{report['at_JST']}（日本时间）。",'',
        '## 预算与进度','',
        '- 阶段6实际使用10个几何、97次Analyze请求，其中96次归属于9项完成结果，P10失败请求1次。',
        '- 累计183/200个几何、1730次Analyze请求；余量不能擅自转为新设计或扩大授权。',
        '- P11、P12、P13、P14、N0未开始真实求解；条件密网格、C1、B1R及6C均未开始。',
        '- P9早先的端口属性异常为0Analyze；后续工具预检也为0Analyze，均未冒充仿真结果。',
        '- 所有停止、失败、缓存和冻结保留；没有复算P1–P8，没有放宽网格、ΔS或设计阈值。','',
        '## P10根因','',
        '欠蚀刻e=−0.01 mm使地铜外轮廓扩至x=±15.01 mm，而原air_box包络仍为x=±15.00 mm。已保存的CAD确实与原冻结相符，但冻结本身没有约束铜与计算空气域的合法性。',
        '原生日志直接报告：`Parts Substrate_9 and air_box intersect`及`Parts Substrate_7 and air_box intersect`。首次请求约3秒返回失败，没有观察到hf3d自适应进程、没有网格或S参数结果。因此这不是ΔS不收敛，也不能记为设计S11未达标。',
        '此前门禁验证了槽盒、轮廓、材料、端口及其与冻结的一致性，但漏掉了整体布尔/空气域合法性，这是应补齐的建模门禁，不能靠同设置重算解决。','',
        '## 已完成的有效实验点（不是9个新交付设计）','',
        '|点|中央谷GHz|低内峰dB|高内峰dB|BW20 GHz|网格|ΔS|Analyze|','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        m=r['measurement'];lines.append(f"|{r['case'].removeprefix('S6R10_').removesuffix('__T1')}|{m['center_GHz']:.2f}|{m['low_peak_dB']:.6f}|{m['high_peak_dB']:.6f}|{m['BW20_GHz']:.6f}|{r['mesh']}|{r['delta_s']:.7f}|{r['actual_Analyze']}|")
    lines+=['','九项原生CSV均由不导入规范提取器的重放器独立复算；中央谷、两峰、BW20最大差见STOP_REVIEW.json，均≤1e−10。','',
        '## 当前能说与不能说的结论','',
        '- Q11：Ws高频峰中心差分半幅0.560542 dB；Lm中央谷半幅35 MHz，符合登记量级。35 MHz浮点端点问题已单独披露，保留冻结代码的原始False和1e−8编码容差后的独立True，不改预测区间。',
        '- 已完整实测的四组几何公差中，最高内峰最坏升幅：Ws约0.503 dB，Ls1约0.313 dB，Wm约0.273 dB，Lm约0.234 dB。h和εr尚无电磁结果，不能称这就是全部公差的最终排序。',
        '- P9过蚀刻单侧最高峰升幅约0.308 dB，小于单改Ws正侧的0.503 dB；欠蚀刻侧缺失，暂不评分Q12，也不把单侧当作最坏侧。',
        '- M、P_req、C1最坏符号和稳健交付选择都未定；不推荐把当前B1直接说成制造−20dB保证。6C未做，没有新增2.5/2.65mm平台结论。','',
        '## 下一步（仅方案，不自动执行）','',
        '先由用户/计划审核明确地铜外沿的制造边界口径：偏置后按板框裁切，或保留完整偏置并重建合法空气/布尔域。两者不能悄悄混用；若改变已测P9的定义，必须显式处理其可比性。',
        '然后在新冻结中补铜/空气包络和原生整体模型合法性检查，在Analyze前拦截此类相交；明确P10已耗1次、后续若算同点技术恢复则合计仍≤14次（最多余13次），几何槽归属须写清，不自动追加额度。',
        '旧P10记录不覆盖、不删marker、不清工程锁；完成新的有限恢复约定后才接续P10及后续。原R1/R2当前均保持停止。','']
    (HERE/'STOP_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    print(json.dumps(dict(budget=current,max_replay_diff=report['max_abs_replay_difference'],native_error_count=len(errors),bbox_violations=viol),ensure_ascii=False))

if __name__=='__main__':run()
