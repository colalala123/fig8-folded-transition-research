"""合成数据离线测试；不会创建/连接HFSS或网络。"""
import copy
import unittest
import numpy as np
import fit_model as m

def fixtures(kind="ka",k=.045,g0=1.):
    rows=[]
    pairs=[("S2_E1_0",.6,.55),("S2_E1_1",1.,.55),("S2_E1_2",2.2,.55),("S2_E1_3",2.6,.55),
           ("S2_E2_0",1.8,.25),("S2_E2_1",1.8,.4),("S2_E2_2",1.8,.8),("S2_E2_3",1.8,1.2),
           ("S2_E3_0",1.,.25),("S2_E3_1",1.,1.2),("S2_E3_2",2.6,.25),("S2_E3_3",2.6,1.2),
           (None,1.8,.55)]
    for i,(parent,a,gap) in enumerate(pairs):
        wm,ws=1.810636,.394178
        l2,l3=gap+2*ws,a+ws
        ds=m.chain.corrections(wm,ws,a)[1]+.01-.05*a-.02*(gap-.55)
        ls1=m.chain.wave_length(ws,6.588,False)-ds-2*l2-2*l3+4*ws
        g=dict(Wm=wm,Ws=ws,Lm=6.6,Ls1=ls1,Ls2=l2,Ls3=l3)
        r=dict(case=parent or "N14_A18",parent_id=parent,source="stage2a_selected" if parent else "archive_reference",
            topology="folded",geometry_mm=g,length_calibrated=True,numerical_pass=True,fit_unique_under_R2=True,
            circuit=dict(zs_eff=0,fm_GHz=6.622,fs_GHz=6.588))
        r["circuit"]["zs_eff"]=1.75*m.shape_value(kind,r,k,g0)
        rows.append(r)
    return rows

class Tests(unittest.TestCase):
    def test_exact_three_forms(self):
        for kind in m.KINDS:
            r=fixtures(kind);fit=m.fit_kappa(r,kind)
            self.assertLess(fit["relative_max"],1e-7)

    def test_shared_reference_removed_from_both_stairs(self):
        r=fixtures();cv=m.kappa_cv(r,"ka")
        for f in cv["folds"]:
            self.assertFalse(set(f["training_case_ids"]) & set(f["held_case_ids"]))
            if f["held_group"] in ("E1","E2"):
                self.assertIn("N14_A18",f["held_case_ids"])
                self.assertNotIn("N14_A18",f["training_case_ids"])

    def test_exact_group_cv(self):
        for kind in m.KINDS:
            cv=m.kappa_cv(fixtures(kind),kind)
            self.assertTrue(cv["within_1percent_every_point"])

    def test_length_fit_keeps_width_terms(self):
        r=fixtures();f=m.fit_length(r)
        self.assertAlmostEqual(f["delta_intercept_mm"],.01)
        self.assertAlmostEqual(f["delta_a_coefficient"],-.05)
        self.assertAlmostEqual(f["g_minus_0p55_coefficient"],-.02)
        self.assertFalse(f["width_coefficients_refitted"])
        self.assertLess(m.length_cv(r)["max_abs_MHz"],1e-6)

    def test_no_unknown_negative_decay(self):
        with self.assertRaises(ValueError):m.shape_value("ka_exp",fixtures()[0],.1,-1)
        with self.assertRaises(ValueError):m.shape_value("bad",fixtures()[0],.1)

    def test_straight_and_uncalibrated_excluded(self):
        r=fixtures()[0]
        for flag in ("length_calibrated","numerical_pass","fit_unique_under_R2"):
            s=copy.deepcopy(r);s[flag]=False;self.assertFalse(m.eligible(s))
        s=copy.deepcopy(r);s["topology"]="straight_control";self.assertFalse(m.eligible(s))

    def test_straight_kappa_zero(self):
        r=dict(topology="straight_control",geometry_mm=dict(Wm=1.8,Ws=.4,Lm=6.6,Ls1=16.,Ls2=0.,Ls3=0.))
        for kind in m.KINDS:self.assertEqual(m.shape_value(kind,r,.1,1),1.)

    def test_transfer_same_width_consistent(self):
        r=fixtures();model=dict(reference_widths_mm=m.REFERENCE_WIDTHS,kappa=m.fit_kappa(r,"ka"),slot_length=m.fit_length(r))
        before=copy.deepcopy(r[0]["geometry_mm"])
        p=m.forward(before,"folded",model)
        self.assertAlmostEqual(p["zs_eff"],m.fitted_zs(model["kappa"],r[0]),places=12)
        self.assertEqual(before,r[0]["geometry_mm"])
        self.assertAlmostEqual(p["fs_GHz"],6.588,places=9)
        self.assertFalse(p["cross_family_transfer_validated"])

    def test_no_incomplete_freeze(self):
        with self.assertRaises(ValueError):m.build(dict(summary=dict(count_conditions_met=False)))

    def test_underidentified_length_fails(self):
        with self.assertRaises(ValueError):m.fit_length(fixtures()[:4])

    def test_absolute_error_checks_not_average(self):
        q=m.error_summary([0,0,.03])
        self.assertEqual(q["max_abs"],.03)
        self.assertLess(q["MAE"],q["max_abs"])

if __name__=="__main__":unittest.main()
