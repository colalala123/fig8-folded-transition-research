"""纯离线测试；不启动HFSS/网络/消息。"""
import unittest,copy,tempfile
from pathlib import Path
import numpy as np
from common_stage2 import *
from prepare_stage3 import rows
from tuning import classify,propose
from power_analysis import power_s_sanity,lossless_modal_balance
from budget_stage2 import charge
class Tests(unittest.TestCase):
    def setUp(self):
        self.q=read(REPO/'experiments/fold_bandwidth_r6_stage2b_20261112/results/S2_E2_N04_g0.40__T2/review/extraction_R2.json')
    def test_registry(self):
        rr=rows();self.assertEqual(len(rr),22)
        self.assertEqual(sum(r['max_Analyze'] for r in rr),42)
        self.assertEqual(len({r['id'] for r in rr}),22)
        self.assertEqual(sum(r['kind']=='EQ' for r in rr),10)
    def test_initial_exact(self):
        from prepare_stage3 import REG
        original={r['id']:r for r in read(REG)['designs']}
        for r in rows()[:10]:
            self.assertEqual(r['geometry_mm'],original[r['id']]['geometry_mm'])
            self.assertEqual(r['boxes'],r['expected_boxes'])
    def test_lossless_ids(self):
        from prepare_stage3 import REG
        originals={r['id'] for r in read(REG)['designs']}
        self.assertTrue(all(r['id'] in originals for r in rows() if r['kind']=='LOSSLESS'))
    def test_tuned_stops(self):self.assertFalse(propose(self.q,1.8)['needs_solve'])
    def test_hard_peak(self):
        self.q['shape']['inner_peaks'][0]['S11_dB']=-19.99
        self.assertFalse(classify(self.q)['tuned'])
    def test_mean_limit(self):
        for p in self.q['shape']['inner_peaks']:p['S11_dB']=-20.61
        self.assertFalse(classify(self.q)['tuned'])
    def test_gap_strict(self):
        self.q['shape']['inner_peaks'][0]['S11_dB']=-20.001
        self.q['shape']['inner_peaks'][1]['S11_dB']=-20.502
        self.assertFalse(classify(self.q)['tuned'])
    def test_no_nonunique(self):
        self.q['circuit']['extraction_nonunique']=True
        self.q['shape']['inner_peaks'][0]['S11_dB']=-19
        self.assertFalse(propose(self.q,1.8)['needs_solve'])
    def test_proposal(self):
        self.q['shape']['inner_peaks'][0]['S11_dB']=-19.4
        self.q['shape']['inner_peaks'][1]['S11_dB']=-19.5
        r=propose(self.q,1.8);self.assertTrue(r['needs_solve'])
        old=self.q['geometry_mm'];new=r['geometry_mm']
        self.assertEqual(old['Wm'],new['Wm'])
        self.assertAlmostEqual(new['Ls2']-2*new['Ws'],old['Ls2']-2*old['Ws'])
        self.assertTrue(r['screen']['can_submit'])
    def test_duplicate_freeze(self):
        from common_stage2 import write
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.json';write(p,{'a':1})
            with self.assertRaises(FileExistsError):write(p,{'a':2})
    def test_power_absurd_rejected(self):
        d={'S':np.ones((2,4,4),complex)}
        self.assertFalse(power_s_sanity(d)['passive_column_sums_all_frequencies'])
    def data(self):
        S=np.zeros((2,4,4),complex);S[:,2,0]=.9;S[:,1,0]=100
        return dict(f_GHz=np.array([6.,7.]),S=S,
            Zo=np.array([[50,100j,50,100j]]*2,complex),
            Gamma=np.array([[200j,100,200j,100]]*2,complex))
    def test_evanescent_not_counted(self):
        b=lossless_modal_balance(self.data(),True)
        self.assertTrue(np.all(b['valid']))
        np.testing.assert_allclose(b['residual_fraction'],.19)
    def test_lossy_refused(self):self.assertFalse(lossless_modal_balance(self.data(),False)['valid'].any())
    def test_near_cutoff_unknown(self):
        d=self.data();d['Gamma'][:,1]=1+1j
        self.assertFalse(lossless_modal_balance(d,True)['valid'].any())
    def test_nonpassive_not_clipped(self):
        d=self.data();d['S'][:,2,0]=1.1
        self.assertFalse(lossless_modal_balance(d,True)['valid'].any())
    def setup_budget(self,td,kind='EQ'):
        root=Path(td);(root/'ledger').mkdir()
        cfg=dict(batch='3',limits=LIMITS,case_paths={'x':'runs/x'},parent_order=['p'],
           designs={'p':dict(max_Analyze=3 if kind=='EQ' else 1)},prior_geometry_total=100)
        write(root/'authorization.json',cfg)
        f=dict(parent_id='p',attempt_ordinal=1,design=dict(data_role=kind))
        return root,dict(Analyze_requested=0),f
    def test_charge(self):
        with tempfile.TemporaryDirectory() as td:
            r,rec,f=self.setup_budget(td);charge(r,'x','adaptive_00',rec,f)
            self.assertEqual(rec['Analyze_requested'],1)
            self.assertEqual(len(list((r/'ledger').glob('geometry*'))),1)
            charge(r,'x','final_sweep',rec,f)
            with self.assertRaises(RuntimeError):charge(r,'x','final_sweep',rec,f)
    def test_pause_no_write(self):
        with tempfile.TemporaryDirectory() as td:
            r,rec,f=self.setup_budget(td);write(r/'PAUSE.json',{})
            with self.assertRaises(RuntimeError):charge(r,'x','adaptive_00',rec,f)
            self.assertEqual(len(list((r/'ledger').iterdir())),0)
    def test_control_cannot_second(self):
        with tempfile.TemporaryDirectory() as td:
            r,rec,f=self.setup_budget(td,'LOSSLESS');f['attempt_ordinal']=2
            with self.assertRaises(RuntimeError):charge(r,'x','adaptive_00',rec,f)
            self.assertEqual(len(list((r/'ledger').iterdir())),0)
    def test_14_api_cap(self):
        with tempfile.TemporaryDirectory() as td:
            r,rec,f=self.setup_budget(td);rec['Analyze_requested']=14
            with self.assertRaises(RuntimeError):charge(r,'x','adaptive_12',rec,f)
    def test_global_cap(self):
        with tempfile.TemporaryDirectory() as td:
            r,rec,f=self.setup_budget(td)
            cfg=read(r/'authorization.json');cfg['prior_geometry_total']=187
            (r/'authorization.json').write_text(__import__('json').dumps(cfg),encoding='utf-8')
            with self.assertRaises(RuntimeError):charge(r,'x','adaptive_00',rec,f)
            self.assertEqual(len(list((r/'ledger').iterdir())),0)
if __name__=='__main__':unittest.main()
