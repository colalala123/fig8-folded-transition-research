from lib import *
from sklearn.preprocessing import PolynomialFeatures,StandardScaler
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits
import joblib
threadpool_limits(limits=1)
d=read(ROOT/'DATASET.json');a=np.load(ROOT/'dataset.npz');X,Y,Z,f=a['X'],a['Y'],a['Z'],a['f'];rows=d['rows'];groups=np.array([r['family'] for r in rows]);dev=np.array([i for i,r in enumerate(rows) if r['source']!='diagnostic_holdout']);hold=np.array([i for i,r in enumerate(rows) if r['source']=='diagnostic_holdout'])
truth=np.array([r['score']['passed'] for r in rows]);band=(f>=3.92)&(f<=9.52);complexY=np.concatenate([Z.real.reshape(len(Z),-1),Z.imag.reshape(len(Z),-1)],axis=1)
CONFIGS=[{'degree':p,'alpha':v} for p in [1,2] for v in [.001,.01,.1,1.,10.]]
def weights(idx):
 g=groups[idx];w=np.array([1/np.sum(g==v) for v in g]);return w/w.mean()

def folds(idx,n):
 gs=sorted(set(groups[idx]));return [(idx[~np.isin(groups[idx],gs[k::n])],idx[np.isin(groups[idx],gs[k::n])]) for k in range(n)]

def fit(idx,kind,cfg):
 cols=[0,1,2] if kind in ['A','C0'] else [0,1,2,3,4];raw=StandardScaler().fit(X[idx][:,cols]);u=raw.transform(X[idx][:,cols]);poly=PolynomialFeatures(cfg['degree'],include_bias=False).fit(u);u=poly.transform(u);scale=StandardScaler().fit(u);u=scale.transform(u)
 target=complexY if kind.startswith('C') else Y
 reg=Ridge(alpha=cfg['alpha']).fit(u,target[idx],sample_weight=weights(idx))
 return {'kind':kind,'columns':cols,'raw':raw,'poly':poly,'scale':scale,'reg':reg,'config':cfg,'train_cases':[rows[i]['case'] for i in idx]}

def predict(m,x):return m['reg'].predict(m['scale'].transform(m['poly'].transform(m['raw'].transform(x[:,m['columns']]))))

def decode(p):
 n=len(f)*2;return (p[:,:n]+1j*p[:,n:]).reshape(-1,len(f),2)

def decisions(y):return (y[:,0]<=-20)&(y[:,1]>=-2)&(abs(y[:,2]-6.72)<=.03000000001)&(y[:,3]<=.5)&(y[:,3]>=0)

def loss(idx,p,kind):
 w=weights(idx)
 if kind.startswith('C'):
  z=decode(p);worst=(20*np.log10(np.maximum(abs(z[:,band,0]),1e-15))).max(axis=1)
  # Same safety-priority scalar plus complex in-band response error; no held-out fold tuning.
  err=abs(worst-Y[idx,0])/.1+np.sqrt(np.mean(abs(z[:,band]-Z[idx][:,band])**2,axis=(1,2)))/.01
 else:
  err=(abs(p-Y[idx])/np.array([.1,.05,.03,.5,.02])).mean(axis=1)+5*(decisions(p)&~truth[idx])
 return float(np.average(err,weights=w))

def choose(idx,kind):
 results=[]
 for c in CONFIGS:
  values=[]
  for tr,va in folds(idx,3):
   assert set(groups[tr]).isdisjoint(groups[va]);m=fit(tr,kind,c);values.append(loss(va,predict(m,X[va]),kind))
  results.append({'config':c,'loss':float(np.mean(values))})
 return min(results,key=lambda r:r['loss'])['config'],results

def stats(idx,p,passed):
 w=weights(idx);err=np.abs(p-Y[idx]);return {'rows':len(idx),'true_passes':int(truth[idx].sum()),'predicted_passes':int(passed.sum()),'false_passes':int((passed&~truth[idx]).sum()),'missed_passes':int((~passed&truth[idx]).sum()),'MAE':dict(zip(LABELS,err.mean(axis=0).tolist())),'family_balanced_MAE':dict(zip(LABELS,np.average(err,axis=0,weights=w).tolist()))}
