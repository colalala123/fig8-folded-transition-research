"""阶段1已完成报告的辅助图，不改变冻结噪声算法或任何门槛。"""
import argparse
import json
from pathlib import Path
import numpy as np

def plot(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data=json.loads((folder/'input.json').read_text(encoding='utf-8'))
    a=json.loads((folder/'analysis.json').read_text(encoding='utf-8'))
    rows=data['perturbations']
    baseline=next(r for r in data['baseline'] if r['id']=='S1_BASE_N14')
    x=np.array([r['geometry_mm']['Ws']-baseline['geometry_mm']['Ws'] for r in rows])
    keys=['inner_peak_low_dB','inner_peak_high_dB','central_valley_GHz','BW15_GHz']
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for ax,key in zip(axes.ravel(),keys):
        y=np.array([r['metrics'][key] for r in rows])
        xx=np.linspace(x.min(),x.max(),201)
        ax.plot(x,y,'o',label='HFSS (independent mesh)')
        for deg,style in ((1,'--'),(2,'-')):
            ax.plot(xx,np.polyval(np.polyfit(x,y,deg),xx),style,lw=1,label=f'degree {deg}')
        ax.set(xlabel='Delta Ws (mm)',ylabel=key)
        ax.grid(alpha=.3);ax.legend(fontsize=8)
        n=a['perturbation_noise'][key]
        ax.set_title(f"residual SD: linear {n['linear_residual_sd']:.4g}; quadratic {n['quadratic_residual_sd']:.4g}",fontsize=10)
    fig.suptitle('R6 stage 1b: geometry response and residuals (not independent noise samples)')
    fig.tight_layout()
    target=folder/'PERTURBATIONS.png'
    if target.exists():raise RuntimeError('图已存在，不覆盖')
    fig.savefig(target,dpi=150);plt.close(fig)
    import hashlib
    path=folder/'PLOT_MANIFEST.json'
    with path.open('x',encoding='utf-8') as fp:
        json.dump({target.name:hashlib.sha256(target.read_bytes()).hexdigest()},fp,indent=2)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);a=p.parse_args();plot(a.folder)
