"""Plot actual W5R peaks and the frozen acceptance rectangle."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
out=Path(__file__).resolve().parent.parent
def draw():
    r=json.loads((out/'RESULTS.json').read_text(encoding='utf-8'));req=r['margin']['P_req_dB'];fig,ax=plt.subplots(figsize=(7.4,4.5))
    ax.add_patch(Rectangle((6.73,req-.2),.03,.2,facecolor='#77bba5',edgecolor='#146b51',alpha=.48,label='Joint target window'))
    for i,(c,t) in enumerate(r['raw'].items()):
        if '_W5R__' not in c:continue
        m=t['measurement'];x=m['center_GHz'];lo=m['low_peak_dB'];hi=m['high_peak_dB'];col='#2e5c85'
        ax.plot([x,x],[lo,hi],c=col,lw=1.8);ax.scatter([x],[lo],marker='o',s=38,c=col,label='Lower-frequency peak' if i==0 else None)
        ax.scatter([x],[hi],marker='^',s=45,c='#ad6137',label='Higher-frequency peak' if i==0 else None)
        ax.annotate(c.split('__')[-1],(x,max(lo,hi)),xytext=(5,3),textcoords='offset points')
    ax.set(xlabel='Measured central valley (GHz)',ylabel='Measured inner peak S11 (dB)',title='W5R: both peaks must fall inside the same green window',xlim=(6.69,6.795),ylim=(-23.5,-22.15))
    ax.legend(loc='lower left',fontsize=8);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'W5R_TUNING.png',dpi=145);plt.close(fig)
if __name__=='__main__':draw()
