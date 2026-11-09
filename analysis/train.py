from lib import *
from sklearn.preprocessing import PolynomialFeatures,StandardScaler
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits
from datetime import datetime,timezone
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
 cols=[0,1,2] if kind=='A' else [0,1,2,3,4];raw=StandardScaler().fit(X[idx][:,cols]);u=raw.transform(X[idx][:,cols]);poly=PolynomialFeatures(cfg['degree'],include_bias=False).fit(u);u=poly.transform(u);scale=StandardScaler().fit(u);u=scale.transform(u)
 target=complexY if kind=='C' else Y
 reg=Ridge(alpha=cfg['alpha']).fit(u,target[idx],sample_weight=weights(idx))
 return {'kind':kind,'columns':cols,'raw':raw,'poly':poly,'scale':scale,'reg':reg,'config':cfg,'train_cases':[rows[i]['case'] for i in idx]}
def predict(m,x):return m['reg'].predict(m['scale'].transform(m['poly'].transform(m['raw'].transform(x[:,m['columns']]))))
def decode(p):
 n=len(f)*2;return (p[:,:n]+1j*p[:,n:]).reshape(-1,len(f),2)
def decisions(y):return (y[:,0]<=-20)&(y[:,1]>=-2)&(abs(y[:,2]-6.72)<=.03000000001)&(y[:,3]<=.5)&(y[:,3]>=0)
def loss(idx,p,kind):
 w=weights(idx)
 if kind=='C':
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
allres={};allpred={};splits=[];tune=[]
for kind in ['A','B','C']:
 pp=np.full_like(Y,np.nan);predpass=np.zeros(len(rows),bool);extra={}
 for k,(tr,va) in enumerate(folds(dev,6)):
  cfg,search=choose(tr,kind);m=fit(tr,kind,cfg);p=predict(m,X[va]);tune.append({'model':kind,'fold':k,'train_families':sorted(set(groups[tr])),'test_families':sorted(set(groups[va])),'selected':cfg,'inner':search})
  assert set(groups[tr]).isdisjoint(groups[va])
  if kind=='C':
   for i,z in zip(va,decode(p)):
    q=label(f,z);extra[str(i)]=q;pp[i]=[q.get(key,float('nan')) for key in LABELS];predpass[i]=q['passed']
  else:pp[va]=p;predpass[va]=decisions(p)
  print(kind,k,cfg,flush=True)
 if not np.isfinite(pp[dev]).all():
  # Shape failures remain explicit; numeric comparison is available only where defined.
  valid=dev[np.isfinite(pp[dev]).all(axis=1)]
 else:valid=dev
 met=stats(valid,pp[valid],predpass[valid]);met['shape_failures']=len(dev)-len(valid);met['unconditional_false_passes']=int((predpass[dev]&~truth[dev]).sum());met['total_rows']=len(dev)
 if kind=='C':
  topology=[];edges=[]
  for i in dev:
   q=extra[str(i)];q0=rows[i]['score'];topology.append(q['joint_components']!=q0['joint_components'])
   if q['joint_center_band'] is not None and q0['joint_center_band'] is not None:edges.append(abs(np.array(q['joint_center_band'][:2])-q0['joint_center_band'][:2]))
  met['joint_component_count_errors']=int(sum(topology));met['joint_edge_MAE_GHz_conditional']=np.mean(edges,axis=0).tolist() if edges else None;met['joint_edge_pairs']=len(edges)
 allres[kind]=met;allpred[kind]={'prediction':pp,'pass':predpass,'extra':extra}
 cfg,search=choose(dev,kind);m=fit(dev,kind,cfg);joblib.dump(m,ROOT/f'model_{kind}.joblib');tune.append({'model':kind,'deployment':True,'selected':cfg,'inner':search})
 hp=predict(m,X[hold]);hrows=[]
 for j,i in enumerate(hold):
  if kind=='C':
   q=label(f,decode(hp[j:j+1])[0]);val=[q.get(key) for key in LABELS];pas=q['passed']
  else:val=hp[j].tolist();pas=bool(decisions(hp[j:j+1])[0])
  hrows.append({'case':rows[i]['case'],'predicted':val,'actual':Y[i].tolist(),'predicted_pass':pas,'actual_pass':bool(truth[i]),'status':'retrospective geometry holdout; family seen, outcomes known before project'})
 allres[kind]['diagnostic_geometry_holdout']=hrows
print(json.dumps(allres,indent=2),flush=True)
write('METRICS.json',allres);write('FOLDS_AND_TUNING.json',tune)
oof=[]
for i in dev:
 r={'case':rows[i]['case'],'family':groups[i],'actual':rows[i]['score'],'predictions':{}}
 for kind,v in allpred.items():
  r['predictions'][kind]={'values':[float(q) if np.isfinite(q) else None for q in v['prediction'][i]],'predicted_pass':bool(v['pass'][i])}
  if kind=='C':r['predictions'][kind]['curve_score']=v['extra'][str(i)]
 oof.append(r)
write('OUT_OF_FOLD.json',oof)
base=allres['A'];gate={}
for kind in ['B','C']:
 met=allres[kind];gate[kind]=bool(met['family_balanced_MAE']['worst_S11_dB']<=.9*base['family_balanced_MAE']['worst_S11_dB'] and met['unconditional_false_passes']<=base['unconditional_false_passes'] and met['shape_failures']==0)
write('MODEL_GATE.json',{'B_improved_indicator':gate['B'],'C_eligible_for_curve_inverse':gate['C'],'new_HFSS_started':False,'criterion':'predeclared >=10% family-balanced worstS11 MAE reduction; no more false passes; zero shape failures','scope':'6-fold development grouped CV, not independent future accuracy guarantee'})
write('TRAINING_CHECK.json',{'offline_reproduction':True,'HFSS_calls':0,'all_models_fitted_on_development_only':True})
