"""One-shot OFFLINE R14 stage6 closeout. Never dispatches/reconnects AEDT."""
import json,math,sys
from pathlib import Path
import numpy as np
REPO=Path(__file__).resolve().parents[1]
H=REPO/'experiments/fold_bandwidth_r14_stage6_r6_20261116'
sys.path.insert(0,str(H))
from common_stage2 import read,write,sha,now,case_dir
from prepare_r10 import ROOT,INITIAL
import manage,r13,tolerance_analysis as ta

def num(x,n=6):return 'null' if x is None else f'{x:.{n}f}'
def plain(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [plain(v) for v in x]
    return x
def build():
    cfg=read(ROOT/'authorization.json')
    if (ROOT/'STOP.json').exists():raise RuntimeError('Strict STOP requires a separate stop report, not completed closeout')
    decisions={p.stem.removesuffix('_FINAL'):read(p) for p in (ROOT/'decisions').glob('*_FINAL.json')}
    if any(not decisions.get(p,{}).get('complete') for p in cfg['parent_order']):raise RuntimeError('Authorized sequence is not complete')
    import psutil
    active=[dict(pid=p.pid,name=p.info['name']) for p in psutil.process_iter(['name']) if (p.info['name'] or '').casefold() in ('ansysedt.exe','hf3d.exe')]
    if active:raise RuntimeError('Native processes still present')
    out=H/'final'
    if (out/'RESULTS.json').exists() or (out/'REPORT.md').exists():raise RuntimeError('completed report exists; no overwrite')
    out.mkdir(exist_ok=True)
    def measured(parent):
        d=decisions.get(parent)
        return manage.measurement(manage.measured_case_path(ROOT,d['selected_case'],cfg)) if d and d.get('selected_case') and not d.get('missing') else None
    nominal=measured('S6R10_B1R');dense=measured('S6R10_B1Rdense');corner=measured('S6R10_C1R')
    margin=read(H/'freeze_6B/R10_2.json')['analysis'];conf=r13.confirmation(nominal,dense,corner,margin)
    baseline=manage.baseline();ms={n:manage.measurement(manage.measured_case_path(ROOT,'S6R10_'+n+'__T1',cfg)) for n in INITIAL}
    # Reproduce side evidence without reinstating cancelled P1/P2dense or the superseded dB gate.
    linearity={k:ta.linearity(baseline,ms[p],ms[m]) for k,(p,m) in ta.PAIRS.items()}
    rises={k:max(0.,*(ta.highest(ms[x])-ta.highest(baseline) for x in pair)) for k,pair in ta.PAIRS.items()}
    differences={n:{k:ms[n].get(k)-baseline[k] if ms[n].get(k) is not None and baseline.get(k) is not None else None for k in ta.RESPONSES} for n in ms}
    old=read(REPO/'experiments/fold_bandwidth_r12_stage6_r4_20261115/stop_review/REVIEW.json')
    q={}
    for name in ('Q15','Q21','Q22'):
        # Old report retains these scored predictions; no retrospective rewriting.
        q[name]=old.get(name,old.get('predictions',{}).get(name))
    dense_high=ta.highest(dense) if dense else None
    ch=ta.highest(corner) if corner else None
    q['Q23']=dict(assessable=dense is not None and corner is not None,
        passed=(conf['statistical_without_residual'] and -20.4<=ch<=-19.6) if dense is not None and corner is not None else None,
        statistical_without_residual=conf['statistical_without_residual'],corner_highest_dB=ch)
    q['Q24']=dict(assessable=corner is not None,passed=.020<=conf['corner_minus_nominal_dGamma']<=.031 if corner else None,dGamma=conf['corner_minus_nominal_dGamma'])
    q['Q25']=dict(assessable=dense is not None,
        passed=(-22.34<=dense_high<=-22.06 and .0015<=conf['own_nonnegative_mesh_dGamma']<=.004 and conf['statistical_label']=='统计稳健（不含网格残差，边缘）') if dense else None,
        highest_dB=dense_high,own_delta=conf['own_nonnegative_mesh_dGamma'],label=conf['statistical_label'])
    q['Q26']=dict(assessable=dense is not None,passed=6.66<=dense['center_GHz']<=6.70 if dense else None,center_GHz=dense['center_GHz'] if dense else None)
    w3=measured('S6R10_W3');w4=measured('S6R10_W4');usable3=decisions['S6R10_W3'].get('passed',False)
    q['Q16']=dict(assessable=bool(usable3),passed=6.90<=w3['BW15_star_GHz']<=6.99 if usable3 else None,
        BW15_star_GHz=w3['BW15_star_GHz'] if w3 else None,
        conclusion=('2.5mm以内仍不弯' if w3['BW15_star_GHz']>=7 else '落入6.90–6.99GHz预测区间' if w3['BW15_star_GHz']<=6.99 and w3['BW15_star_GHz']>=6.9 else '区间外，不能事后改阈值') if usable3 else 'W3不可用，平台不可判')
    f=read(H/'freeze/R10_1.json')
    platform={n:dict(measurement=measured('S6R10_'+n),decision=decisions['S6R10_'+n]) for n in ('W3','W4')}
    platform_slopes=dict(previous_frozen_linear_GHz_per_mm=1.1678210578,
        B1_W3_GHz_per_mm=(w3['BW15_star_GHz']-baseline['BW15_star_GHz'])/.15 if usable3 else None,
        W3_W4_GHz_per_mm=(w4['BW15_star_GHz']-w3['BW15_star_GHz'])/.15 if usable3 and decisions['S6R10_W4'].get('passed') else None,
        caution='Normalized BW15*, not BW20; a finite pairwise slope is not a universal asymptote or complete plateau.')
    platform_trials=[]
    for case,spec in cfg['case_specs'].items():
        if spec['parent_id'] not in ('S6R10_W3','S6R10_W4'):continue
        w=case_dir(ROOT,case,cfg)
        if not (w/'review/visual_ack.json').exists():continue
        actual=manage.measurement(w);design=read(w/'input/freeze.json')['design'];raw_pred=design.get('prediction',{})
        # W3's inherited Broyden prediction is a [valley,D,L] list; W4 uses a named object.
        pred=dict(response_y=raw_pred) if isinstance(raw_pred,list) else raw_pred
        platform_trials.append(dict(case=case,data_role=design['data_role'],actual=actual,frozen_prediction=raw_pred,
            predicted_y=pred.get('response_y',[pred.get('central_valley_GHz'),pred.get('D_dB'),pred.get('L_dB')]),
            measured_y=[actual['center_GHz'],actual['high_peak_dB']-actual['low_peak_dB'],(actual['high_peak_dB']+actual['low_peak_dB'])/2],
            BW15_star_primary_residual_MHz=1000*(actual['BW15_star_GHz']-pred['BW15_star_primary_linear_GHz']) if 'BW15_star_primary_linear_GHz' in pred else None,
            BW15_star_alternative_residual_MHz=1000*(actual['BW15_star_GHz']-pred['BW15_star_quadratic_alternative_GHz']) if 'BW15_star_quadratic_alternative_GHz' in pred else None))
    budget=manage.status(ROOT)
    # All immutable inputs and previous histories must still match after native work.
    for rel,h in {**cfg['code_hashes'],**cfg['frozen_hashes'],**cfg['plan_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('Frozen hash mismatch '+rel)
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('Historical hash mismatch '+p)
    r13.audit_cache_files(r13.SOURCE,cfg)
    result=dict(at=now(),nominal=nominal,dense=dense,C1R=corner,confirmation=conf,margin=margin,
        baseline=baseline,stage6A=ms,differences_vs_B1=differences,linearity=linearity,sensitivity_peak_rise_dB=rises,
        conservative_linear_margin_dB=sum(rises[k] for k in ('Ws','Lm','Ls1','Wm','er','h')),
        predictions=q,platform=platform,platform_slopes=platform_slopes,platform_trials_and_frozen_predictions=platform_trials,prior_R12_scientific_review=old,budget=budget,
        no_native_processes=True,all_frozen_and_historical_hashes_verified=True,source_cache_file_count=597,
        runtime_self_fixes=[],unused_self_fix_allowance_not_reused=True,stage7_authorized=False)
    write(out/'RESULTS.json',plain(result))
    rows=['# R14：阶段6收尾报告','',
        '## 总结','',f"已按R14完成有限R6修复和R13规定的三步流程（6C按可用性门槛执行/跳过）。统计标注：**{conf['statistical_label']}**；联合角点：**{conf['worst_corner_label']}**。",
        f"本轮新增{budget['R6_new_geometries']}个几何、{budget['R6_actual_Analyze']}次Analyze；累计{budget['geometry_total']}/200几何、{budget['actual_Analyze_total']}次Analyze。阶段6累计{budget['R10_geometries']}/27几何、{budget['R10_actual_Analyze']}次Analyze。已停止；不进入阶段7。",
        '', '## 1. 工具修复、验证与运行口径','',
        'R6冻结提交b397e33。只修观察器导入路径，capture函数AST与R5相同。10个入口×2种cwd的新解释器隔离导入、实际观察器ready/stop空跑均通过；R5失败复现和R6通过证据均保留。55项R5回归、55项R6回归、默认11项及8765归档文件校验通过。',
        '首次未发布测试有两个适配问题：Windows venv启动器与真实解释器PID不同，现按创建时间和祖先链验证；默认测试需原有sklearn依赖路径，已恢复该测试环境。原失败输出保留。这些不是HFSS求解恢复。发布后的运行中自行修复0次，无求解重试。',
        '原R4的597文件缓存重新复制，R5已打开副本未复用；新副本原生CAD、材料、端口、Rad1和全部27行历史核验通过。密网格只补1次扫频，同一物理几何12→13/20，新增自适应0轮；247756单元/ΔS=.0023507保持不变。观察到31个14核1组扫频角色，不是31次Analyze。',
        'C1R及后续每个新几何均先零Analyze原生ValidateDesign并推送；普通网格与每几何预算未改。14核1组串行，无hook、无新增直接频点。R1–R5不改、不删，源缓存及冻结/历史哈希复核一致。',
        '', '## 2. B1R交付与确认','',
        '名义尺寸(mm)：Wm=2.350，Ws=0.459，Lm=6.599，Ls1=12.545，Ls2=1.468，Ls3=2.259；a=1.8，g=.55。名义εr=3.55、h=.813、tanδ=.0027、铜厚=.035。C1R是在这套几何上联合施加真实铜边e=+.01mm、εr=3.50、h=.775mm；板框和端口截断面不动，端口高度8h、宽15.04mm。',
        '|项目|中央谷 GHz|低内峰 dB|高内峰 dB|BW20 GHz|BW20内最差S21 dB|','|---|---:|---:|---:|---:|---:|']
    for name,m in [('B1基准',baseline),('B1R名义T3',nominal),('B1R密网格',dense),('C1R',corner)]:
        rows.append('|'+name+'|'+('|'.join(num(m.get(k)) for k in ta.RESPONSES) if m else '未测|未测|未测|未测|未测')+'|')
    rows+=['',f"统计阈值Γ_stat={conf['Gamma_stat']:.12f}；Γ_dense={num(conf['Gamma_dense'],12)}，加入残差.0023507后={num(conf['Gamma_dense']+.0023507 if dense else None,12)}。不含残差通过={conf['statistical_without_residual']}；含残差通过={conf['statistical_with_residual']}。这不是自适应收敛证明。",
        f"自身网格偏差δ_mesh=max(0,Γ_dense−Γ_T3,max)={num(conf['own_nonnegative_mesh_dGamma'],12)}。C1R的Γ={num(conf['Gamma_C1R'],12)}，加偏差后={num(conf['corner_Gamma_plus_bias'],12)}，要求≤0.1。",
        f"密网格两峰变化(dB)：{conf['dense_minus_T3_peak_dB']}；对应ΔΓ：{conf['dense_minus_T3_peak_dGamma']}。中央谷是否在6.69–6.75GHz：{6.69<=dense['center_GHz']<=6.75 if dense else '未知'}，不为此追加T4。",
        f"联合角点C1R−名义B1R的ΔΓ={num(conf['corner_minus_nominal_dGamma'],12)}；三项单独扰动线性和={sum(margin['dGamma'].values()):.12f}，RSS={margin['rss']:.12f}。不把RSS当制造良率概率，不把本角点当全参数域的数学最坏点。",
        'BW20为围绕指定中央谷的完整主窗；消失时写null，不拼接小窗口。S21列仅为BW20内离散样本，不混用BW15或其他窗口。名义/插值通过不等于制造保证。',
        '', '## 3. 6A公差直测回顾','',
        '|点|中央谷 GHz|低内峰 dB|高内峰 dB|BW20 GHz|最差S21 dB|','|---|---:|---:|---:|---:|---:|']
    for n,m in ms.items():rows.append('|'+n+'|'+'|'.join(num(m.get(k)) for k in ta.RESPONSES)+'|')
    rows+=['','各点相对B1的完整差分及逐指标非线性判定见RESULTS.json。规则不变：|Δ+ + Δ−| > 0.5|Δ+ − Δ−|记明显非线性；有null不评分。后续余量使用两侧直测，不用J替代。P9c替代板框偏置不合规则的旧P9；不把旧P9合入新公差估计。',
        '最高内峰升幅排名：'+ ' > '.join(f'{k} {v:.6f}dB' for k,v in sorted(rises.items(),key=lambda x:-x[1]))+'。',
        f"现实来源蚀刻/εr/h：ΔΓ={margin['dGamma']}；RSS={margin['rss']:.12f}；Γ_req={margin['Gamma_req']:.12f}，P_req={margin['P_req_dB']:.6f}dB。保守独立尺寸/εr/h线性相加升幅={result['conservative_linear_margin_dB']:.6f}dB，仅报告、不作为本轮设计目标。",
        'P1/P2密网格和原C1已由R12取消，本轮没有重启。N0噪声约.0775dB，低于.1dB噪声追加线，不增余量。',
        '', '## 4. 6C与预测评分','',
        '|设计|规律可用|两内峰均≤−20dB|中央谷 GHz|BW15* GHz|BW20 GHz|','|---|---|---|---:|---:|---:|']
    for n in ('W3','W4'):
        d=platform[n]['decision'];m=platform[n]['measurement'];rows.append(f"|{n}|{d.get('passed',False)}|{ta.highest(m)<=-20 if m else '未知'}|{num(m['center_GHz']) if m else '跳过/缺失'}|{num(m['BW15_star_GHz']) if m else 'null'}|{num(m['BW20_GHz']) if m else 'null'}|")
    rows+=['',f"Q16：{q['Q16']['conclusion']}。W3是T1–T3之后的调参T4，不是独立盲测；W4首次候选才是冻结前瞻点，后续修改属于调参。不可用点不纳入带宽平台拟合。",
        f"归一化BW15*的有限差分斜率：B1(2.35mm)→W3(2.50mm)={num(platform_slopes['B1_W3_GHz_per_mm'])}GHz/mm；W3→W4(2.65mm)={num(platform_slopes['W3_W4_GHz_per_mm'])}GHz/mm。原冻结线性斜率1.167821GHz/mm。斜率减小只说明该区间增益减缓，不等于已经完全饱和；不拿BW20与BW15*混比。",
        '本轮W4 T1即通过，未创建/派发T2。W3→W4的增益仍明显，且局部斜率高于B1→W3，因此不能宣称“斜率单调下降”或“2.65mm已到平台”。',
        '各次候选的冻结预测、[中央谷,D,内峰均值]实测与数据角色详见RESULTS.json/platform_trials_and_frozen_predictions。T1目标参数拟合不是独立的全响应代理模型，不把给定目标当作已被证明的全响应预测。',
        '|预测|评分|证据|','|---|---|---|',
        '|Q11|通过，保留浮点端点披露|高峰中心差分和Lm移频量级，继承R12审核|',
        '|Q12|不通过|实际蚀刻最高内峰损伤小于单改Ws|',
        '|Q13/Q14|通过|εr主要移频；h是现实三项中主导来源|',
        '|Q15|不通过|B1→B1R名义约177.53MHz/dB，不在90–150|',
        '|Q21/Q22|通过|J大步均值达到目标99.8%；B1R名义BW20=6.1316GHz|']
    for k in ('Q16','Q23','Q24','Q25','Q26'):
        d=q[k];rows.append('|'+k+'|'+('不可判' if not d['assessable'] else '通过' if d['passed'] else '不通过')+'|'+json.dumps(plain(d),ensure_ascii=False)+'|')
    rows+=['', '## 5. 规律的适用范围与实物含义','',
        '两参数P_eff/失谐规律只在公差尺度的小扰动成立：原局部R²约.983/.969，适合公差估计、微调；不是一步完成深纹波大幅逆向设计的通用公式。B1R T1–T3均值残差+.18/+.13/+.12dB、倾斜残差−.34/−.28/−.50dB，T2/T3倾斜变化符号也与该式不同。大改动依靠实测J外推和有限Broyden修正，不用这些新数据事后改原预测。',
        '名义B1→B1R最高内峰加深1.821dB，BW20减少323.28MHz（约5%）；这一个点对且中央谷不同，不能据此宣称普适178MHz/dB斜率。',
        '若要在本轮两套尺寸中选更有反射余量的名义加工起点，可用B1R T3，但必须连同上面的统计边缘/角点标签交付，不能称为全公差保证。模型不含SMA接头，实物会叠加连接器与转接反射。板厚是主导误差；取得板厂或实测h0/tol_h后，可用P13/P14直测灵敏度离线重估余量，无需为这一步线性估算新增仿真，但该估算不是新的制造认证。',
        '', '## 6. 停止与归档','',
        '本轮已到有限流程末尾，全部自有worker/HFSS退出、scratch还原；没有定时任务或hook继续派发。不自动建立R7、不进入阶段7，剩余额度不转作新授权。',
        '原生曲线、独立提取、实际看图ACK、角色证据、CAD/验证及预算均在本目录results/、validation/、pre_solve/及final/。运行中工具补丁恢复列表为空；没有改变判据或掩盖失败。']
    (out/'REPORT.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    # Static scientific plots from actual native curves only.
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(2,1,figsize=(10,8),sharex=True)
    sources=[('B1',manage.OLD/'results/S5R9_B1__T2'),('B1R T3',manage.measured_case_path(ROOT,'S6R10_B1R__T3',cfg))]
    for p,label in [('S6R10_B1Rdense','B1R dense'),('S6R10_C1R','C1R')]:
        if decisions[p].get('selected_case'):sources.append((label,case_dir(ROOT,decisions[p]['selected_case'],cfg)))
    for label,path in sources:
        z=np.load(path/'native/full_modes.npz',allow_pickle=False)
        for a,col in zip(ax,(0,2)):a.plot(z['f_GHz'],20*np.log10(np.maximum(abs(z['S'][:,col,0]),1e-15)),label=label)
    ax[0].axhline(-20,color='gray',ls='--');ax[1].axhline(-2,color='gray',ls='--')
    ax[0].set(ylim=(-40,-15),ylabel='S11 (dB)');ax[1].set(ylim=(-2.5,0),ylabel='S21 (dB)',xlabel='Frequency (GHz)',xlim=(3,10))
    for a in ax:a.grid(alpha=.25);a.legend()
    fig.tight_layout();fig.savefig(out/'DELIVERY_CURVES.png',dpi=150);plt.close(fig)
    print(json.dumps(dict(budget=budget,confirmation=conf,predictions=q),ensure_ascii=False,default=str))
if __name__=='__main__':build()
