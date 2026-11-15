"""Post-STOP offline audit, independent CSV replay and Chinese handoff.
Never imports AEDT, dispatches a worker, edits frozen code or resets markers.
"""
import sys,math,shutil,json,os,subprocess
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
H=REPO/'experiments/fold_bandwidth_r12_stage6_r4_20261115'
sys.path.insert(0,str(H))
from common_stage2 import read,write,sha,now,case_dir,history
from prepare_r10 import ROOT,OLD
from manage import measurement,baseline,measured_case_path
import r12,independent_response as raw,tolerance_analysis as ta

def build():
    out=H/'stop_review';out.mkdir(exist_ok=False)
    cfg=read(ROOT/'authorization.json');stop=read(ROOT/'STOP.json')
    dense='S6R10_B1Rdense__T1';w=case_dir(ROOT,dense,cfg);rec=read(w/'RUN_RECORD.json')
    if stop['case']!=dense or rec['mesh_cells']!=247756 or rec['Analyze_requested']!=12 or rec['delta_s']!=.0023507:raise RuntimeError('stop evidence changed')
    if (w/'done.json').exists() or (w/'native/full_modes.csv').exists():raise RuntimeError('unexpected dense sweep data')
    if not (w/'model.aedtresults').is_dir():raise RuntimeError('dense cache not retained')
    import psutil
    natives=[dict(pid=p.pid,name=p.info['name']) for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe')]
    workers=[dict(pid=p.pid,name=p.info['name']) for p in psutil.process_iter(['name','cmdline']) if p.pid!=os.getpid() and (p.info['name'] or '').lower().startswith('python') and any(('fig8_r12_stage6_r4' in x or 'fold_bandwidth_r12_stage6_r4' in x) for x in p.info['cmdline'] or [])]
    if natives or workers:raise RuntimeError('unexpected native or R4 worker active')
    b=baseline();replays=[];rows=[];maxdiff=0.
    def replay(case,d,m):
        nonlocal maxdiff
        q=raw.metrics(*raw.load_csv(d/'native/full_modes.csv'));ds={}
        for k,z in [('center_GHz','valley_GHz'),('low_peak_dB','peak_lo_dB'),('high_peak_dB','peak_hi_dB'),('BW20_GHz','BW20')]:
            if (m[k] is None)!=(q[z] is None):raise RuntimeError('null replay mismatch '+case)
            ds[k]=None if m[k] is None else q[z]-m[k]
            if ds[k] is not None:
                maxdiff=max(maxdiff,abs(ds[k]))
                if abs(ds[k])>1e-10:raise RuntimeError('raw CSV replay mismatch '+case)
        replays.append(dict(case=case,csv_sha256=sha(d/'native/full_modes.csv'),independent=q,differences=ds))
    replay('B1',OLD/'results/S5R9_B1__T2',b)
    ms={}
    for n in [f'P{i}' for i in range(1,10)]+['P9c','P10','P11','P12','P13','P14','N0']:
        dec=read(ROOT/'decisions'/('S6R10_'+n+'_FINAL.json'));c=dec['selected_case'];d=measured_case_path(ROOT,c,cfg)
        m=measurement(d);ms[n]=m;replay(c,d,m)
        rows.append(dict(point=n,measurement=m,differences={k:m[k]-b[k] if m.get(k) is not None and b.get(k) is not None else None for k in ta.RESPONSES},
            highest_peak_rise_dB=ta.highest(m)-ta.highest(b),source=d.relative_to(REPO).as_posix()))
    trials=[]
    for i in (1,2,3):
        c=f'S6R10_B1R__T{i}';d=H/'results'/c;m=measurement(d);replay(c,d,m)
        trials.append(dict(case=c,measurement=m,geometry_mm=read(d/'INPUT.json')['design']['geometry_mm'],
            nominal_robust_pass=ta.robust_nominal_pass(m,read(H/'freeze_6B/R10_2.json')['analysis']['P_req_dB']),
            record=read(d/'SUMMARY.json')['record']))
    fz=read(H/'freeze_6B/R10_2.json');a=fz['analysis'];s=trials[2]['measurement'];t1=trials[0]['measurement']
    requested=fz['T1_comparison']['target_response'][1]-(b['low_peak_dB']+b['high_peak_dB'])/2
    actual=(t1['low_peak_dB']+t1['high_peak_dB']-b['low_peak_dB']-b['high_peak_dB'])/2
    bw_cost_MHz=(b['BW20_GHz']-s['BW20_GHz'])*1000
    added_margin=ta.highest(b)-ta.highest(s);cost=bw_cost_MHz/added_margin
    scores=dict(
        Q21=dict(assessable=True,passed=.7<=actual/requested<=1.3,actual_mean_change_dB=actual,target_mean_change_dB=requested,fraction=actual/requested),
        Q22=dict(assessable=True,passed=6.10<=s['BW20_GHz']<=6.30,BW20_GHz=s['BW20_GHz']),
        Q23=dict(assessable=False,passed=None,reason='Dense confirmation stopped before sweep; C1R not started. Neither robustness label is certified.'),
        Q24=dict(assessable=False,passed=None,reason='No C1R result; missing does not mean zero DeltaGamma.'),
        Q15=dict(assessable=True,passed=90<=cost<=150,BW20_loss_MHz=bw_cost_MHz,extra_actual_highest_peak_margin_dB=added_margin,MHz_per_dB=cost,
            caveat='Only one B1/B1R pair, central valley differs30MHz; report observed cost, not a universal slope.'),
        Q16=dict(assessable=False,passed=None,reason='W3 T4/6C not started because numerical STOP precedes them.'))
    eq=read(REPO/'experiments/fold_bandwidth_review_r12_20261115/out/S6R3_RECOMPUTED.json');eb=eq['points']['B1']['eq'];laws=eq['laws'];forward=[]
    for tr in trials:
        m=tr['measurement'];metrics=read(H/'results'/tr['case']/'review/REVIEW_STAGE3.json')['metrics']
        dp=metrics['P_eff']-eb['P_eff'];dt=1000*((metrics['fm_GHz']-metrics['fs_GHz'])-(eb['fm_GHz']-eb['fs_GHz']))
        measured_mean=(m['low_peak_dB']+m['high_peak_dB']-b['low_peak_dB']-b['high_peak_dB'])/2
        measured_tilt=(m['high_peak_dB']-m['low_peak_dB'])-(b['high_peak_dB']-b['low_peak_dB'])
        forward.append(dict(case=tr['case'],delta_P_eff=dp,detune_delta_MHz=dt,actual_mean_change_dB=measured_mean,
            frozen_law_mean_change_dB=dp*laws['mean_vs_Peff']['slope_dB_per_unit'],
            mean_residual_dB=measured_mean-dp*laws['mean_vs_Peff']['slope_dB_per_unit'],
            actual_tilt_change_dB=measured_tilt,frozen_law_tilt_change_dB=dt*laws['tilt_vs_detune']['slope_dB_per_MHz'],
            tilt_residual_dB=measured_tilt-dt*laws['tilt_vs_detune']['slope_dB_per_MHz'],
            role='R12 frozen-law forward check; equivalent parameters extracted after solve, not independent geometry prediction; no refit'))
    reqs=[read(p) for p in (ROOT/'ledger').glob('Analyze_*.json')];geoms=[read(p) for p in (ROOT/'ledger').glob('geometry_*.json')]
    cases=[f'S6R10_B1R__T{i}' for i in (1,2,3)]+[dense]
    costs={c:sum(x['case']==c for x in reqs) for c in cases}
    if len(geoms)!=4 or len(reqs)!=39 or list(costs.values())!=[10,7,10,12]:raise RuntimeError('cost mismatch')
    workers_audit=[]
    for c in cases:
        ww=case_dir(ROOT,c,cfg);rr=read(ww/'RUN_RECORD.json');pre=read(H/'validation'/c/'PASS.json')
        if not pre['passed'] or not read(ww/'evidence/design_validation/VERDICT.json')['passed']:raise RuntimeError('native validation failure')
        roles=[read(p) for p in (ww/'evidence').glob('*_role_check.json')]
        if len(roles)!=costs[c] or not all(v['passed'] for v in roles):raise RuntimeError('role/cost discrepancy')
        if not rr['cleanup']['released'] or not rr['cleanup']['scratch_restored']:raise RuntimeError('not cleaned up')
        start=read(ww/'evidence/actual_start_observed.json')
        if not start['actual_14core_1group']:raise RuntimeError('no actual14core start')
        workers_audit.append(dict(case=c,record=rr,validated_roles=len(roles),actual_start=start,preflight_Analyze=pre['new_Analyze']))
    frozen={**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}
    for rel,h in frozen.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen code/model changed '+rel)
    for path,h in cfg['historical_hashes'].items():
        if sha(path)!=h:raise RuntimeError('historical evidence changed '+path)
    for n in ('C1R','W3','W4','P1dense','P2dense','C1'):
        if (ROOT/'runs'/('S6R10_'+n)).exists():raise RuntimeError('unexpected later/cancelled input '+n)
    settings=[dict(stage=p.name.removesuffix('_settings.json'),setup=read(p)['setup'],percent=read(p)['percent'],sweep_enabled=read(p)['sweep']['IsEnabled']) for p in sorted((w/'evidence').glob('*_settings.json'))]
    for name in ('STOP.json',):shutil.copyfile(ROOT/name,out/name)
    for name in ('failure.txt','RUN_RECORD.json','cleanup.json','supervised_start.json'):
        if (w/name).exists():shutil.copyfile(w/name,out/('dense_'+name))
    for name in ('adaptive_09_settings.json','adaptive_10_settings.json','adaptive_11_settings.json'):
        v=read(w/'evidence'/name);write(out/name,{k:v[k] for k in ('setup','percent','sweep','pre_history_verified')})
    write(out/'LEDGER.json',dict(geometries=geoms,Analyze=reqs))
    write(out/'WORKER_AUDIT.json',workers_audit)
    scopekeys=['execution_revision','plan_commit','user_authorization','prior_geometry_total','prior_Analyze_total','batch_geometry_limit','total_geometry_limit','inherited_stage6_geometry','inherited_stage6_Analyze','full_stage6_geometry_limit','parent_order','cancelled_parents','case_specs','cores','tasks','serial','no_hook','technical_recovery_policy','batch_max_Analyze_from_geometry_caps','full_stage6_max_Analyze_from_geometry_caps']
    write(out/'AUTHORIZATION_SCOPE.json',{k:cfg[k] for k in scopekeys})
    report=dict(at=now(),all_R12_complete=False,R4_IR_fix_validated=True,nominal_B1R_passed=True,selected_B1R='S6R10_B1R__T3',
        statistical_RSS_robust=None,worst_corner_robust=None,stop=stop,new_geometry=4,new_Analyze=39,
        cumulative_geometry=193,cumulative_Analyze=1846,stage6_geometry=20,stage6_Analyze=213,
        per_case_Analyze=costs,stage6C_started=False,C1R_started=False,cancelled=['P1dense','P2dense','C1'],
        margin=a,trials=trials,tolerance_rows=rows,predictions=scores,two_parameter_forward_checks=forward,
        independent_raw_CSV=dict(cases=len(replays),maximum_abs_difference=maxdiff,replays=replays),
        dense_stage_settings=settings,current_native_processes=natives,current_workers=workers,
        frozen_hashes_verified=len(frozen),historical_hashes_verified=len(cfg['historical_hashes']),
        cache_project_sha256=sha(w/'model.aedt'),cache_directory_exists=True,final_dense_sweep_submitted=False,
        not_connector_or_manufacturing_certified=True)
    write(out/'REVIEW.json',report)
    def fmt(v,d=6):return '—' if v is None else f'{v:.{d}f}'
    lines=['# R12 阶段6 R4：B1R名义调准；密网格触发安全停止','',
        '## 总结',
        '**R4兼容修复已完成并在真实求解路径验证，B1R在3次内名义调准；但本轮未全部做完。** 密网格第27轮达到247,756单元，超过240,000安全上限，ΔS=0.0023507仍高于0.002；未提交最终扫频，未导出有效密网格S参数。按停止规则保留工程与缓存，停止C1R和6C，不放宽标准、不追加几何、不自动建R5。',
        '',
        '**当前只有名义仿真设计，不能标为“统计稳健”或“最坏角点稳健”。** 所有结果均不含SMA接头和实际转接反射，不能等同制造合格率、实测或全模式功率认证。',
        '',
        '累计 **193/200几何、1846次Analyze**；阶段6为20/27几何、213次请求。本R4新增4几何、39次，费用10+7+10+12；没有重复计算历史P10或任何已完成公差点。',
        '',
        '## 1. R4工具修订与冻结',
        '计划ead3d02；R4首次冻结225287a先于任何本轮Analyze。真实继承P1/P2配置走spec→make_input，完整重建fixed_milled_outline规范CAD，不只补字段；六尺寸、槽布尔盒及全对象物理包络与旧记录相同。八个新分支、正负蚀刻、旧P10拦截、预算、取消项和Ws固定a/g规则均有回归。47项修订离线回归及11项默认测试通过，默认归档8765项无错误。',
        '四个实际启动几何分别在首次Analyze前完成独立零Analyze ValidateDesign并推送输出，worker又在首次Analyze前重复原生验证。全部无error；保留材料因果性建议warning，未擅自改材料或边界。Rad1仍是air_box的Radiation，板框±15/±25mm固定，端口截断面与高度8h/宽15.04mm规则不变。',
        'R1/R2/R3的冻结、STOP、claim、marker、锁、账本均保持原字节；后验审计历史哈希'+str(len(cfg['historical_hashes']))+'项均一致。R12取消P1/P2密网格及旧C1，本轮从未创建它们的运行输入。',
        '',
        '## 2. |Γ|余量与T1求解前预测',
        '|量|冻结值|','|---|---:|',
        f"|蚀刻ΔΓ幅值|{a['dGamma']['etch']:.12f}|",f"|εr ΔΓ幅值|{a['dGamma']['er']:.12f}|",f"|h ΔΓ幅值|{a['dGamma']['h']:.12f}|",
        f"|RSS|{a['rss']:.12f}|",f"|网格增量（0.256dB）|{a['mesh']:.12f}|",f"|调参增量（0.1dB）|{a['tune']:.12f}|",
        f"|Γ_req|{a['Gamma_req']:.12f}|",f"|P_req|{a['P_req_dB']:.9f} dB|",
        f"|密网格统计判据|两内峰均≤{a['statistical_dense_dB_limit']:.9f} dB|",'',
        'h0=.813mm，tol_h=±.038mm；N0=.077535dB≤.1，不加噪声。与审核方review_s6r3.py余量结果差0dB。采用反射系数增量叠加，不使用旧dB公式或−21.8dB跳过规则。',
        'T1采用B1直测中心差分J，目标取许可区间中点−22.551839dB；Ws=.456、Lm=6.590、Ls1=12.544mm。两参数规律交叉解为.460/6.588/12.570mm，历史调参J替代解也原样冻结。与审核参考最大差.006mm；不是求解后选模型。T1是4–5步外推，后续只用冻结的有限Broyden规则。',
        '',
        '## 3. B1R三次结果与最终尺寸','|项|中央谷GHz|低内峰dB|高内峰dB|BW20 GHz|带内最差S21 dB|网格|ΔS|Analyze|名义专用判据|','|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for tr in trials:
        m=tr['measurement'];rr=tr['record'];lines.append('|'+tr['case'].split('__')[-1]+'|'+'|'.join([fmt(m['center_GHz'],2),fmt(m['low_peak_dB']),fmt(m['high_peak_dB']),fmt(m['BW20_GHz']),fmt(m['S21_min_dB']),str(rr['mesh_cells']),fmt(rr['delta_s'],7),str(rr['Analyze_requested']),'通过' if tr['nominal_robust_pass'] else '未通过'])+'|')
    lines+=['','T1峰差.259111dB，低峰未深到目标；T2高峰比许可下界−22.651839dB更深.004187dB，严格保留“未调准”，未放宽窗口。T3两峰都在区间内、峰差.097999dB、中心谷6.70GHz、S21≥−2dB，专用稳健名义判据通过。',
        '通用R7 classify针对−20.3dB等纹波规律目标，因此深纹波B1R的通用tuned=false；这不覆盖R12专用robust_nominal_pass=true。两种标签不能混用。',
        '',
        '**最终名义尺寸（mm）**：Wm=2.350，Ws=.459，Lm=6.599，Ls1=12.545，Ls2=1.468，Ls3=2.259；a=1.800、g=.550，er=3.55、h=.813、tanδ=.0027、铜厚.035。蚀刻后的形状必须用规范CAD记录，不能只靠六参数近似。',
        '![B1R T3](results/S6R10_B1R__T3/review/S11_S21.png)',
        '',
        '## 4. 密网格：明确的数值停止，不是建模或设计失败',
        '同一B1R T3几何另起独立进程和新工程，从头求解。第26轮226,858单元、ΔS=.0040312；下一轮设置PercentRefinement=5，实际第27轮247,756单元、ΔS=.0023507。细化百分比不等于实际单元数增长的硬上界，本次增长20,898（约9.21%）。冻结代码先检查24万安全上限，因此在第13次Analyze之前抛出NumericalStop。',
        '超过上限7,756单元（3.232%），而且ΔS仍未过关；即使只容忍这次网格超限，也不能据此认为数值收敛。没有用旧源工程结果或自适应单频值冒充最终宽带扫频。12次请求都是自适应段，最终Sweep1始终关闭。',
        '原生ValidateDesign、CAD包络、槽布尔盒、实际14核1组和全部12段进程角色均通过。此次不是R3元数据兼容问题复发，不是零Analyze几何相交；也不是单纯扫频超时。`SUMMARY.technical_failure=true`是收集器按failure.txt存在给出的通用标志，具体分类以RUN_RECORD.numerical_pass=false及堆栈为准。STOP内“R10数值停止”是沿用字段文字，不表示跑错计划。',
        '工程model.aedt、model.aedtresults和全部失败记录保留。清理器仅释放本案例自有AEDT、恢复scratch设置；没有清工程锁或删除缓存。停止后核验无本批worker、HFSS或hf3d。',
        '',
        '## 5. 两种稳健标注与预测评分',
        '|预测|结果|依据|','|---|---|---|',
        f"|Q21|通过|T1均值变化{actual:.6f}dB／目标{requested:.6f}dB={100*actual/requested:.3f}%，在70%–130%|",
        '|Q22|通过|调准B1R的BW20=6.131644GHz，在6.10–6.30|',
        '|Q23|不可判定|无有效密网格宽带结果，C1R未启动；不能填通过或零影响|',
        '|Q24|不可判定|缺C1R，ΔΓ幅值未测|',
        f'|Q15|不通过|实测带宽损失{bw_cost_MHz:.3f}MHz／新增最高峰余量{added_margin:.6f}dB={cost:.3f}MHz/dB，超90–150|',
        '|Q16|不可判定|6C被前序数值STOP阻止|',
        '',
        'Q21支持所选实测J的大步均值预测，但不能证明两参数拟合在深纹波处仍普适。冻结两参数规律在T1/T2/T3的均值残差为+.182/+.129/+.121dB，倾斜变化残差为−.342/−.284/−.497dB；T2/T3的倾斜变化连符号也与该式相反。残差已大于原公差拟合的.055/.12dB RMS，说明公差尺度的优秀回归不能直接当作深纹波设计的通用公式。不能把“均值命中”说成全响应一次命中。逐点数值见stop_review/REVIEW.json/two_parameter_forward_checks。等效参数来自求解后的同一条曲线，这部分不是独立的几何→响应前瞻预测；没有用新数据回改预测或重拟合。',
        'Q15只有一个B1/B1R对，中央谷还差30MHz，因此是本对点的观测价格，不是新普适斜率。Q11–Q20承接R12审核：Q11通过（浮点端点披露保留）；Q12不通过；Q13/Q14通过，Q14理由错误的修正保留；Q17–Q19通过；Q20不通过（旧dB余量−22.13在预测区间外）。',
        '**统计稳健与最坏角点稳健均为“未验证”**，不是“已经失败”或“通过”。C1R本应采用e+.01、er3.50、h.775并加本设计自身密网格向上偏差；两项证据现在都不齐，不能使用B1旧密网格偏差替代B1R的新确认。',
        '',
        '## 6. 6A公差规律汇总（继承有效观测，不复算）',
        'h是现实误差中最强的一项；薄.038mm使高峰升到−18.957dB，完整−20dB主窗消失。Ws在四种独立±.02mm平面尺寸中最敏感；Lm主要移频、Ls1主要调倾斜。最高峰在两峰切换处有拐点，余量用两侧直测，不用J硬叠加。过蚀刻P9c最高峰升.353294dB，低于Ws单项.502913dB。er3.50/3.60主要移频+30/−40MHz。',
        'h不能简单等价成微带阻抗宽度变化；R12指出槽线变比N2和失谐是更重要的解释。这是现有等效模型的证据，不是排除所有其他机理的因果证明。两参数公差规律的已有R² .983/.969及去h检验保留，但不把等效参数拟合与逆向交付认证混为一谈。',
        'P9c与旧P9两峰差−.014934/+ .045053dB，含板框和重新剖分影响；N0=.077535dB使其不能被孤立解释为边界效应。旧P9只作不同外轮廓情形归档，余量用P9c。完整线性/J比较在R3报告及本轮JSON公差明细；P13 BW20缺失仍为null，不改写为0。',
        '',
        '## 7. 预算、暂停位置与接续入口',
        '|项|几何|Analyze|','|---|---:|---:|','|继承|189|1807|','|B1R T1/T2/T3|3|27|','|B1R密网格|1|12|','|本轮新增|4|39|','|累计|193/200|1846|','|阶段6|20/27|213|',
        '',
        '本轮最多8几何，本次已用4；剩余名额只能是原定C1R、W3T4、W4最多2次，不能转给新的密网格几何或追加B1R T4。密网格同一物理几何12/20次请求已计；8次“尚未用完”不是自动恢复授权，也不能重置账本重开20次。',
        '冻结与模型：freeze/R12_R4.json、freeze_6B/R10_2.json；数值失败：stop_review/dense_failure.txt、dense_RUN_RECORD.json、STOP.json；预算：stop_review/LEDGER.json；当前状态：CURRENT_STATUS.json。实际缓存位于本机独立runtime目录，路径见RECOVERY_REQUIREMENTS.md。',
        '需要审核具体的密网格数值恢复方案与边界，再由人类明确授权；不能修改现有冻结、删除STOP、直接补扫频或擅自增大24万上限。当前ΔS不合格，直接补扫频并不能修复自适应精度。6C未测，Wm=2.50/2.65平台结论没有新证据。停止在这里，不进入阶段7。',
        '',
        f'## 8. 独立重放与证据完整性\n共{len(replays)}份原生CSV（B1、16公差点、3个B1R）独立重放，两峰/中央谷/BW20最大绝对差{maxdiff}。四个几何均实际14核、单组、串行，零Analyze预检与worker验证通过；名义三项最终扫频不改变自适应历史。冻结哈希和历史哈希全部核对一致。全部数据保持与均匀模型分离，不发hook或定时消息。']
    (H/'STOP_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (H/'RECOVERY_REQUIREMENTS.md').write_text('''# R12 R4数值停止后的审核入口（不是恢复授权）

R4元数据兼容修复有效；B1R T3已名义调准。唯一密网格确认在第27轮247,756单元、ΔS .0023507触发24万安全上限，12次Analyze，无最终扫频S参数。不是几何失败，也不是仅需补扫频的提交问题。

## 本地保留
- runtime：F:/2026-1/circuit/test/output/fig8_r12_stage6_r4_20261115
- 当前工程：runs/S6R10_B1Rdense/attempt_001/model.aedt
- 当前缓存：runs/S6R10_B1Rdense/attempt_001/model.aedtresults
- STOP、launcher_claim、preflight CLAIM、owner、input/freeze、全部证据、ledger都原样保留。
- 最后两轮：226,858/.0040312（26）→247,756/.0023507（27）；最后细化设置5%，实际单元增9.21%。

## 必须先审核
1. 先决定有限的数值恢复策略及验收范围；不改现有R4代码/输入，不删除STOP，不自动R5，不清锁。
2. 不能把现有ΔS当达标或直接只补宽带扫频；必须先满足经明确授权的自适应验收标准。
3. 任何从缓存接续都要先独立只读核对几何/材料/边界、历史和实际进程，不能假定能安全回退到某一轮或收回已用预算。
4. 已用193/200几何、1846Analyze；阶段6已用20/27、213。密网格物理几何12/20已记，剩余8请求不是恢复授权。
5. R12余下4个几何槽只能用于C1R、W3T4、W4最多2次；未用额度不转新点。若需要额外尝试/上限/设置变更，须明确审阅和授权，不偷偷借用。
6. 三个已完成B1R、16个公差点、旧基准和已闭账记录不复算。统计稳健、最坏角点稳健仍未知。
7. 收到明确恢复指令之前保持停止；不运行controller、Analyze、hook，不自动重启HFSS。阶段7未授权。
''',encoding='utf-8')
    doc=REPO/'docs/R12_EXECUTION_STOP_20261115.md'
    doc.write_text('''# R12执行回报入口

R4修复有效，B1R在3次内名义调准（BW20=6.131644GHz）；密网格247,756单元、ΔS=.0023507触发安全停止，无有效密网格扫频。C1R、6C未执行，稳健性未认证。累计193/200几何、1846次Analyze。

中文完整报告：[STOP_REPORT](../experiments/fold_bandwidth_r12_stage6_r4_20261115/STOP_REPORT.md)

审核接续边界：[RECOVERY_REQUIREMENTS](../experiments/fold_bandwidth_r12_stage6_r4_20261115/RECOVERY_REQUIREMENTS.md)

全部原冻结、STOP、锁和预算保留。此文不构成恢复授权，不自动R5或阶段7。
''',encoding='utf-8')
    print(dict(max_raw_difference=maxdiff,costs=costs,scores=scores,forward_checks=forward,frozen=len(frozen),historical=len(cfg['historical_hashes']),stopped=True))

if __name__=='__main__':build()
