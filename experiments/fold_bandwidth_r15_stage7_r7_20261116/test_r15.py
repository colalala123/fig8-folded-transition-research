"""R15 offline tests; no AEDT, sockets or solver calls."""
import ast,copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from common_stage2 import *
import stage7,prepare_r10 as prep,budget_stage2 as budget
from unittest.mock import patch

class R15Tests(unittest.TestCase):
    def test_01_default_margin(self):
        a=stage7.margin();self.assertAlmostEqual(a['P_req_dB'],-23.153557779873);self.assertLess(abs(a['P_req_dB']+23.15),.005)
    def test_02_table_discrepancy_detected_not_hidden(self):
        bad=[r for r in stage7.margin_table() if not r['within_0p005']];self.assertEqual(len(bad),1);self.assertEqual((bad[0]['tol_h_mm'],bad[0]['mode']),(.025,'corner'));self.assertGreater(abs(bad[0]['error_dB']),.005)
    def test_03_statistical_default(self):self.assertAlmostEqual(stage7.margin(statistical=True)['P_req_dB'],-22.70012165399946)
    def test_04_thickness_scaling(self):self.assertAlmostEqual(stage7.margin(.025)['corner_dGamma'],.026838-.020355+.020355*.025/.038)
    def test_05_bad_h(self):
        for h in (0.,-.01,float('nan'),.9):
            with self.assertRaises(ValueError):stage7.margin(h)
    def test_06_dense_initial(self):self.assertEqual(dense_next_stage([]),('adaptive_00',16,30))
    def test_07_dense_below200(self):self.assertIsNotNone(dense_next_stage([(20,199999,.0001)])[2])
    def test_08_dense200_good(self):self.assertEqual(dense_next_stage([(21,200000,.002)]),('final_sweep',21,None))
    def test_09_dense219_bad_continues(self):self.assertEqual(dense_next_stage([(26,219999,.003)])[2],5)
    def test_10_dense220_any_residual(self):self.assertEqual(dense_next_stage([(26,220000,.03)]),('final_sweep',26,None))
    def test_11_dense247_sweeps(self):self.assertIsNone(dense_next_stage([(27,247756,.0023507)])[2])
    def test_12_dense300_sweeps(self):self.assertIsNone(dense_next_stage([(28,300000,.1)])[2])
    def test_13_dense_over300_strict(self):
        with self.assertRaises(RuntimeError) as e:dense_next_stage([(28,300001,.001)])
        self.assertNotIsInstance(e.exception,NumericalStop)
    def test_14_dense_cap(self):
        with self.assertRaises(NumericalStop):dense_next_stage([(34,210000,.003)])
    def test_15_dense_cadence(self):
        for n,r in [(149999,30),(150000,10),(184999,10),(185000,5)]:self.assertEqual(dense_next_stage([(20,n,.003)])[2],r)
    def test_16_ordinary_unchanged(self):
        self.assertEqual(next_stage([(23,105000,.004)]),('final_sweep',23,None))
        with self.assertRaises(NumericalStop):next_stage([(23,112001,.004)])
    def test_17_t1_geometry_and_J(self):
        d,p=stage7.t1(stage7.margin());self.assertTrue(d['screen']['can_submit']);self.assertEqual(d['geometry_mm']['Wm'],2.65);self.assertTrue(all(abs(x)<=.04 for x in p['differences_from_reference_mm'].values()));self.assertNotEqual(d['geometry_mm'],p['nearby_proxy_geometry_mm']);self.assertEqual(d['target_y'][0],6.735)
    def test_18_ground_and_ports(self):
        d,_=stage7.t1(stage7.margin());c=stage7.build_design(d['geometry_mm'],'C1W','CONTROL',e=.01,er=3.5,h=.775)
        self.assertEqual(c['cad_ir']['rectangles']['ground'],[[-15.,-25.,15.,25.]])
        self.assertAlmostEqual(c['cad_ir']['port_height_mm'],8*.775);self.assertEqual(c['cad_ir']['port_width_mm'],15.04)
    def sample(self,center=6.735,delta=0.,shift=0.):
        req=stage7.margin()['P_req_dB'];mean=req-.1+shift
        return dict(shape=dict(shape_valid=True,central_valley_GHz=center,inner_peaks=[dict(GHz=5.,S11_dB=mean-delta/2),dict(GHz=8.,S11_dB=mean+delta/2)]),bandwidths=dict(BW20=dict(BW_GHz=6.3)))
    def test_19_nominal_pass(self):self.assertTrue(stage7.nominal_check(self.sample(),stage7.margin()['P_req_dB'],-1.5)['tuned'])
    def test_20_center_below_window_fails(self):self.assertFalse(stage7.nominal_check(self.sample(center=6.71),stage7.margin()['P_req_dB'],-1.)['tuned'])
    def test_21_center_above_window_fails(self):self.assertFalse(stage7.nominal_check(self.sample(center=6.76),stage7.margin()['P_req_dB'],-1.)['tuned'])
    def test_22_peak_edges(self):
        req=stage7.margin()['P_req_dB'];self.assertTrue(stage7.nominal_check(self.sample(delta=.2),req,-1.)['tuned']);self.assertFalse(stage7.nominal_check(self.sample(shift=.101),req,-1.)['tuned'])
    def test_23_s21_and_missing(self):
        q=self.sample();req=stage7.margin()['P_req_dB'];self.assertFalse(stage7.nominal_check(q,req,-2.001)['tuned']);self.assertFalse(stage7.nominal_check(q,req)['tuned']);q['bandwidths']['BW20']['BW_GHz']=None;self.assertFalse(stage7.nominal_check(q,req,-1.)['tuned'])
    def test_24_stat_three_labels(self):
        m=stage7.margin();n=dict(center_GHz=6.735,low_peak_dB=-23.2,high_peak_dB=-23.2)
        d={**n,'high_peak_dB':-23.1};c={**n,'high_peak_dB':-20.4}
        self.assertEqual(stage7.confirmation(n,d,c,.002,m)['statistical_label'],'统计稳健（含网格残差）')
        self.assertEqual(stage7.confirmation(n,d,c,.02,m)['statistical_label'],'统计稳健（不含网格残差，边缘）')
        self.assertEqual(stage7.confirmation(n,{**d,'high_peak_dB':-20},c,.002,m)['statistical_label'],'不满足统计稳健')
    def test_25_borrowed_bias(self):
        n=dict(center_GHz=6.735,low_peak_dB=-23.2,high_peak_dB=-23.2);x=stage7.confirmation(n,None,n,None,stage7.margin());self.assertEqual(x['corner_bias_used'],.002538);self.assertEqual(x['corner_bias_source'],'borrowed_B1R_unconfirmed')
    def test_26_bias_no_free_margin(self):
        n=dict(center_GHz=6.735,low_peak_dB=-23.2,high_peak_dB=-23.2);d={**n,'low_peak_dB':-23.3,'high_peak_dB':-23.3};self.assertEqual(stage7.confirmation(n,d,n,.001,stage7.margin())['own_nonnegative_mesh_dGamma'],0)
    def test_27_observer_capture_unchanged(self):
        f=lambda p:ast.dump(next(n for n in ast.parse(p.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name=='capture'))
        self.assertEqual(f(HERE/'observer_r13.py'),f(stage7.PRIOR_H/'observer_r13.py'))
    def cfg(self):
        p='S7R15_W4R';case=p+'__T1';return dict(execution_revision='R15_STAGE7_R7',batch_geometry_limit=6,total_geometry_limit=202,prior_geometry_total=196,prior_Analyze_total=1880,case_specs={case:dict(parent_id=p,attempt_ordinal=1,numerical_retry=False)},inherited_geometry_logicals=[],inherited_logical_Analyze={})
    def test_28_exact_charge_and_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/'ledger').mkdir();write(r/'authorization.json',self.cfg());f=dict(logical_case='S7R15_W4R__T1',parent_id='S7R15_W4R',attempt_ordinal=1,numerical_retry=False,design={});rec=dict(Analyze_requested=0)
            budget.charge(r,f['logical_case'],'adaptive_00',rec,f);self.assertEqual(rec['Analyze_requested'],1);self.assertEqual(len(list((r/'ledger').glob('geometry_*'))),1)
            with self.assertRaises(RuntimeError):budget.charge(r,f['logical_case'],'adaptive_00',rec,f)
    def test_29_budget_caps(self):
        for dense,cap in [(False,14),(True,20)]:
            with tempfile.TemporaryDirectory() as t:
                r=Path(t);(r/'ledger').mkdir();write(r/'authorization.json',self.cfg());f=dict(logical_case='S7R15_W4R__T1',parent_id='S7R15_W4R',attempt_ordinal=1,numerical_retry=False,design=dict(dense_confirmation=dense))
                for i in range(cap):write(r/'ledger'/f'Analyze_x_{i}.json',dict(logical_case=f['logical_case'],stage=f'adaptive_{i:02d}'))
                with self.assertRaises(NumericalStop):budget.charge(r,f['logical_case'],'final_sweep',dict(Analyze_requested=cap),f)
    def test_30_pause_hard(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);write(r/'PAUSE.json',{})
            with self.assertRaises(RuntimeError):budget.charge(r,'x','adaptive_00',{}, {})
    def test_31_old_history_hashes(self):
        from freeze_r15 import source_checks
        self.assertTrue(source_checks())
    def test_32_prediction_verbatim(self):
        d=read(HERE/'DRAFT_R15.json');q=(REPO/stage7.PLAN).read_text(encoding='utf-8').split('## 4. 新登记的预测')[1].split('## 5. 报告')[0];self.assertEqual(d['Q27_Q30_verbatim'],q)
    def test_33_active_default_table_passes_without_waiving_other_rows(self):
        m=stage7.margin();active=[r for r in stage7.margin_table() if r['tol_h_mm']==m['tol_h_mm'] and r['mode']==m['mode']]
        self.assertEqual(len(active),1);self.assertTrue(active[0]['within_0p005']);self.assertTrue(any(not r['within_0p005'] for r in stage7.margin_table()))
    def test_34_stage8_no_implicit_authorization(self):
        text=(HERE/'freeze_r15.py').read_text(encoding='utf-8-sig');self.assertIn('no_stage8=True',text);self.assertIn('new_geometry_cap=6,total_geometry_cap=202',text)
if __name__=='__main__':unittest.main(verbosity=2)
