import copy,unittest
from prospective_report import *
class Tests(unittest.TestCase):
    def setUp(self):
        registry=read(REGISTRY);self.d=copy.deepcopy(registry["designs"][0])
        par=self.d["prediction"]["parameters"]
        self.q=dict(data_role="prospective_test",geometry_mm=copy.deepcopy(self.d["geometry_mm"]),topology=self.d["topology"],
             circuit=dict(parameters={k:par[k] for k in ("zm_eff","zs_eff","fm_GHz","fs_GHz")},extraction_nonunique=False),
             bandwidths=copy.deepcopy(self.d["prediction"]["lossless_circuit_bandwidths"]),
             shape=copy.deepcopy(self.d["prediction"]["lossless_circuit_shape"]))
    def test_identity(self):
        r=compare(self.d,self.q);self.assertEqual(r["errors"]["zs_eff_relative_pct"],0.)
    def test_sign_units(self):
        self.q["circuit"]["parameters"]["fs_GHz"]-=.025
        self.assertAlmostEqual(compare(self.d,self.q)["errors"]["fs_GHz_MHz"],25.)
    def test_tuned_rejected(self):
        self.q["data_role"]="tuned_data"
        with self.assertRaises(ValueError):compare(self.d,self.q)
    def test_wrong_geometry_rejected(self):
        self.q["geometry_mm"]["Lm"]+=.001
        with self.assertRaises(ValueError):compare(self.d,self.q)
    def test_nonunique_not_quantified(self):
        self.q["circuit"]["extraction_nonunique"]=True
        self.assertIsNone(compare(self.d,self.q)["errors"]["fs_GHz_MHz"])
    def test_invalid_band_not_envelope(self):
        b=self.q["bandwidths"]["BW15"];b.update(fit_eligible=False,BW_GHz=None,outer_span_GHz=6.5)
        self.assertIsNone(compare(self.d,self.q)["errors"]["BW15_MHz"])
    def test_missing_not_zero(self):
        self.assertEqual(stats([None,float("nan")])["n"],0)
        self.assertIsNone(stats([])["mae"])
    def test_no_false_lossy_prediction(self):
        r=compare(self.d,self.q);self.assertTrue(r["HFSS_BW_S21_prediction_absent"])
        self.assertIsNone(r["HFSS_BW_S21_prediction_error"])
    def test_no_mutation(self):
        a,b=copy.deepcopy(self.d),copy.deepcopy(self.q);compare(self.d,self.q)
        self.assertEqual(a,self.d);self.assertEqual(b,self.q)
if __name__=="__main__":unittest.main()
