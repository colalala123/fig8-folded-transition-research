"""R15 final offline report. Does not connect AEDT or dispatch work."""
import json,sys,math
from pathlib import Path
import numpy as np
REPO=Path(__file__).resolve().parents[1];H=REPO/'experiments/fold_bandwidth_r15_stage7_r7_20261116'
sys.path.insert(0,str(H))
from common_stage2 import read,write,sha,now,case_dir
from prepare_r10 import ROOT
import stage7,manage

def plain(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [plain(v) for v in x]
    return x

def build():
    import psutil
    cfg=read(ROOT/'authorization.json');fz=read(H/'freeze/R15_R7.json');old=read(stage7.PRIOR_H/'final/RESULTS.json')
    if (ROOT/'STOP.json').exists():raise RuntimeError('strict STOP: use separate fault report')
    dec={p:read(ROOT/'decisions'/(p+'_FINAL.json')) for p in cfg['parent_order']}
    if not all(d['complete'] for d in dec.values()):raise RuntimeError('not complete')
    assert not [p for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe')]
    def measured(p):
        d=dec[p]
        if d.get('missing'):return d.get('measurement')
        return manage.measurement(case_dir(ROOT,d['selected_case'],cfg))
    n=measured('S7R15_W4R');c=measured('S7R15_C1W');d=measured('S7R15_W4Rdense')
    dc=dec['S7R15_W4Rdense'].get('selected_case');record=read(case_dir(ROOT,dc,cfg)/'RUN_RECORD.json') if dc else None
    residual=record['delta_s'] if d else None
    conf=stage7.confirmation(n,d,c,residual,fz['margin']);nominal_pass=dec['S7R15_W4R'].get('passed',False)
    q={}
    q['Q27']=dict(assessable=bool(nominal_pass and n),passed=bool(6.20<=n['BW20_GHz']<=6.40 and n['BW20_GHz']>old['nominal']['BW20_GHz']) if nominal_pass and n else None,BW20_GHz=n.get('BW20_GHz') if n else None)
    delta=conf['corner_minus_nominal_dGamma'];q['Q28']=dict(assessable=delta is not None,passed=.022<=delta<=.032 if delta is not None else None,dGamma=delta)
    selected=dec['S7R15_W4R']['selected_case'];ordinal=cfg['case_specs'][selected]['attempt_ordinal']
    q['Q29']=dict(assessable=not dec['S7R15_W4R'].get('missing',False),passed=bool(nominal_pass and ordinal<=3) if not dec['S7R15_W4R'].get('missing',False) else None,selected_ordinal=ordinal,nominal_tuned=nominal_pass)
    shifts=conf['dense_peak_changes_dGamma'];shift=conf['dense_center_shift_MHz']
    q['Q30']=dict(assessable=bool(n and d),passed=bool(-30-1e-7<=shift<=-10+1e-7 and .0015<=shifts['high_peak_dB']<=.004 and abs(shifts['low_peak_dB'])<abs(shifts['high_peak_dB'])) if n and d else None,center_shift_MHz=shift,peak_changes_dGamma=shifts)
    trials=[]
    for case,s in cfg['case_specs'].items():
        w=case_dir(ROOT,case,cfg)
        if not (w/'RUN_RECORD.json').exists():continue
        rec=read(w/'RUN_RECORD.json');f=read(w/'input/freeze.json');trial=dict(case=case,record=rec,geometry_mm=f['design']['geometry_mm'],data_role=f['design']['data_role'])
        if (w/'review/visual_ack.json').exists():
            m=manage.measurement(w);raw=read(w/'review/extraction_R2.json');pr=f['design'].get('prediction',{})
            trial.update(measurement=m,nominal_check=stage7.nominal_check(raw,fz['margin']['P_req_dB'],m.get('S21_min_dB')) if s['parent_id']=='S7R15_W4R' else None,frozen_prediction=pr)
            if pr and pr.get('response_y'):
                y=[m['center_GHz'],m['high_peak_dB']-m['low_peak_dB'],(m['high_peak_dB']+m['low_peak_dB'])/2];trial['response_minus_prediction']=[v-u for v,u in zip(y,pr['response_y'])]
        trials.append(trial)
    before=dict(geometries=196,Analyze=1880);newg=len(list((ROOT/'ledger').glob('geometry_*.json')));newa=len(list((ROOT/'ledger').glob('Analyze_*.json')))
    assert newg<=6 and 196+newg<=202 and newa<=90
    for rel,h in {**cfg['code_hashes'],**cfg['frozen_hashes'],**cfg['plan_hashes']}.items():assert sha(REPO/rel)==h,rel
    for p,h in cfg['historical_hashes'].items():assert sha(p)==h,p
    b1dense_path=REPO/'experiments/fold_bandwidth_r9_stage5_20261114/results/S5R9_B1dense__T1'
    b1dense=manage.measurement(b1dense_path)
    outcome=dict(at=now(),nominal=n,C1W=c,dense=d,nominal_tuned=nominal_pass,confirmation=conf,predictions=q,trials=trials,
        margin=fz['margin'],dense_record=record,selected_geometry_mm=read(case_dir(ROOT,selected,cfg)/'input/freeze.json')['design']['geometry_mm'],
        budget=dict(prior=before,new_geometries=newg,new_Analyze=newa,cumulative_geometry=196+newg,cumulative_Analyze=1880+newa,geometry_cap=202),
        former_comparisons=dict(B1=old['baseline'],B1dense=b1dense,B1R=old['nominal'],B1Rdense=old['dense'],C1R=old['C1R'],W4=old['platform']['W4']['measurement']),
        full_R14_report_remains_authoritative_for_stage6=True,all_frozen_historical_hashes_verified=True,
        runtime_self_fixes=[],not_connector_or_manufacturing_certified=True,no_stage8=True)
    out=H/'final';out.mkdir(exist_ok=False);write(out/'RESULTS.json',plain(outcome))
    fmt=lambda x:'null' if x is None else f'{x:.6f}'
    rows=['# R15：阶段7 W4R稳健交付报告','','## 总结','',f"有限流程已完成。名义调准：{nominal_pass}；密网格：**{conf['statistical_label']}**；联合角点：**{conf['worst_corner_label']}**。",f"新增{newg}/6几何、{newa}次Analyze；累计{196+newg}/202几何、{1880+newa}次Analyze。14核1组串行。做完停止，不进入阶段8。",'',
        '## 1. 冻结与执行','',
        'R7冻结提交f52cc0c；R1–R6不改。观察器继承R14修复，R6原55项、R7新34项、默认11项、8765文件归档和20次独立解释器导入/2次观察器空跑通过。每个新点先零Analyze原生ValidateDesign并推送，再发布绑定后启动；逐点独立看图ACK。',
        f"默认h0=.813mm、tol_h=.038mm、角点档。Γ_req={fz['margin']['Gamma_req']:.9f}，P_req={fz['margin']['P_req_dB']:.9f}dB，目标中央谷6.72–6.75GHz，纹波窗[P_req−.2,P_req]。S21以完整BW20主窗的原生样本最小值验收。",'未选用的±.025mm角点表项与公式差.005221dB，已在冻结披露；默认行误差.003558dB满足计划精度。用户随后明确确认“以公式为准，披露差异并继续默认输入”，见USER_CLARIFICATION_P_REQ.json；没有回写旧冻结或更改参数/预算。',
        'T1同时冻结B1实测中心差分J与邻近W3 Broyden代理J的解，选择前者。W4没有独立局部扰动J，未冒称实测W4 J。T2–T4采用原有限Broyden。候选均是调参数据，不是新的独立盲测集。',
        '', '## 2. 交付对比','', '|设计|中央谷 GHz|低峰 dB|高峰 dB|BW20 GHz|BW20内最差S21 dB|','|---|---:|---:|---:|---:|---:|']
    comparison=[('B1名义',old['baseline']),('B1密网格',b1dense),('B1R名义',old['nominal']),('B1R密网格',old['dense']),('B1R角点C1R',old['C1R']),('W4名义',old['platform']['W4']['measurement']),('W4R名义',n),('W4R角点C1W',c),('W4R密网格',d)]
    for label,m in comparison:rows.append('|'+label+'|'+('|'.join(fmt(m.get(k)) for k in ['center_GHz','low_peak_dB','high_peak_dB','BW20_GHz','S21_min_dB']) if m else '未完成|未完成|未完成|null|null')+'|')
    rows+=['','B1角点C1已按R12取消，无直测值；B1名义和密网格仅名义−20dB通过，现实公差余量不足。B1R旧密网格和角点标注以R14报告为准：B1R统计边缘通过、最坏角点不满足。W4没有单独密网格/角点结果，不用W4R结果冒充W4认证。',
        'W4R最终尺寸(mm)：'+json.dumps(outcome['selected_geometry_mm'],ensure_ascii=False)+'；名义a=1.8、g=.55。',
        '', '## 3. 角点与密网格判定','',
        'C1W在选定W4R上施加e=+.01mm、εr=3.50、h=.775mm；板框和端口截断面不动，高度8h、宽15.04mm。',
        '密网格重新自适应；200k且ΔS<=.002即可扫频，220k强制转扫频并计残差，>300k严格停止。实际原生历史、计费和角色见逐点记录；强制转扫频不是收敛证书。',
        '统计分档：Γ_dense+实测ΔS<=Γ_stat为含残差通过；只满足Γ_dense<=Γ_stat为边缘档；否则不满足。Γ_stat=.1−RSS。',
        '对照文件中的design_pass/nominal_check是名义调准条件（中心和等纹波），不等于公差稳健判定；C1W与密网格的最终标注只按本节Γ域条件计算。',
        '角点要求Γ_C1W+δ_mesh,W4R<=.1；自身偏差=max(0,Γ_dense−Γ_nominal,max)，缺失时仅借用B1R的.002538并注明未经本设计确认。',
        '数值判定：\n\n```json\n'+json.dumps(plain(conf),ensure_ascii=False,indent=2)+'\n```',
        '', '## 4. 调参与预测评分','', '|尝试|中央谷 GHz|低峰 dB|高峰 dB|BW20 GHz|R15调准|','|---|---:|---:|---:|---:|---|']
    for t in trials:
        if not t['case'].startswith('S7R15_W4R__'):continue
        m=t.get('measurement');rows.append('|'+t['case']+'|'+('|'.join(fmt(m.get(k)) for k in ['center_GHz','low_peak_dB','high_peak_dB','BW20_GHz']) if m else '未完成|未完成|未完成|null')+'|'+str(t.get('nominal_check',{}).get('tuned',False))+'|')
    rows+=['','原文Q27–Q30保存在freeze/R15_R7.json。未调准的候选不能拿来证明“调准W4R”的Q27。', '|预测|评分|数值|','|---|---|---|']
    for key,v in q.items():rows.append('|'+key+'|'+('不可判' if not v['assessable'] else '通过' if v['passed'] else '不通过')+'|'+json.dumps(plain(v),ensure_ascii=False)+'|')
    rows+=['','所有候选的冻结预测、实测和残差见RESULTS.json/trials；保留未达标记录，不改原预测。','','## 5. 带宽规律与加工推荐','',
        '6C表明Wm从2.35→2.50→2.65mm，归一化BW15*局部斜率约.918和1.076GHz/mm，尚不能宣称平台。稳健纹波加深损失BW20；加宽Wm带来的增益与该损失必须分别比较，不混用BW15*。']
    if n and n.get('BW20_GHz'):
        loss=old['platform']['W4']['measurement']['BW20_GHz']-n['BW20_GHz'];gain=n['BW20_GHz']-old['nominal']['BW20_GHz'];rows.append(f'W4→W4R的BW20损失{loss*1000:.3f}MHz；W4R相对B1R名义BW20增益{gain*1000:.3f}MHz。这是本轮有限点对，不是普适MHz/dB常数。')
    recommended=bool(nominal_pass and conf['worst_corner_robust'] and conf['statistical_label']=='统计稳健（含网格残差）')
    rows.append('推荐以本轮W4R选定版本作为名义加工起点，并附带全部公差与网格证据。' if recommended else '目前不能把W4R称作同时满足全部稳健条件的制造保证；应保留上面的分档与未满足项，不能仅凭名义通过推荐为全公差达标件。')
    rows+=['结果不含SMA接头，板厚仍是主导误差；即使本轮角点通过也只是已建模范围内的仿真证据，不是制造良率认证。',
        '', '## 6. 后续实测板厚如何离线更新','',
        '取得h0/tol_h后，先按P13/P14分别在Γ域计算两侧斜率（以各自实测减B1除以±.038），不要把中心频率和峰高混用；围绕.813用对应侧估算名义厚度偏移，再按tol_h缩放h项。当前角点ΔΓ中扣除旧h项.020355，加入新h项；蚀刻/εr项保留。统计档则对现实三项重算RSS。结合本次C1W−W4R实测ΔΓ对跨设计灵敏度转移作校验，记录不一致量。',
        '然后重算Γ_req、P_req以及现有设计余量，只做离线估算，不自动新增仿真；超出已测h区间或明显非线性时标注外推，不当作制造认证。',
        '', '## 7. 停止与交付','', '原生曲线、校验、实际看图ACK、逐次Analyze与冻结均已归档。本轮运行中技术自修复次数为0；若发生异常，必须以真实单独故障报告为准。剩余预算不是新授权；不自动进入阶段8。']
    (out/'REPORT.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(2,1,figsize=(10,8),sharex=True)
    sources=[('W4',stage7.PRIOR_H/'results/S6R10_W4__T1')]
    for p,label in [('S7R15_W4R','W4R'),('S7R15_C1W','C1W'),('S7R15_W4Rdense','W4R dense')]:
        if not dec[p].get('missing'):sources.append((label,case_dir(ROOT,dec[p]['selected_case'],cfg)))
    for label,path in sources:
        z=np.load(path/'native/full_modes.npz',allow_pickle=False)
        for a,col in zip(ax,(0,2)):a.plot(z['f_GHz'],20*np.log10(np.maximum(abs(z['S'][:,col,0]),1e-15)),label=label)
    ax[0].axhline(-20,color='gray',ls='--');ax[1].axhline(-2,color='gray',ls='--');ax[0].set(ylim=(-40,-15),ylabel='S11 (dB)');ax[1].set(ylim=(-2.5,0),ylabel='S21 (dB)',xlabel='Frequency (GHz)',xlim=(3,10))
    for a in ax:a.grid(alpha=.25);a.legend()
    fig.tight_layout();fig.savefig(out/'CURVES.png',dpi=150);plt.close(fig)
    print(json.dumps(plain(dict(budget=outcome['budget'],nominal_tuned=nominal_pass,confirmation=conf,predictions=q)),ensure_ascii=False))
if __name__=='__main__':build()
