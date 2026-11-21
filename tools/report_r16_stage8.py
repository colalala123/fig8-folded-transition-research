"""Write a Chinese stage-8 report from finished decisions. Pure postprocessing."""
import argparse,json
import analyze_r16_stage8 as A
from analyze_r16_stage8 import H,ROOT,read
from pathlib import Path
F=H/'final'
def fmt(v,n=3):return '—' if v is None else f'{v:.{n}f}'
def yes(v):return '不可判' if v is None else ('通过' if v else '不通过')
def band(g):
    if not g:return '不可判'
    if g.get('empty'):return '空集（0 GHz）'
    return f"{fmt(g['low_GHz'])}–{fmt(g['high_GHz'])}（宽 {fmt(g['width_GHz'])}）"
def table(cols,rows):
    return ['|'+'|'.join(cols)+'|','|'+'|'.join(['---']*len(cols))+'|']+['|'+'|'.join(str(k).replace('|',r'\|') for k in r)+'|' for r in rows]
def label(n):return {'dense':'W4R 密网格','W4R':'W4R 名义'}.get(n,n)
def vals(m):return [fmt((m or {}).get(k)) for k in ('center_GHz','low_peak_dB','high_peak_dB','BW20_GHz','S21_min_dB')]
def write_x(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def draw(s):
    import matplotlib
    matplotlib.use('Agg');import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    import numpy as np
    fig,axes=plt.subplots(3,1,figsize=(10.5,10),gridspec_kw={'height_ratios':[1.3,1,.8]},layout='constrained')
    ax,at,ab=axes;g=s['guarantee'];e=s['five']
    names=['W4R','dense','C1W','C2W','C3W'];sources={k:p for k,(p,_) in A.stage8.ANCHORS.items()}
    for k in ('C2W','C3W'):
        d=s['decisions'][k]
        if d.get('selected_case'):sources[k]=H/'results'/d['selected_case']
    colors=dict(zip(names,['#192934','#756bb1','#c05a16','#0072B2','#008877']))
    for j,n in enumerate(names):
        if n not in sources:continue
        with np.load(sources[n]/'native/full_modes.npz',allow_pickle=False) as z:
            freq=z['f_GHz']
            for axx,col in [(ax,0),(at,2)]:axx.plot(freq,20*np.log10(np.maximum(abs(z['S'][:,col,0]),1.e-15)),label=n,c=colors[n],lw=1.5,ls='--' if n=='dense' else '-')
        edge=(e[n] or {}).get('edges20')
        if edge:ab.plot([edge['low_GHz'],edge['high_GHz']],[j,j],c=colors[n],lw=2,marker='|',ms=11)
    if g and not g['empty']:
        for a in axes:a.axvspan(g['low_GHz'],g['high_GHz'],color='#91c08e',alpha=.12)
        ab.plot([g['low_GHz'],g['high_GHz']],[5,5],lw=4,c='#242424',marker='|')
    ab.set_yticks(range(6),['W4R','dense','C1W','C2W','C3W','intersection'])
    ax.set(ylabel='S11 (dB)',ylim=(-40,-12),title='W4R: five simulated main windows');ax.axhline(-20,color='gray',ls=':')
    at.set(ylabel='S21 (dB)',ylim=(-3,0));at.axhline(-2,color='gray',ls=':')
    ab.set(xlabel='Frequency (GHz)');ax.legend(ncols=5,loc='lower center',fontsize=8)
    for a in axes:a.grid(alpha=.22);a.set_xlim(3,10.1)
    fig.savefig(F/'CURVES.png',dpi=125);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4.8),layout='constrained')
    ax,ag=axes
    for k,n,cl in [('nominal_curve','Nominal (~ -20.3 dB)','#0072B2'),('robust_curve','Robust (common P_req)','#c05a16')]:
        data=s[k];xs=[r['Wm'] for r in data];ys=[r['BW20_GHz'] for r in data]
        ax.plot(xs,ys,'-',color=cl,lw=1.6,label=n)
        for x,y,r in zip(xs,ys,data):ax.plot(x,y,'o',mfc=cl if r['measured'] else 'white',mec=cl);ax.annotate(r['design'],(x,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
    ax.plot([],[],'o',mfc='white',mec='gray',label='W4R: adjusted, not re-solved');ax.set(xlabel='Wm (mm)',ylabel='BW20 (GHz)',title='Tuned geometries only');ax.margins(.14,.24);ax.legend(fontsize=8)
    for name,x in [('B1R',2.35),('W4R',2.65),('W5R',2.8),('W6R',2.95)]:
        y=s['dGamma'][name]
        if y is not None:ag.plot(x,y,'o',color='#008877');ag.annotate(name,(x,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
    ag.set(xlabel='Wm (mm)',ylabel='Corner minus nominal peak |Gamma|',title='Measured C1 differences');ag.margins(.2,.35)
    for a in axes:a.grid(alpha=.25);a.xaxis.set_major_locator(MaxNLocator(nbins=6))
    fig.savefig(F/'WIDTH_LAW.png',dpi=140);plt.close(fig)

def render(s):
    g=s['guarantee'];b=s['budget'];d=s['decisions'];n=s['nominal'];rr=s['residuals'];ctr=s['corner'];cm=s['corner_measurements'];new=s['margin']['P_req_dB']
    lines=['# Fig. 8 弯折过渡：阶段 8 交付报告（R16）','','## 结论','',
    f"**W4R 五条 HFSS 曲线的 −20 dB 交集：{band(g)} GHz。** "+(f"低端由 {label(g['lower_limiter'])} 限定，高端由 {label(g['upper_limiter'])} 限定；两个新角点的四个带边相对冻结线性预测最大偏差 {max(abs(v) for k in ('C2W','C3W') for v in rr[k]['residual_MHz'] if v is not None):.1f} MHz。" if g and not g['empty'] else '没有可报告的完整非空五曲线交集。'),
    f"**建议加工起点：{s['recommend']}。** "+('W4R 有自己的密网格和三种联合角点证据。' if s['recommend']=='W4R' else '这版名义调准、比 W4R 更宽，实测 C1 加借用的网格偏差仍通过；没有自身密网格，保证带只能估算。'),
    f"本轮占用 {b['new_geometries']}/10 个几何尝试槽，其中 {b['distinct_simulated_configurations']} 种不同的 HFSS 配置；{b['new_Analyze']}/140 次实际 Analyze。累计计费 {b['cumulative_geometries']}/212 个几何槽、{b['cumulative_Analyze']} 次实际 Analyze。未用额度不另作新授权。",'',
    '## 1　−20 dB 带边与五曲线交集','',
    '带边是在 dB 域线性插值得到的、包含中央谷的连续主窗边界；不是所有子带的外包络。BW20 另要求此连通分量覆盖两个内峰，若分裂则报告空值，不填零。S21 取完整 BW20 窗口内原生扫频样本的最小值。独立从复数 CSV 与 NPZ 重算并核对了每条可用曲线。','']
    rows=[]
    for k in ('W4R','dense','C1W','C2W','C3W'):
        m=s['five'][k];e=(m or {}).get('edges20') or {};ct=ctr.get(k)
        rows.append([label(k),*vals(m),fmt(e.get('low_GHz'),5),fmt(e.get('high_GHz'),5),fmt(ct['adjusted'],6)+' / '+yes(ct['passed']) if ct else '不适用' if k in ('dense','W4R') else '不可判'])
    lines+=table(['曲线','中央谷 GHz','低峰 dB','高峰 dB','BW20 GHz','最低 S21 dB','低边 GHz','高边 GHz','角点 Γ + 网格偏差'],rows)
    lines+=['','C2W：e=−0.010 mm、εr=3.60、h=0.851 mm；C3W：e=−0.010 mm、εr=3.50、h=0.851 mm。C1 系列：e=+0.010 mm、εr=3.50、h=0.775 mm。板框和馈线端口截断面均固定，高度 8h、横向宽 15.04 mm。W4R 用自身测得的网格项 0.002336。','',
    '![五条曲线与交集](CURVES.png)','','五曲线交集不是全公差立方体、全部八角或实际生产良率的证明。工艺误差仍有未直接求解的组合。','',
    '## 2　带边移动能否相加？','', '基准为 W4R 名义。单位 MHz；残差 = 实测 − 冻结线性预测。C1 薄板项的高端缺少可比的完整带边，不虚构预测值。','']
    rows=[]
    for k in ('C1W','C2W','C3W'):
        a=rr[k];rows.append([k,*[fmt(a[t][i],1) for i in [0,1] for t in ['predicted_MHz','measured_MHz','residual_MHz']]])
    lines+=table(['角点','低边预测','低边实测','低边残差','高边预测','高边实测','高边残差'],rows)
    for i,edge in enumerate(['低','高']):
        vals_r=[rr[k]['residual_MHz'][i] for k in ('C2W','C3W')]
        if any(x is None for x in vals_r):v='覆盖不全，不能认定可替代角点仿真。'
        elif max(map(abs,vals_r))<=30:v='两项残差均不超过 30 MHz，可在相近几何、材料和公差范围内用相加法做初估，不必为了初估重跑这两点；认证不在此结论内。'
        else:v='至少有一项残差超过 30 MHz，不能用该线性叠加替代这一侧的直接角点验证。'
        lines.append(f'\n**{edge}边：**{v}')
    lines+=['','## 3　Wm 加宽后的名义带宽与稳健交付','',
    f"默认 h=0.813±0.038 mm；Γ_req=0.073324、P_req={new:.6f} dB。峰值窗 [{new-.2:.4f},{new:.4f}] dB，|D|≤0.2 dB，中央谷 6.73–6.75 GHz，完整 BW20 内 S21≥−2 dB。a=1.8、g=0.55 mm；Ls2=2Ws+g，Ls3=Ws+a。",'']
    rows=[]
    for name,m,c,gt in [('B1R',s['B1R'],'C1R','未测；C1R 完整主窗断开'),('W4R',n['W4R'],'C1W',band(g)+'（五曲线交集）'),('W5R',n['W5R'],'C1W5',band(s['estimated_guarantee']['W5R'])),('W6R',n['W6R'],'C1W6',band(s['estimated_guarantee']['W6R']))]:
        wider=name in ('W5R','W6R');control=ctr.get(c)
        if name=='B1R':cv=s['B1R_confirmation']['corner_Gamma_plus_bias'];pl='不通过，自身'
        else:cv=(control or {}).get('adjusted');pl=(yes((control or {}).get('passed'))+'，'+('借用' if wider else '自身'))
        state= ('调准' if d[name].get('passed') else ('未调准的最近候选' if m else '未运行/无有效值')) if wider else '上阶段目标'
        rows.append([name+' / '+state,*vals(m),f"{c}: {fmt(cv,6)}（{pl}）",('未运行，无名义曲线可供估算' if wider and not m else gt+('；未直测，按 W4R 带边移动估算' if wider else ''))])
    lines+=table(['设计 / 名义状态','中央谷 GHz','低峰 dB','高峰 dB','BW20 GHz','最低 S21 dB','Γ角点+偏差','保证带 GHz'],rows)
    for k in ('C1W5','C1W6'):
        v=cm[k];lines.append(f"\n{k} 实测：[中央谷、低峰、高峰、BW20、最低 S21] = "+' / '.join(vals(v))+'；'+('无测量值。' if not v else '网格项借用 W4R，不是本设计密网格结果。'))
    lines+=['','B1R 密网格统计档边缘（未含残差），C1R 的 Γ 加自身网格偏差为 0.10430，不满足 0.1。W4R 自身密网格统计档含残差通过，C1W 为 0.09508；其他实测角点见表 1。较宽设计的保证带估算：把 W4R 交集相对名义的两侧收缩量分别转移，再与该设计已测 C1 主窗相交。若未调准，不作为稳健曲线样本。','',
    '**推荐版名义尺寸（mm）**：'+ '，'.join(f'{k}={v:.3f}' for k,v in s['geometry_mm'].items())+'；a=1.800，g=0.550。仿真未含 SMA 接头；板厚是既有工艺考察中影响内峰最大的误差，不要用插值扫频和少数角点代替加工良率认证。','',
    '### 两条 BW20–Wm 曲线','',
    f"W4R 的旧目标 {s['robust_curve'][0]['old_req']:.4f} dB，按 0.170 GHz/dB 换算到共同目标 {new:.4f} dB，得到 {s['robust_curve'][0]['BW20_GHz']:.5f} GHz（估算，不是重算）。名义组为约 −20.3 dB，不人为把 B1 的不同纹波当作同一条曲线。"]
    for field in ('nominal','robust'):
        lines+=['',('名义' if field=='nominal' else '稳健')+'组：'+ '；'.join(f"{x['design']} ({x['Wm']:.2f} mm, {x['BW20_GHz']:.4f} GHz)" for x in s[field+'_curve'])+'。','相邻区间斜率（GHz/mm）：'+('；'.join(f"{x['from_mm']:.2f}→{x['to_mm']:.2f}: {x['GHz_per_mm']:.3f}" for x in s[field+'_slopes']) or '不可估计')+'。']
    sl=s['robust_slopes']
    if len(sl)>=2:
        a,b=[x['GHz_per_mm'] for x in sl[-2:]]
        lines.append(f'稳健组后一区间的斜率比前一区间{"小" if b<a else "不小"}（{a:.3f} → {b:.3f}）。'+('增益下降' if b<a else '未见斜率下降')+'不等于确立普适平台；第一段基线经过纹波目标换算。')
    else:lines.append('同一稳健目标下可比较的相邻区间不到两个，不能判断斜率是否递减或平台出现在哪里。')
    lines+=['','![两种纹波条件下的宽度规律](WIDTH_LAW.png)','',
    'C1 相对名义的实测 Δ|Γ|：'+ '；'.join(k+' '+fmt(v,6) for k,v in s['dGamma'].items())+'。这只描述已测宽度及组合，不能外推为普适单调律。','',
    '## 4　预登记预测与顺序门槛','', 'Q31–Q35 原文见 [求解前冻结](../freeze/R16_R8.json)。所有合取条件均需满足；测量缺失与预测失败分别记录。','']
    lines+=table(['预测','评分','对照条件'],[[k,yes(v['passed']),desc] for (k,v),desc in zip(s['Q'].items(),['C2W 双边、带宽及双峰全部满足','C3W 低边与带宽同时满足','五曲线交集宽度','≤3 次调准且带宽落在预测区间','配对角点 Δ|Γ| 区间且计网格偏差后通过'])])
    if d['W5R']['complete'] and not d['W5R']['passed'] and n['W5R']:
        m=n['W5R']
        lines+=['',f"W5R 的最近候选 {d['W5R']['selected_case'].split('__')[-1]}：中央谷 {m['center_GHz']:.2f} GHz，纹波峰 {m['low_peak_dB']:.3f}/{m['high_peak_dB']:.3f} dB。带宽落入区间不等于调准；Q34 仍不通过。C1W5 是此候选的联合角点测试，即使 Q35 通过，也不能据此开放 W6R 或宣称 W5R 完成稳健调准。"]
    for k,v in d.items():lines.append('\n'+k+'：'+(v.get('reason') or ('已完成规定角点' if v.get('selected_case') else '见终态'))+'；选定 '+str(v.get('selected_case') or '无')+'。')
    lines+=['','## 5　实际尝试、预算和证据','']
    rows=[]
    for t in s['trials']:
        m=t.get('measurement');rows.append([t['case'],*vals(m),t['mesh_cells'] or '—',fmt(t['delta_s'],6),t['Analyze'],yes((t.get('tuning') or {}).get('tuned')) if t['case'].split('__')[0] in ('S8R16_W5R','S8R16_W6R') else '角点对照'])
    lines+=table(['算例','中央谷 GHz','低峰 dB','高峰 dB','BW20 GHz','最低 S21 dB','网格','ΔS','Analyze','名义调准'],rows)
    if b['duplicate_full_configuration_groups']:
        lines+=['', '**执行偏差：W5R 三次付费尝试实际只有两种名义几何。** 第三次 T3 与 T2 的冻结 CAD、材料和端口指纹相同，原生验证与输入相符，均为独立冷启动且结果一致；T3 不是独立设计点。两次原始证据均保留，重复尝试的 '+str(b['extra_Analyze_on_duplicate_inputs'])+' 次 Analyze 全额计入，没有补做第四次。', '',
        '原因：以最大归一化误差选基点，T1=3.000、T2=3.515，程序仍取 T1；T2 两个纹波分量的预测改变量为 +0.098 和 −0.183 dB，均未触发冻结的 >0.3 dB 雅可比更新条件，故提议返回同一尺寸。派发时仅检查算例编号，没有按最终 CAD 指纹去重。这是调参/调度的局限，不是 HFSS 未响应尺寸修改，也不能判 2.80 mm 物理不可达。下一版应在验证及计费前按尺寸、材料、端口和数值设置去重；相同候选应停止或按另行预先批准的规则选不同候选。本阶段没有改写冻结控制器。']
    lines+=['','每次 T1 及后续尝试的预测、三维响应残差、实际几何和独立验证的提交均在 [RESULTS.json](RESULTS.json)；未改原盲测，不把调参样本算作新独立测试。新几何按零 Analyze 原生验证、绑定发布、14 核单组串行求解、终态和实际看图记录分别归档。','',
    '阶段 6 的逐点扰动、B1 差值、线性与 Jacobian 对照、现实/保守公差和 Q11–Q16 的原始评分不因本阶段修改。参阅[阶段 6 中文报告](../../fold_bandwidth_r14_stage6_r6_20261116/final/REPORT.md)与[阶段 7 对照](../../fold_bandwidth_r15_stage7_r7_20261116/final/REPORT.md)。本轮未新增密网格、直接频点或连接器测试。','',
    '本报告到阶段 8 为止，剩余额度不转入新阶段。闭账证据：[FINAL_AUDIT.json](FINAL_AUDIT.json)、[CLOSURE.json](CLOSURE.json)。']
    return '\n'.join(lines)+'\n'
def main():
    if (ROOT/'STOP.json').exists():raise RuntimeError('already stopped; no rewrite')
    s=A.summarize();md=render(s);F.mkdir(exist_ok=True)
    if any((F/n).exists() for n in ['REPORT.md','RESULTS.json','CURVES.png','WIDTH_LAW.png']):raise RuntimeError('report exists, no overwrite')
    draw(s);write_x(F/'RESULTS.json',s)
    with (F/'REPORT.md').open('x',encoding='utf-8',newline='\n') as f:f.write(md)
    print(json.dumps({k:s[k] for k in ('budget','guarantee','Q','recommend')},ensure_ascii=False))
if __name__=='__main__':main()
