"""R6离线噪声报告回归；只用构造数据。"""
import copy
import unittest
from analyze_stage1_r6 import analyze,BASES,STEPS,REPO,read
class Stage1(unittest.TestCase):
    def fixture(self):
        c=read(REPO/'experiments/fold_bandwidth_r1_20261110/STAGE1_CRITERIA.json')
        f={r['id']:r['geometry_mm'] for r in read(REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json')['designs']}
        def row(case,x=0):
            return dict(id=case,geometry_mm=f[case],metrics={k:1.+x for k in c['noise_metrics']},
                mesh_cells=101000,MaxDeltaS=.005,final_delta_s=.002,sweep_low_GHz=.01,sweep_high_GHz=15.)
        old=[row(case) for case in BASES];new=copy.deepcopy(old)
        for q in new:q['metrics']['inner_peak_low_dB']+=.18
        return dict(archive=old,baseline=new,perturbations=[row(case,x) for case,x in zip(STEPS,c['width_delta_mm'])]),[dict(case=case,baseline_pass=True,numerical_pass=True) for case in BASES]
    def test_old_peak_threshold_not_gate(self):
        d,g=self.fixture();r=analyze(d,g)
        self.assertTrue(r['batch1b_outputs_complete'])
        self.assertFalse(r['superseded_baseline_comparisons_information_only'][0]['passed'])
        self.assertFalse(r['noise_threshold_added'])
    def test_new_comparison_still_required(self):
        d,g=self.fixture();g[1]['baseline_pass']=False
        self.assertFalse(analyze(d,g)['batch1b_outputs_complete'])
    def test_final_delta_is_required(self):
        d,g=self.fixture();d['perturbations'][0]['final_delta_s']=.006
        self.assertFalse(analyze(d,g)['numerical_checks_passed'])
    def test_no_imputation(self):
        d,g=self.fixture();d['perturbations'][0]['metrics']['inner_peak_low_dB']=None
        r=analyze(d,g)
        self.assertFalse(r['perturbation_noise']['inner_peak_low_dB']['available'])
        self.assertFalse(r['batch1b_outputs_complete'])
    def test_absent_bw20_kept_null(self):
        d,g=self.fixture()
        for r in d['perturbations']:r['metrics']['BW20_GHz']=None
        r=analyze(d,g)
        self.assertTrue(r['batch1b_outputs_complete'])
        self.assertFalse(r['perturbation_noise']['BW20_GHz']['available'])
if __name__=='__main__':unittest.main()
