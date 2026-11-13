"""Strictly offline final visualization. Never imported by dispatch code."""
from prepare_r8 import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def main():
    out=HERE/'final';selected=read(out/'SELECTED.json');scores=read(out/'T1_SCORES.json');models=read(HERE/'offline/LAWS.json')
    import laws
    fig,ax=plt.subplots(figsize=(8,5));w=np.linspace(1.68,2.09,200)
    for deg,pm in models['platform'].items():ax.plot(w,[laws.platform(pm,float(x)) for x in w],label='Frozen F'+deg,lw=1.5)
    pp=models['platform']['2']['plateaus'];ax.scatter([p['Wm'] for p in pp],[p['F'] for p in pp],marker='^',s=70,color='gray',label='Retrospective family plateaus')
    for n in ('D6','D8'):
        r=next(x for x in selected if x['design']==n)
        if r['tuned']:
            lo,hi=r['BW15_star_slope_range'];v=r['BW15_star']
            ax.errorbar(r['geometry_mm']['Wm'],v,yerr=[[v-lo],[hi-v]],marker='s',ms=7,capsize=3,label=n+' selected usable (tuned)')
    ax.set(xlabel='Wm (mm)',ylabel='BW15* (GHz)',title='Stage4: frozen platform predictions vs selected usable designs');ax.grid(alpha=.25);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(out/'PLATFORM.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5));x=np.arange(1,9)
    for mode in ('tip','sum','a'):
        ax.plot(x,[s['frozen_prediction']['BW15_star_GHz']['F2_'+mode] for s in scores],marker='.',label='Frozen F2_'+mode,alpha=.8)
    for i,(s,r) in enumerate(zip(scores,selected),1):
        if s['T1']['BW15_star'] is not None:ax.scatter(i,s['T1']['BW15_star'],marker='x',c='gray',s=55,label='T1 actual (may be imbalanced)' if i==2 else None)
        if r['tuned']:
            lo,hi=r['BW15_star_slope_range'];v=r['BW15_star'];ax.errorbar(i,v,yerr=[[v-lo],[hi-v]],marker='s',color='black',capsize=3,label='Selected R7 usable' if i==2 else None)
        else:ax.text(i,6.06,'not usable',ha='center',fontsize=8,rotation=90,color='firebrick')
    ax.set(xticks=x,xticklabels=[s['design'] for s in scores],ylabel='BW15* (GHz)',title='Predictions remain frozen; T2/T3 are tuning, not blind tests');ax.grid(alpha=.25);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(out/'BANDWIDTH_COMPARISON.png',dpi=160);plt.close(fig)
    cfg=read(ROOT/'authorization.json');fig,axs=plt.subplots(4,2,figsize=(12,13),sharex=True,sharey=True)
    for ax,r in zip(axs.flat,selected):
        z=np.load(case_dir(ROOT,r['case'],cfg)/'native/full_modes.npz');f=z['f_GHz'];S=z['S']
        ax.plot(f,20*np.log10(abs(S[:,0,0])),label='S11');ax.plot(f,20*np.log10(abs(S[:,2,0])),label='S21')
        ax.axhline(-20,color='gray',ls='--',lw=.8);ax.axhline(-2,color='gray',ls=':',lw=.8)
        ax.set(xlim=(3,10.5),ylim=(-60,3),title=r['case']+(' [usable]' if r['tuned'] else ' [not usable]'));ax.grid(alpha=.2)
    axs[0,0].legend(fontsize=8)
    for ax in axs[-1,:]:ax.set_xlabel('Frequency (GHz)')
    for ax in axs[:,0]:ax.set_ylabel('Magnitude (dB)')
    fig.tight_layout();fig.savefig(out/'SELECTED_CURVES.png',dpi=140);plt.close(fig)
    write(out/'PLOT_MANIFEST.json',{n:sha(out/n) for n in ('PLATFORM.png','BANDWIDTH_COMPARISON.png','SELECTED_CURVES.png')})
if __name__=='__main__':main()
