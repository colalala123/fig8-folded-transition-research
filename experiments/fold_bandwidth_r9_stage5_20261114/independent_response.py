"""Independent raw-CSV R2 response replay, OFFLINE ONLY.

Use the registered three prominent valleys and the MAXIMUM between adjacent
valleys, not the first tiny local maximum. No canonical extractor is imported.
"""
import csv
import numpy as np
from scipy.signal import find_peaks

def load_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:r=list(csv.DictReader(f))
    fr=np.array([float(z['f_GHz']) for z in r])
    def db(ex):
        z=np.array([complex(float(x[ex+'_real']),float(x[ex+'_imag'])) for x in r])
        return 20*np.log10(np.maximum(abs(z),1e-15))
    return fr,db('S(1:1,1:1)'),db('S(2:1,1:1)')

def components(f,d,threshold):
    below=np.asarray(d)<=threshold
    starts=np.flatnonzero(below & np.r_[True,~below[:-1]])
    ends=np.flatnonzero(below & np.r_[~below[1:],True])
    out=[]
    for a,b in zip(starts,ends):
        l=f[a] if a==0 else f[a-1]+(threshold-d[a-1])/(d[a]-d[a-1])*(f[a]-f[a-1])
        h=f[b] if b==len(f)-1 else f[b]+(threshold-d[b])/(d[b+1]-d[b])*(f[b+1]-f[b])
        out.append((float(l),float(h)))
    return out

def metrics(f,d,t):
    passbands=components(f,-t,2) # transmission pass condition is S21 >= -2dB
    if not passbands:return dict(three_valley=False)
    l,h=max(passbands,key=lambda b:b[1]-b[0])
    vv=[i for i in find_peaks(-d,prominence=.5)[0] if l<f[i]<h and d[i]<-10]
    if len(vv)!=3:return dict(three_valley=False)
    lo=vv[0]+1+int(np.argmax(d[vv[0]+1:vv[1]]));hi=vv[1]+1+int(np.argmax(d[vv[1]+1:vv[2]]))
    out=dict(three_valley=True,valley_GHz=float(f[vv[1]]),valley_indices=list(map(int,vv)),peak_lo_GHz=float(f[lo]),peak_hi_GHz=float(f[hi]),peak_lo_dB=float(d[lo]),peak_hi_dB=float(d[hi]),D_dB=float(d[hi]-d[lo]),peak_mean_dB=float((d[lo]+d[hi])/2))
    for k,thr in [('BW15',-15),('BW20',-20)]:
        bb=next((b for b in components(f,d,thr) if b[0]<=f[lo]<=f[vv[1]]<=f[hi]<=b[1]),None)
        out[k]=None if bb is None else float(bb[1]-bb[0]);out[k+'_edges']=bb
    return out

if __name__=='__main__':
    import sys,json
    print(json.dumps(metrics(*load_csv(sys.argv[1])),indent=2))
