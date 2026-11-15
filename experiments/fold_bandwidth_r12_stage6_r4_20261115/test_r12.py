"""Real inherited-config preparation regressions. Temp-only, no AEDT/network."""
import copy, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from common_stage2 import *
import r12, prepare_r10 as p, native_control as nc, geometry_gate as gg, budget_stage2 as budget

class R12Tests(unittest.TestCase):
    def fixture(self,r):
        cfg=copy.deepcopy(read(r12.PRIOR_R/'authorization.json'))
        cfg.update(cancelled_parents=[],inherited_closed_parents=[],case_paths={},case_specs={})
        for n,ii in [('P1dense',[1]),('P2dense',[1]),('B1R',[1,2,3]),('B1Rdense',[1]),('C1R',[1]),('W3',[4]),('W4',[1,2])]:
            for i in ii:
                par='S6R10_'+n;c=par+f'__T{i}';cfg['case_paths'][c]=f'runs/{n}/{i}';cfg['case_specs'][c]=dict(parent_id=par,attempt_ordinal=i,numerical_retry=False)
        r.mkdir();(r/'decisions').mkdir();(r/'model_freeze').mkdir();(r/'public').mkdir();(r/'public/pre_solve').mkdir()
        (r/'public/freeze_6B').mkdir();shutil.copyfile(HERE/'freeze_6B/R10_2.json',r/'public/freeze_6B/R10_2.json')
        write(r/'authorization.json',cfg);write(r/'decisions/6A_PRIMARY.json',dict(conditional_dense_required=True))
        return cfg
    def test01_real_failure_config_spec_make_input_equivalence(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';cfg=self.fixture(r)
            for n in ('P1','P2'):
                old=cfg['designs']['S6R10_'+n]['cad_ir']
                self.assertNotIn('board_policy',old)
                with self.assertRaises(RuntimeError):gg.check_ir(old)
                with patch.object(p,'HERE',r/'public'):
                    result=p.make_input(r,'S6R10_'+n+'dense',1)
                f=read(p.case_dir(r,result['case'],cfg)/'input/freeze.json');ir=f['design']['cad_ir']
                self.assertEqual(ir['board_policy'],'fixed_milled_outline');self.assertTrue(gg.check_ir(ir)['passed'])
                self.assertEqual(ir['geometry_mm'],old['geometry_mm']);self.assertEqual(ir['expected_slot_boxes'],old['expected_slot_boxes'])
                self.assertEqual(nc.expected_objects(ir),nc.expected_objects(old))
    def test02_all_eight_new_branches_real_make_input(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';cfg=self.fixture(r)
            cfg['designs']['S6R10_B1R']=read(HERE/'freeze_6B/R10_2.json')['designs']['S6R10_B1R']
            (r/'authorization.json').unlink();write(r/'authorization.json',cfg)
            with patch.object(p,'HERE',r/'public'):
                first=p.make_input(r,'S6R10_B1R',1);firstpath=p.case_dir(r,first['case'],cfg)
                (firstpath/'review').mkdir();write(firstpath/'review/extraction_R2.json',{'test_only':True})
                write(r/'decisions/S6R10_B1R_FINAL.json',dict(passed=True,selected_case=first['case']))
                g=cfg['designs']['S6R10_B1R']['geometry_mm'];sg=dict(needs_solve=True,geometry_mm=g,screen=cfg['designs']['S6R10_B1R']['screen'],predicted_y=[6.72,0,-22.55])
                for i in (2,3):
                    if i==3:
                        w=p.case_dir(r,'S6R10_B1R__T2',cfg);(w/'review').mkdir();write(w/'review/extraction_R2.json',{})
                    with patch.object(p,'suggestion',return_value=sg):p.make_input(r,'S6R10_B1R',i)
                for n,i in [('B1Rdense',1),('C1R',1),('W3',4),('W4',1)]:p.make_input(r,'S6R10_'+n,i)
                w=p.case_dir(r,'S6R10_W4__T1',cfg);(w/'review').mkdir();write(w/'review/extraction_R2.json',{})
                sg['geometry_mm']=cfg['designs']['S6R10_W4']['geometry_mm'];sg['screen']=cfg['designs']['S6R10_W4']['screen']
                with patch.object(p,'suggestion',return_value=sg):p.make_input(r,'S6R10_W4',2)
            for path in (r/'runs').rglob('freeze.json'):
                ir=read(path)['design']['cad_ir'];self.assertEqual(ir['board_policy'],'fixed_milled_outline');gg.check_ir(ir)
            self.assertEqual(len(list((r/'runs').rglob('freeze.json'))),8)
    def test03_cancelled_hard(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';cfg=self.fixture(r);cfg['cancelled_parents']=['S6R10_P1dense','S6R10_P2dense','S6R10_C1']
            for n in cfg['cancelled_parents']:
                with self.assertRaises(RuntimeError):p.spec(r,n,cfg)
    def test04_t1_fixed_a_g_follow_ws(self):
        d=read(HERE/'freeze_6B/R10_2.json')['designs']['S6R10_B1R'];g=d['geometry_mm']
        self.assertEqual(g['Wm'],2.35);self.assertAlmostEqual(g['Ls2']-2*g['Ws'],.55);self.assertAlmostEqual(g['Ls3']-g['Ws'],1.8)
        for delta in (-.02,.02):
            q=copy.deepcopy(g);q['Ws']+=delta;q.update(Ls2=2*q['Ws']+.55,Ls3=1.8+q['Ws'])
            dd=p.chain.dimensions(q);self.assertAlmostEqual(dd['a_mm'],1.8);self.assertAlmostEqual(dd['g_mm'],.55)
    def test05_gamma_margin_and_predictions(self):
        b,ms=r12.source_measurements();a=r12.margin(b,ms)
        self.assertAlmostEqual(a['P_req_dB'],-22.451838778053094,places=10)
        self.assertFalse(a['noise_added']);self.assertEqual(a['stage6B_decision'],'try_B1R_max_three')
        self.assertEqual(a['corner_worst_sides'],dict(etch='P9c',er='P11',h='P13'))
        f=read(HERE/'freeze/R12_R4.json');plan=(REPO/'docs/PLAN_20261115_FOLD_BANDWIDTH_R12.md').read_text(encoding='utf-8')
        self.assertEqual(f['Q21_Q24_verbatim'],plan.split('## 4. 新登记的预测')[1].split('## 5.')[0])
    def test06_two_labels_independent_and_bias_nonnegative(self):
        b,ms=r12.source_measurements();a=r12.margin(b,ms)
        n={**b,'low_peak_dB':-22.6,'high_peak_dB':-22.5};d={**n,'low_peak_dB':-22.7,'high_peak_dB':-22.6};c={**n,'high_peak_dB':-19.9}
        x=r12.confirmation(n,d,c,a);self.assertTrue(x['statistical_RSS_robust']);self.assertFalse(x['worst_corner_robust']);self.assertEqual(x['own_upward_mesh_bias_dB'],0)
    def test07_budget_eight_and_dense20(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/'ledger').mkdir();c='S6R10_B1Rdense__T1';par=c.split('__')[0]
            cfg=dict(execution_revision='R12_STAGE6_R4',batch_geometry_limit=8,total_geometry_limit=200,prior_geometry_total=189,prior_Analyze_total=1807,
                case_specs={c:dict(parent_id=par,attempt_ordinal=1,numerical_retry=False)})
            write(r/'authorization.json',cfg);f=dict(logical_case=c,parent_id=par,attempt_ordinal=1,numerical_retry=False,design=dict(dense_confirmation=True));rec=dict(Analyze_requested=0)
            for i in range(20):budget.charge(r,c,f'adaptive_{i:02d}',rec,f)
            with self.assertRaises(NumericalStop):budget.charge(r,c,'adaptive_20',rec,f)
            for i in range(7):write(r/'ledger'/f'geometry_fake{i}.json',{})
            c2='S6R10_W4__T2';cfg['case_specs'][c2]=dict(parent_id='S6R10_W4',attempt_ordinal=2,numerical_retry=False)
            (r/'authorization.json').unlink();write(r/'authorization.json',cfg)
            f.update(logical_case=c2,parent_id='S6R10_W4',attempt_ordinal=2,design={})
            with self.assertRaises(RuntimeError):budget.charge(r,c2,'adaptive_00',dict(Analyze_requested=0),f)

if __name__=='__main__':
    import shutil
    unittest.main(verbosity=2)
