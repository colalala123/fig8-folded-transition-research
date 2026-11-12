"""覆盖漏测的中心线恒等式；纯离线。"""
import unittest,importlib.util
import numpy as np
from common_stage2 import *
from tuning import propose,chain,MODEL
OLD=HERE.parent/'fold_bandwidth_r6_stage3_20261112'
s=importlib.util.spec_from_file_location('defective_frozen_rule_readonly',OLD/'tuning.py')
bad=importlib.util.module_from_spec(s);s.loader.exec_module(bad)
class TestFix(unittest.TestCase):
    def test_all_registry_centerlines(self):
        rr=read(REPO/'experiments/fold_bandwidth_r3_20261110/freeze_r3/REGISTRY_R3.json')['designs']
        for r in rr:
            g=r['geometry_mm'];d=chain.dimensions(g,r['topology'])
            expected=g['Ls1'] if r['topology']=='straight_control' else g['Ls1']+2*d['a_mm']+2*d['g_mm']+2*g['Ws']
            self.assertAlmostEqual(d['L_centerline_mm'],expected,places=12)
    def test_inverse_identity_all_widths(self):
        for a in (.6,1.4,2.2,2.9):
            for w in (.1,.283,.342,.365,.459,.8):
                g=dict(Wm=1.936496,Ws=w,Lm=6.6,Ls1=12.,Ls2=2*w+.55,Ls3=a+w)
                offset=chain.dimensions({**g,'Ls1':.01})['L_centerline_mm']-.01
                target=18.
                n={**g,'Ls1':round(target-offset,3)}
                self.assertLessEqual(abs(chain.dimensions(n)['L_centerline_mm']-target),.000500001)
    def test_known_folded_regression(self):
        q=read(OLD/'results/S3R3_EQ_N04_01__T1/review/extraction_R2.json')
        old,new=bad.propose(q,.6),propose(q,.6)
        self.assertTrue(new['needs_solve']);self.assertEqual(new['geometry_mm']['Ws'],.365)
        self.assertAlmostEqual(new['geometry_mm']['Ls1'],13.696,places=9)
        self.assertAlmostEqual(new['geometry_mm']['Ls1']-old['geometry_mm']['Ls1'],.730,places=9)
        self.assertLessEqual(abs(new['length_identity']['error_mm']),.000500001)
    def test_straight_unchanged(self):
        q=read(OLD/'results/S3R3_EQ_N04_00__T1/review/extraction_R2.json')
        self.assertEqual(bad.propose(q,0.,'straight_control')['geometry_mm'],propose(q,0.,'straight_control')['geometry_mm'])
if __name__=='__main__':unittest.main()
