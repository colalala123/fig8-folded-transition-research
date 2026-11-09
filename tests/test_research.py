"""Offline regression checks; no solver or network import. Run from any cwd."""
from pathlib import Path
import hashlib,json,sys,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from lib import features,label,load_curve,read,LABELS,intervals
from predict_response import prediction
D=read(ROOT/'model/DATASET.json');A=np.load(ROOT/'model/dataset.npz',allow_pickle=False)
FINAL=read(ROOT/'results/inverse_case/FINAL_RESULTS.json')
class ResearchTests(unittest.TestCase):
 def test_01_dataset_scope(self):
  self.assertEqual(len(D['rows']),80)
  self.assertEqual(len({r['case'] for r in D['rows']}),80)
  self.assertEqual(sum(r['source']=='diagnostic_holdout' for r in D['rows']),2)
  self.assertEqual(len({r['family'] for r in D['rows']}),24)
  self.assertNotIn('INV01_A14',{r['case'] for r in D['rows']})
 def test_02_features_replay(self):
  for i,r in enumerate(D['rows']):np.testing.assert_allclose(features(r['geometry'])[0],A['X'][i],atol=1e-12,rtol=0)
 def test_03_all_raw_curves(self):
  idx=read(ROOT/'data/RAW_INDEX.json');self.assertEqual(len(idx),81)
  for r in idx:
   p=ROOT/r['curve'];self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),r['curve_sha256'])
   f,z=load_curve(p);self.assertEqual(len(f),1500)
   if r['case']!='INV01_A14':
    i=next(i for i,v in enumerate(D['rows']) if v['case']==r['case'])
    np.testing.assert_allclose(f,A['f'],atol=1e-12,rtol=0);np.testing.assert_allclose(z,A['Z'][i],atol=1e-12,rtol=0)
 def test_04_scores_replay(self):
  for i,r in enumerate(D['rows']):
   q=label(A['f'],A['Z'][i]);self.assertEqual(q['passed'],r['score']['passed'])
   for k in LABELS:self.assertAlmostEqual(q[k],r['score'][k],places=10)
 def test_05_domain_replay(self):
  for r in D['rows']:
   if r['source']!='diagnostic_holdout':
    q,z=prediction(r['geometry']);self.assertTrue(q['in_domain']);self.assertFalse(q['HFSS_verified'])
 def test_06_invalid_inputs_rejected(self):
  g=FINAL['geometry']
  for bad in [{**g,'Lm':100},{**g,'Wm':float('nan')},{**g,'Ls3':g['Ws']+1.6},{**g,'Ls2':g['Ls2']+.1}]:
   with self.assertRaises((ValueError,AssertionError)):prediction(bad)
 def test_07_frozen_prediction(self):
  q,z=prediction(FINAL['geometry'])
  for k in ['worst_S11_dB','min_S21_dB','central_valley_GHz','peak_difference_dB']:
   self.assertAlmostEqual(q['prediction'][k],FINAL['predicted'][k],places=9)
  self.assertFalse(q['HFSS_verified'])
 def test_08_single_case_actual(self):
  f,z=load_curve(ROOT/'data/raw/INV01_A14/sparams.csv');q=label(f,z)
  self.assertTrue(q['passed'])
  for k in LABELS:self.assertAlmostEqual(q[k],FINAL['actual'][k],places=9)
  self.assertGreater(q['worst_S11_dB'],-20.4)
 def test_09_disjoint_family_folds(self):
  ts=read(ROOT/'model/FOLDS_AND_TUNING.json')
  for r in ts:
   if 'fold' in r:self.assertFalse(set(r['train_families'])&set(r['test_families']))
  self.assertEqual(sum('fold' in r for r in ts),18)
 def test_10_formula_refit(self):
  # Refit only the already-selected deployment model; no hyperparameter selection on new case.
  from models import fit,predict,decode,dev,X
  m=fit(dev,'C',{'degree':1,'alpha':.01});z=decode(predict(m,X))
  c=np.load(ROOT/'model/complex_formula.npz',allow_pickle=False)
  actual=c['intercept'][None]+np.einsum('ni,ifk->nfk',X,c['coefficients'])
  np.testing.assert_allclose(z,actual,atol=1e-10,rtol=0)
 def test_11_intersection_keeps_interior(self):
  # Different constraints fail opposite endpoints, but middle is valid.
  q=intervals(np.array([0.,1.]),np.array([-21.,-19.]),np.array([-3.,1.]))
  np.testing.assert_allclose(q,[[.25,.5]],atol=1e-12)
if __name__=='__main__':unittest.main(verbosity=2)
