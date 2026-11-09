"""Read-only predictor. Does not launch HFSS or claim predicted compliance is verified."""
from lib import *
from scipy.spatial import ConvexHull
import argparse

def prediction(g,low=3.92,high=9.52):
 if set(g)!={'Wm','Ws','Lm','Ls1','Ls2','Ls3'} or not all(np.isfinite(v) and v>0 for v in g.values()):raise ValueError('Exactly six positive finite geometry dimensions required')
 if not np.isfinite(low) or not np.isfinite(high) or not .01<=low<high<=15:raise ValueError('Band outside native sweep')
 x,c=features(g);x=np.array(x);arm=c['a']
 if not any(abs(arm-a)<1e-8 for a in [1.4,1.8]):raise ValueError('Only a=1.4 or1.8mm supported')
 data=read(ROOT/'DATASET.json');aa=np.load(ROOT/'dataset.npz');dev=np.array([i for i,r in enumerate(data['rows']) if r['source']!='diagnostic_holdout' and abs(r['a']-arm)<1e-8]);xx=aa['X'][dev][:,[0,1,3,4]];mu=xx.mean(axis=0);sd=xx.std(axis=0);h=ConvexHull((xx-mu)/sd);v=(x[[0,1,3,4]]-mu)/sd
 violation=float(max(h.equations[:,:-1]@v+h.equations[:,-1]))
 if violation>1e-7:raise ValueError(f'Outside supported actual-length/P/R joint convex hull: {violation}')
 assert 2*g['Ls3']/g['Ls1']<=.5 and (g['Ls1']-2*g['Ls3']-g['Wm'])/2>=.813,'Geometric screen failed'
 fm=np.load(ROOT/'complex_formula.npz');z=fm['intercept']+np.einsum('i,ifk->fk',x,fm['coefficients']);f=fm['f_GHz'];q=assess(f,z,{**TARGET,'f_low_GHz':low,'f_high_GHz':high,'BW_GHz':high-low});db=20*np.log10(np.maximum(abs(z),1e-15))
 return {'geometry_mm':g,'nominal_PR':c,'band_GHz':[low,high],'prediction':q,'joint20_intervals':intervals(f,db[:,0],db[:,1]),'in_domain':True,'hull_max_violation':violation,'HFSS_verified':False,'certification':'none; mesh-controlled development surrogate only','model_formula_sha256':sha(ROOT/'complex_formula.npz')},z

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in ['Wm','Ws','Lm','Ls1','Ls2','Ls3']:p.add_argument('--'+k,type=float,required=True)
 p.add_argument('--f-low',type=float,default=3.92);p.add_argument('--f-high',type=float,default=9.52);a=p.parse_args()
 try:r,z=prediction({k:getattr(a,k) for k in ['Wm','Ws','Lm','Ls1','Ls2','Ls3']},a.f_low,a.f_high)
 except (ValueError,AssertionError) as e:p.error(str(e))
 print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False))
if __name__=='__main__':main()
