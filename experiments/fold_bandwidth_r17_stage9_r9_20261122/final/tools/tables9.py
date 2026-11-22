"""Generate the reproducible numerical annex and two figures from RESULTS.json only."""
import json,csv
from pathlib import Path
from analysis9 import H,OUT,REPO
import numpy as np
def num(x,n=3):return '—' if x is None else f'{x:.{n}f}'
def vec(x,n=3):return ' / '.join(num(v,n) for v in x) if x is not None else '—'
def mark(v):return '未检验' if v is None else '通过' if v else '未通过'
def geometry(t):
    if not t:return '—'
    return vec([t['geometry_mm'][k] for k in ('Wm','Ws','Lm','Ls1','Ls2','Ls3')])
def tables(d):
    L=['# 阶段 9 数值附表','','## 1　回放、逐次调参与前瞻误差','','R9-1：旧代码重提 T2；R9-2：新代码给出规定 T4；R9-3：加入 T3 后不变；R9-4：历史相同物理输入被拒，0 计费；R9-5：传入雅可比确实替代 J0。均使用实际历史。详见 [REPLAY.json](../freeze/REPLAY.json)。','','响应顺序：中央谷 GHz / D dB（高峰减低峰）/ 均值 dB。残差定义为实测减预测；预测是求解前的冻结值，不是回代。','','|案例|角色|预测响应|实测响应|残差|BW20 GHz|S21 最低 dB|网格 / ΔS|实际 Analyze|','|---|---|---|---|---|---:|---:|---|---:|']
    for k,t in d['raw'].items():
        m=t['measurement'];a=t['central_state'];p=t['prediction'];res=(np.array(a)-p) if p is not None and a is not None else None
        L += [f"|{k}|{t['role']}|{vec(p,4)}|{vec(a,4)}|{vec(res,4)}|{num(m.get('BW20_GHz'),4)}|{num(m.get('S21_min_dB'))}|{t['mesh']} / {num(t['delta_s'],6)}|{t['Analyze']}|"]
    L+=['','J 的行依次为 Lm、Lc、Ws，列为中央谷、D、均值。下表是最终 J；Δ 为与 B1 初值之差。宽度的继承初值以及每步割线（含 dx=0 的跳过记录）见 [RESULTS.json](RESULTS.json)。','','|宽度|坐标|最终 J 行|Δ vs B1|','|---|---|---|---|']
    for i,k in enumerate(('Lm','Lc','Ws')):L.append(f"|B1 初值|{k}|{vec(d['J0'][i],4)}|0|")
    for n,j in d['jacobians'].items():
        for i,k in enumerate(('Lm','Lc','Ws')):L.append(f"|{n}|{k}|{vec(j['final'][i],4)}|{vec(j['change_vs_B1'][i],4)}|")
    L+=['','## 2　宽度规律；实测与换算分列','','尺寸顺序 Wm / Ws / Lm / Ls1 / Ls2 / Ls3（mm）。B1R、W4R 的共同目标带宽为局部三目标雅可比校正再乘 B1 物理带宽梯度；不是重新仿真的曲线，也不对其角点作相同校正。','','|设计|尺寸 mm|原名义 BW20|原名义带边 GHz|换算到共同目标 BW20|C1 相对哪次名义|C1 ΔΓ|C1 低 / 高边移动 MHz|候选估算保证带 GHz|','|---|---|---:|---|---:|---|---:|---|---|']
    for k,w in d['widths'].items():
        t=w['nominal'];delta=w['delta'];z=w['normalized'];candidate=(d['selection'] or {}).get('candidates',{}).get(k)
        rband=vec(candidate['band_GHz'],4) if candidate else ('阶段 8 已实测 '+vec(d['W4R_intersection']['edges'],4) if k=='W4R' else '无合资格估算')
        L.append(f"|{k}|{geometry(t)}|{num(t['measurement']['BW20_GHz'],4) if t else '—'}|{vec(t['edges'],4) if t else '—'}|{num(z['estimated_BW_GHz'],4) if z else '—'}|{w['C1_ref']['case'] if w['C1_ref'] and w['C1'] else '—'}|{num(delta['dGamma'],5) if delta else '—'}|{vec(delta['edge_shift_MHz'],1) if delta else '—'}|{rband}|")
    L+=['','B1R 的角点高峰高于 −20 dB，三谷主窗被切断；该行若显示带边移动，只是包含中央谷的局部连通区间，不构成整带资格。W5R 若借用 T1 角点只用于资格和估算，不冒充调准件自己的 C1。','','|相邻宽度|增量 GHz|斜率 GHz/mm|依据|','|---|---:|---:|---|']
    for r in d['slopes']:L.append(f"|{' → '.join(r['pair'])}|{num(r['gain_GHz'],4)}|{num(r['slope_GHz_per_mm'],4)}|{'含局部换算' if r['converted'] else '共同目标实测'}|")
    L+=['','## 3　交付的完整性与迁移残差','','|设计 / 曲线|中央谷 GHz|低 / 高峰 dB|主窗 BW20 GHz|S21 最低 dB|带边 GHz|9D 事先预测 GHz|残差 MHz|','|---|---:|---|---:|---:|---|---|---|']
    series=[('W4R',d['W4R_five_reference'])]
    if d['winner']!='W4R':series.append((d['winner'],d['five']))
    for n,points in series:
        for k,t in points.items():
            if not t:L.append(f'|{n} / {k}|—|—|—|—|缺少有效曲线|—|—|');continue
            m=t['measurement'];p=d['selection']['selected_edges'][k] if n!='W4R' and d['selection'] else None;r=(d['transfer_residual_MHz'] or {}).get(k) if n!='W4R' else None
            L.append(f"|{n} / {k}|{num(m.get('center_GHz'))}|{vec([m.get('low_peak_dB'),m.get('high_peak_dB')])}|{num(m.get('BW20_GHz'),4)}|{num(m.get('S21_min_dB'))}|{vec(t['edges'],5)}|{vec(p,5)}|{vec(r,2)}|")
    L+=['','## 4　登记预测评分','','|编号|评分|','|---|---|']
    for k,sc in d['Q'].items():L.append(f'|{k}|{mark(sc)}|')
    L+=['','逐点 CAD、原生四模矩阵、运行身份和 S11/S21 图在 [results/](../results/)；原授权和六条预测原文在 [R9 冻结](../freeze/R17_R9.json)。']
    return '\n'.join(L)+'\n'
