"""离线门槛回归；不读运行目录、不启动HFSS。"""
import unittest
from gate_1a_r6 import validate,BASES
class Gate(unittest.TestCase):
    def rows(self):
        return [dict(case=c,numerical_pass=True,baseline_pass=True,design_pass=False) for c in BASES]
    def hyp(self):return dict(first_role='-port_adapt',port_preparation_observed=True)
    def test_nonpassing_design_can_be_reproduced(self):
        self.assertTrue(validate(self.rows(),self.hyp())['passed'])
    def test_missing_case(self):
        self.assertFalse(validate(self.rows()[:2],self.hyp())['passed'])
    def test_failed_baseline(self):
        r=self.rows();r[1]['baseline_pass']=False
        self.assertFalse(validate(r,self.hyp())['passed'])
    def test_failed_numerics(self):
        r=self.rows();r[1]['numerical_pass']=None
        self.assertFalse(validate(r,self.hyp())['passed'])
    def test_first_role_and_pending_review(self):
        self.assertFalse(validate(self.rows(),dict(first_role='-solve',port_preparation_observed=False))['passed'])
        self.assertFalse(validate(self.rows(),self.hyp(),True)['passed'])
if __name__=='__main__':unittest.main()
