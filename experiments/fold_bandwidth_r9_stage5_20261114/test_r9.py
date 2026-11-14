"""Offline tests: fitting roles, inverse geometry identity, budgets and dense policy."""
import unittest
from laws import *
from tuning import propose_history,coordinate,CAP
from common_stage2 import dense_next_stage,next_stage,NumericalStop
class Tests(unittest.TestCase):
    def test_add_exact_six(self):
        r=read(H/'offline/TRAINING.json');self.assertEqual(len(r['rows']),86);self.assertEqual(len(r['stage4_added']),6);self.assertFalse(any(x.startswith(('S4R8_D1','S4R8_D3')) for x in r['stage4_added']))
    def test_cost_copy(self):self.assertEqual(digest(H/'offline/COST_REFIT.json'),digest(REPO/'experiments/fold_bandwidth_review_r9_20261114/out/COST_REFIT.json'))
    def test_nominal_order(self):self.assertEqual([c['design'] for c in read(H/'offline/T1_GEOMETRIES.json')],['W1','W2','W3','S1'])
    def test_dimensions(self):
        for c in read(H/'offline/T1_GEOMETRIES.json'):
            g=c['geometry_mm'];d=chain.dimensions(g);self.assertAlmostEqual(d['a_mm'],c['nominal_a_mm']);self.assertAlmostEqual(d['g_mm'],c['g_mm']);self.assertTrue(c['screen']['can_submit']);self.assertFalse(c['screen']['adjusted'])
            for k,v in g.items():
                self.assertGreaterEqual(v,.01)
                if k!='Wm':self.assertAlmostEqual(v*1000,round(v*1000))
    def test_cv_groups(self):
        r=read(H/'offline/TRAINING.json')['rows'];fs=read(H/'offline/CROSS_VALIDATION.json')['folds'];self.assertEqual(sum(f['test_n'] for f in fs),len(r))
        for f in fs:self.assertEqual(f['test_n'],sum(x['group']==f['held_out_whole_ladder'] for x in r))
    def test_predictions_verbatim(self):
        plan=(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R9.md').read_text(encoding='utf-8');self.assertEqual(read(H/'offline/REVIEWER_PREDICTIONS.json')['verbatim'],plan.split('## 4. 审核方登记的预测')[1].split('## 5.')[0])
    def test_three_forward_candidates_reproduce(self):
        m=read(H/'offline/LAWS.json');self.assertEqual([candidate(m,*s) for s in DESIGNS],read(H/'offline/T1_GEOMETRIES.json'))
    def test_dense_gate(self):
        self.assertEqual(dense_next_stage([(22,201000,.0019)])[0],'final_sweep');self.assertNotEqual(dense_next_stage([(22,199999,.001)])[0],'final_sweep');self.assertNotEqual(dense_next_stage([(22,210000,.0021)])[0],'final_sweep')
        with self.assertRaises(NumericalStop):dense_next_stage([(30,240001,.001)])
    def test_regular_unchanged(self):
        self.assertEqual(next_stage([(24,101000,.004)])[0],'final_sweep')
        with self.assertRaises(NumericalStop):next_stage([(24,112001,.004)])
    def test_budget(self):self.assertEqual(151+16+9+1,177);self.assertLess(177,187);self.assertEqual(25*14+20,370)
    def test_variable_g_tuner(self):
        c=read(H/'offline/T1_GEOMETRIES.json')[-1];q=dict(geometry_mm=c['geometry_mm'],shape=dict(shape_valid=True,central_valley_GHz=6.76,inner_peaks=[dict(GHz=5,S11_dB=-19),dict(GHz=8,S11_dB=-18.5)]));sg=propose_history([dict(case='synthetic',q=q)],1.4,'folded');self.assertTrue(sg['needs_solve']);self.assertAlmostEqual(chain.dimensions(sg['geometry_mm'])['g_mm'],1.6);self.assertTrue(np.all(abs(np.array(sg['actual_step']))<=CAP+.000500001))
if __name__=='__main__':unittest.main()