def plots(d):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(2,1,figsize=(10,7.4),sharex=True)
    for k,t in d['five'].items():
        if not t:continue
        with np.load(REPO/t['source']/'native/full_modes.npz') as z:
            for a,idx in zip(ax,(0,2)):a.plot(z['f_GHz'],20*np.log10(np.maximum(abs(z['S'][:,idx,0]),1e-15)),label=k,lw=1.2)
    for a,label,yl,target in zip(ax,('S11','S21'),[(-50,-14),(-3,.1)],[-20,-2]):
        a.axhline(target,ls='--',c='k',lw=.8);a.set_ylim(*yl);a.set_ylabel(label+' (dB)');a.grid(alpha=.22)
        if (d['intersection'] or {}).get('edges'):a.axvspan(*d['intersection']['edges'],color='#27895a',alpha=.07)
    ax[0].set_title(d['winner']+' | native HFSS traces and their measured common band');ax[0].legend(ncol=5);ax[1].set_xlabel('Frequency (GHz)');ax[1].set_xlim(2.9,10.3);fig.tight_layout();fig.savefig(OUT/'DELIVERY.png',dpi=145);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.4,4.3))
    for k,w in d['widths'].items():
        t=w['nominal']
        if t:
            z=w['normalized'];y=z['estimated_BW_GHz'] if z else t['measurement']['BW20_GHz']
            ax.scatter(w['width'],y,marker='s' if z else 'o',facecolors='none' if z else '#146485',edgecolors='#146485');ax.annotate(k,xy=(w['width'],y),xytext=(3,7),textcoords='offset points')
    ax.set(xlabel='Wm (mm)',ylabel='20 dB bandwidth (GHz)',title='Common robust target: measured (solid), converted (open)');ax.grid(alpha=.25);ax.margins(.15);fig.tight_layout();fig.savefig(OUT/'WIDTH.png',dpi=145);plt.close(fig)
if __name__=='__main__':
    d=json.loads((OUT/'RESULTS.json').read_text(encoding='utf-8'))
    with (OUT/'TABLES.md').open('x',encoding='utf-8',newline='\n') as f:f.write(tables(d))
    plots(d)
