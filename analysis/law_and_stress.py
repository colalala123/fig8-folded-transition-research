from models import *
from sklearn.linear_model import Ridge
from scipy.spatial import ConvexHull
m=joblib.load(ROOT/'model_C.joblib');assert m['config']['degree']==1
# Recover exact raw-feature complex linear response coefficients without approximations.
p0=predict(m,np.zeros((1,5)))[0];co=np.stack([predict(m,np.eye(5)[j:j+1])[0]-p0 for j in range(5)])
assert np.max(abs(predict(m,X)-(p0+X@co)))<1e-11
np.savez_compressed(ROOT/'complex_formula.npz',f_GHz=f,intercept=decode(p0[None])[0],coefficients=np.stack([decode(v[None])[0] for v in co]),feature_names=np.array(d['feature_names']))
# Descriptive scalar law, conditional on actual-minus-nominal lengths, not a physical identity.
sc=StandardScaler().fit(X[dev]);u=sc.transform(X[dev]);reg=Ridge(alpha=.1).fit(u,Y[dev,4],sample_weight=weights(dev));coef=reg.coef_/sc.scale_;inter=float(reg.intercept_-sc.mean_@coef)
rng=np.random.default_rng(20261109);bs=[];gf=sorted(set(groups[dev]))
for b in range(400):
 gg=rng.choice(gf,size=len(gf),replace=True);ii=np.concatenate([dev[groups[dev]==g] for g in gg]);w=np.concatenate([np.full(np.sum(groups[dev]==g),1/np.sum(groups[dev]==g)) for g in gg]);w/=w.mean()
 s=StandardScaler().fit(X[ii]);rr=Ridge(alpha=.1).fit(s.transform(X[ii]),Y[ii,4],sample_weight=w);bs.append(rr.coef_/s.scale_)
bs=np.array(bs);law={'label':'descriptive conditional S21 -2dB bandwidth, not joint -20dB bandwidth or causal electromagnetic proof','formula':'BW_GHz = intercept + coefficients dot [lnP,lnR,a,deltaLm,deltaLs1]','intercept':inter,'coefficients':dict(zip(d['feature_names'],coef.tolist())),'bootstrap_5_95_percentile':dict(zip(d['feature_names'],np.quantile(bs,[.05,.95],axis=0).T.tolist())),'R_negative_bootstrap_fraction':float(np.mean(bs[:,1]<0)),'bootstrap_unit':'24 width families; 400 deterministic resamples; selected-development descriptive stability, not calibrated confidence','standardized_design_condition_number':float(np.linalg.cond(np.c_[np.ones(len(u)),u])),'nominal_length_definition':'quarter-wave microstrip and nominal unfolded half-wave slot at6.72GHz, er3.55'}
write('CONDITIONAL_BW_LAW.json',law)
# Cross-fit model variation for offline inverse candidate; this is a stress screen, not a CI.
candidate=read(ROOT/'PR_INVERSE_OFFLINE_ONLY.json')['solutions'][0];x=np.array(candidate['features']);stress=[]
for k,(tr,va) in enumerate(folds(dev,6)):
 cfg=next(r['selected'] for r in read(ROOT/'FOLDS_AND_TUNING.json') if r['model']=='C' and r.get('fold')==k)
 mm=fit(tr,'C',cfg);q=label(f,decode(predict(mm,x[None]))[0]);stress.append({'fold':k,'omitted_families':sorted(set(groups[va])),'score':q})
write('CANDIDATE_STRESS_SCREEN.json',{'candidate':candidate,'fold_models':stress,'passes':sum(r['score']['passed'] for r in stress),'is_confidence_interval':False,'geometry_frozen_for_HFSS':False,'requires_width_change_permission':True})
print('LAW',law);print('STRESS',[(r['fold'],r['score']['passed'],r['score']['worst_S11_dB'],r['score'].get('central_valley_GHz'),r['score'].get('peak_difference_dB')) for r in stress])
write('FORMULA_TESTS.json',{'exact_linear_model_prediction_max_error':float(np.max(abs(predict(m,X)-(p0+X@co)))),'all_training_and_holdout_rows':len(X),'model_C_sha256':sha(ROOT/'model_C.joblib'),'formula_sha256':sha(ROOT/'complex_formula.npz')})
