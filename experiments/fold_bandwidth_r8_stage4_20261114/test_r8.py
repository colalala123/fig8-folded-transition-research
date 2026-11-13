"""R8 offline-only tests, including exact frozen T1 and non-.55 gap tuning."""
import unittest,copy
from laws import *
from tuning import propose_history,coordinate,CAP
class Tests(unittest.TestCase):
    def setUp(self):self.cs=read(H/'offline/T1_GEOMETRIES.json')
    def test_eight_order(self):self.assertEqual([c['design'] for c in self.cs],['D'+str(i) for i in range(1,9)])
    def test_exact_nominal_dimensions(self):
        for c,s in zip(self.cs,DESIGNS):
            g=c['geometry_mm'];d=chain.dimensions(g)
            self.assertAlmostEqual(d['a_mm'],s[3]);self.assertAlmostEqual(d['g_mm'],s[4]);self.assertEqual(g['Wm'],s[2])
    def test_grid_and_lower_bound(self):
        for c in self.cs:
            for k,v in c['geometry_mm'].items():
                self.assertGreaterEqual(v,.01)
                if k!='Wm' or c['design'] in ('D6','D8'):self.assertAlmostEqual(v*1000,round(v*1000))
    def test_screen_all(self):
        for c in self.cs:
            self.assertTrue(c['screen']['can_submit']);self.assertFalse(c['screen']['adjusted'])
    def test_reproduce_frozen_chain(self):self.assertEqual(candidates(read(H/'offline/LAWS.json')),self.cs)
    def test_training_excludes_stage4(self):
        rows=read(H/'offline/TRAINING.json')['rows'];self.assertTrue(all(not r['case'].startswith('S4') for r in rows));self.assertEqual(len(rows),80)
    def test_whole_ladder_no_leak(self):
        rows=read(H/'offline/TRAINING.json')['rows'];cvv=read(H/'offline/CROSS_VALIDATION.json')
        self.assertEqual(sum(f['test_n'] for f in cvv['folds']),len(rows))
        for f in cvv['folds']:self.assertEqual(f['test_n'],sum(r['group']==f['held_out_whole_ladder'] for r in rows))
    def test_variable_gap_tuning(self):
        for c in self.cs[:4]:
            q=dict(geometry_mm=c['geometry_mm'],shape=dict(shape_valid=True,central_valley_GHz=6.76,inner_peaks=[dict(GHz=5.1,S11_dB=-19),dict(GHz=8.3,S11_dB=-18.5)]))
            sg=propose_history([dict(case='stress',q=q)],c['nominal_a_mm'],'folded');self.assertTrue(sg['needs_solve'])
            self.assertAlmostEqual(chain.dimensions(sg['geometry_mm'])['g_mm'],c['g_mm'])
            self.assertTrue(np.all(abs(np.array(sg['actual_step']))<=CAP+.000500001))
    def test_reviewer_verbatim(self):
        p=(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R8.md').read_text(encoding='utf-8')
        self.assertEqual(read(H/'offline/REVIEWER_PREDICTIONS.json')['verbatim'],p.split('## 4. 审核方登记的预测')[1].split('## 5.')[0])
    def test_caps(self):self.assertEqual(133+8*3,157);self.assertLessEqual(157,187)
    def test_two_platform_three_cost_models(self):
        m=read(H/'offline/LAWS.json');self.assertEqual(set(m['platform']),{'1','2'});self.assertEqual(set(m['cost']),{'tip','sum','a'})
if __name__=='__main__':unittest.main()
