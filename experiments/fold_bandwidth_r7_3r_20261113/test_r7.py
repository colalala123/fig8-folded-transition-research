"""Offline tests; never connect AEDT."""
import unittest,copy
import numpy as np
from tuning import *
from prepare_r7 import ORDER,source,parent
class Tests(unittest.TestCase):
    def setUp(self):self.q=json.loads(source('S3R3_EQ_N04_01__T3')[0].read_text(encoding='utf-8-sig'))
    def test_regression(self):
        d=json.loads((HERE/'offline/SENSITIVITY.json').read_text());self.assertTrue(d['passed']);self.assertEqual(d['n'],37)
    def test_all_eight_candidates(self):
        for fam,a,cap,seed in ORDER:
            q=json.loads(source(seed)[0].read_text(encoding='utf-8-sig'));top='folded' if a else 'straight_control'
            r=propose_history([dict(case=seed,q=q)],a,top);self.assertTrue(r['needs_solve']);self.assertTrue(r['screen']['can_submit']);self.assertFalse(r['screen']['adjusted'])
            self.assertTrue(np.all(abs(np.array(r['actual_step']))<=CAP+.000500001));self.assertAlmostEqual(chain.dimensions(r['geometry_mm'],top)['a_mm'],a)
    def test_inverse_identity(self):
        for a in (0,.6,1.,1.8,2.2,2.6):
            for ws in (.25,.4,.6):
                top='folded' if a else 'straight_control';g=self.q['geometry_mm'];x=np.array([6.5,17.432,ws]);c=inverse(g,x,top,a,.55)
                self.assertLess(abs(chain.dimensions(c,top)['L_centerline_mm']-x[1]),.000500001)
    def test_usable(self):
        q=copy.deepcopy(self.q)
        q['shape']['central_valley_GHz']=6.72
        for p in q['shape']['inner_peaks']:p['S11_dB']=-19.8
        self.assertTrue(classify(q)['tuned']);self.assertFalse(classify(q)['hard_design_peaks_pass'])
        q['shape']['inner_peaks'][1]['S11_dB']=-19.1;self.assertFalse(classify(q)['tuned'])
    def test_not_shape(self):
        self.q['shape']['shape_valid']=False;self.assertFalse(classify(self.q)['tuned'])
    def test_broyden_trigger(self):
        dx=np.array([.01,.02,.01]);pred=dx@J0;dy=pred.copy();dy[1]+=abs(pred[1])*.6
        j,log=broyden(J0,dx,dy);self.assertTrue(log['triggered']);np.testing.assert_allclose(dx@j,dy,atol=1e-12)
    def test_broyden_no_small_prediction(self):
        dx=np.array([0.,0.,.001]);j,log=broyden(J0,dx,[.1,.2,.3]);self.assertFalse(log['triggered']);np.testing.assert_equal(j,J0)
    def test_step_cap_scaling(self):
        q=copy.deepcopy(self.q);q['shape']['central_valley_GHz']=7.4
        r=propose_history([dict(case='stress',q=q)],.6,'folded');self.assertLess(r['step_scale'],1)
        self.assertTrue(np.all(abs(np.array(r['actual_step']))<=CAP+.000500001))
    def test_geometry_budget(self):self.assertEqual(sum(t[2] for t in ORDER)+10+2+6,41)
    def test_first_step(self):
        r=propose_history([dict(case='seed',q=self.q)],.6,'folded')
        np.testing.assert_allclose(r['actual_step'],[.016,.091,.001],atol=.001)
if __name__=='__main__':unittest.main()
