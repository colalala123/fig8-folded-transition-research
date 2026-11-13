"""R7-1独立回归：只读已完成几何的原生CSV；不导入审核方拟合代码。"""
import csv, json, sys, hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
import chain

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def response(p):
    with p.open(encoding='utf-8-sig',newline='') as fp:
        r=csv.reader(fp); h=next(r); a=np.array(list(r),float)
    s=a[:,h.index('S(1:1,1:1)_real')]+1j*a[:,h.index('S(1:1,1:1)_imag')]
    f=a[:,0];d=20*np.log10(abs(s))
    valleys=np.where((d[1:-1]<d[:-2])&(d[1:-1]<=d[2:]))[0]+1
    valleys=[i for i in valleys if 5.8<f[i]<7.6]
    if not valleys:return None
    v=min(valleys,key=lambda i:abs(f[i]-6.72))
    left=[i for i in range(1,v) if d[i]>d[i-1] and d[i]>=d[i+1]]
    right=[i for i in range(v+1,len(f)-1) if d[i]>=d[i-1] and d[i]>d[i+1]]
    if not left or not right:return None
    lo,hi=left[-1],right[0]
    if not 4<f[lo]<f[hi]<9.2:return None
    return dict(valley_GHz=float(f[v]),D_dB=float(d[hi]-d[lo]),peak_mean_dB=float((d[hi]+d[lo])/2),peak_lo_dB=float(d[lo]),peak_hi_dB=float(d[hi]))

def collect():
    rows=[]
    dirs=['fold_bandwidth_r6_20261111','fold_bandwidth_r6_stage2_20261111','fold_bandwidth_r6_stage2b_20261112','fold_bandwidth_r6_stage3_20261112','fold_bandwidth_r6_stage3_corrected_20261113']
    for folder in dirs:
        for p in sorted((REPO/'experiments'/folder/'results').glob('*/native/full_modes.csv')):
            c=p.parents[1];summary=read(c/'SUMMARY.json')
            if not summary['record']['solve_completed']:continue
            inp=read(c/'INPUT.json');des=inp.get('design',inp);g=des['geometry_mm']
            top='folded' if g['Ls3'] else 'straight_control'
            y=response(p)
            rows.append(dict(case=c.name,source=str(p.relative_to(REPO)),sha256=digest(p),geometry_mm=g,
                 family=des.get('family'),a=chain.dimensions(g,top)['a_mm'],
                 Lm=g['Lm'],Lc=chain.dimensions(g,top)['L_centerline_mm'],Ws=g['Ws'],three_valley=y is not None,**(y or {})))
    return rows

def fit(rows):
    groups=defaultdict(list); steps=[]
    for r in rows:
        if '__T' in r['case']:groups[r['case'].split('__T')[0]].append(r)
    keys=['Lm','Lc','Ws','valley_GHz','D_dB','peak_mean_dB']
    def step(p,q,group):
        steps.append(dict(source=p['case'],destination=q['case'],group=group,dx=[q[k]-p[k] for k in keys[:3]],dy=[q[k]-p[k] for k in keys[3:]]))
    for group,rr in sorted(groups.items()):
        rr=sorted(rr,key=lambda r:r['case'])
        for p,q in zip(rr,rr[1:]):
            if p['three_valley'] and q['three_valley'] and abs(p['a']-q['a'])<1e-6 and max(abs(p['D_dB']),abs(q['D_dB']))<6:step(p,q,group)
    by={r['case']:r for r in rows};base=by['S1_WS_04']
    for r in rows:
        if r['case'].startswith('S1_WS') and r['case']!='S1_WS_04':step(base,r,'1b')
    X=np.array([r['dx'] for r in steps]);Y=np.array([r['dy'] for r in steps]);J=np.linalg.lstsq(X,Y,rcond=None)[0]
    sd=np.std(Y-X@J,axis=0)
    reference=np.array([[-2.29,30.5,-.7],[.54,-12.6,-.9],[-1.70,38.7,27.8]])
    indices=[(0,0),(0,1),(1,0),(1,1),(2,1),(2,2)]
    deviations=[abs(J[i,j]/reference[i,j]-1) for i,j in indices]
    passed=bool(max(deviations)<=.2 and np.all(sd<=[.03,.45,.20]))
    return dict(passed=passed,n=len(steps),rows='Lm,Lc,Ws',cols='valley_GHz,D_dB,L_dB',J0=J.tolist(),residual_sd=sd.tolist(),six_relative_deviations=deviations,steps=steps,rank=int(np.linalg.matrix_rank(X)))

if __name__=='__main__':
    out=HERE/'offline';out.mkdir(exist_ok=False)
    rows=collect();result=fit(rows)
    for n,v in [('INPUT_ROWS',rows),('SENSITIVITY',result)]:
        (out/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='steps'},indent=2))
    if not result['passed']:raise SystemExit(2)
