"""Post-result offline coverage check: all ten controls on identical frequency bins.

Keeps frozen per-control summaries untouched. No extrapolation/interpolation,
no threshold changes, no new native solve, no full-modal certification.
"""
from prepare_r7 import *
import numpy as np,csv

def compare():
    cfg=read(ROOT/'authorization.json');items=[];common=None;freq=None
    for p in cfg['parent_order']:
        s=cfg['designs'][p]
        if s['kind']!='LOSSLESS':continue
        case=read(ROOT/'decisions'/(p+'_FINAL.json'))['selected_case'];w=case_dir(ROOT,case,cfg)
        bal=np.load(w/'review/lossless_modal_balance.npz');f=bal['f_GHz'];sel=selection(ROOT,s['parent'],cfg)
        qp=source(sel[0])[0] if sel[0] not in cfg['case_paths'] else case_dir(ROOT,sel[0],cfg)/'review/extraction_R2.json'
        band=read(qp)['bandwidths']['BW15'];mask=bal['valid']&(f>=band['low_GHz'])&(f<=band['high_GHz'])
        if freq is None:freq=f;common=mask.copy()
        else:np.testing.assert_array_equal(freq,f);common&=mask
        items.append(dict(case=case,family=s['family'],a=s['nominal_a_mm'],residual=bal['residual_fraction'],
            source_sha256=sha(w/'review/lossless_modal_balance.npz'),per_case_valid_count=int(mask.sum())))
    assert len(items)==10 and int(common.sum())>0
    out=HERE/'final_common_power';out.mkdir(exist_ok=False)
    rows=[{k:v for k,v in r.items() if k!='residual'}|dict(common_mean=float(r['residual'][common].mean()),
        common_min=float(r['residual'][common].min()),common_max=float(r['residual'][common].max())) for r in items]
    write(out/'COMMON_GRID.json',dict(post_result_coverage_check=True,no_refit=True,
        common_frequency_count=int(common.sum()),frequency_min_GHz=float(freq[common].min()),frequency_max_GHz=float(freq[common].max()),
        selected_frequency_bins_GHz=freq[common].tolist(),power_fraction_unit='1=100%',full_modal_power_certified=False,rows=rows))
    with (out/'CURVES.csv').open('x',newline='',encoding='utf-8') as fp:
        wr=csv.writer(fp);wr.writerow(['f_GHz']+[r['case'] for r in items])
        for i in np.where(common)[0]:wr.writerow([freq[i]]+[r['residual'][i] for r in items])
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,5))
    for fam in ('N04','N14'):
        rr=sorted([r for r in rows if r['family']==fam],key=lambda r:r['a'])
        ax.plot([r['a'] for r in rr],[r['common_mean'] for r in rr],'-o',label=fam)
    ax.set(xlabel='Fold arm a (mm)',ylabel='Mean radiation plus numerical residual (fraction)',
        title=f'Identical valid frequency bins in all 10 controls (n={int(common.sum())})')
    ax.grid(alpha=.3);ax.legend();fig.tight_layout();fig.savefig(out/'COMMON_POWER_VS_ARM.png',dpi=150);plt.close(fig)
    lines=['# 功率曲线覆盖率补充核对','',
      '原报告每条曲线的有效频点不同（主带有效比例约72%–97%），直接比较各自均值可能有频率选择偏差。这里保留原结果，另取10个无耗控制共同有效且都在各自主带内的同一组原生频点；不插值、不重拟合、不改传播判据。',
      f"共同有效频点{int(common.sum())}个，范围{freq[common].min():.2f}–{freq[common].max():.2f} GHz；不是连续无缺口全频带。",'',
      '|家族|a mm|同频点平均余量（1=100%）|','|---|---|---|']
    for r in rows:lines.append(f"|{r['family']}|{r['a']}|{r['common_mean']:.8f}|")
    lines+=['','![common grid](COMMON_POWER_VS_ARM.png)','',
       '共同频点上两家族的余量都随折臂加长下降；与减少辐射边缘损耗的解释方向一致。但仍是辐射加数值误差，不是纯辐射，端口模完整性和场通量未认证。不能据此把full_modal_power_certified改为true。',
       '','完整逐频数据见CURVES.csv，原各自主带统计和缺口曲线仍保留在final_audit，不用这个事后覆盖检查替换冻结的原口径。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print('COMMON_GRID',int(common.sum()),[(r['family'],r['a'],r['common_mean']) for r in rows])
if __name__=='__main__':compare()
