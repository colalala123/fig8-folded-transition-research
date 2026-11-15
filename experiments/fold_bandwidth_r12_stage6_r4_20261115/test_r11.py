"""R11 offline regressions; fake ledgers only, never starts AEDT."""
import copy,tempfile,unittest
from pathlib import Path
from common_stage2 import *
import cad_ir,native_control as nc,geometry_gate as gg,budget_stage2 as budget
from native_validation import assess
import prepare_r10 as prep,tolerance_analysis as ta

class R11Tests(unittest.TestCase):
    def base(self):return read(HERE/'freeze/R10_1.json')['stage6A'][0]['base_geometry_mm']
    def ir(self,e=0):return cad_ir.json_value(cad_ir.build(self.base(),e,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'))
    def test01_old_p10_blocked(self):
        ir=read(REPO/'experiments/fold_bandwidth_r10_stage6_r2_20261115/pre_solve/S6R10_P10__T1.json')['design']['cad_ir']
        self.assertFalse(gg.check_envelopes(nc.expected_objects(ir))['passed'])
        with self.assertRaises(RuntimeError):gg.check_ir(ir)
    def test02_both_new_etch_sides(self):
        for e in [-.01,.01]:
            ir=self.ir(e);self.assertTrue(gg.check_ir(ir)['passed']);self.assertEqual(ir['rectangles']['ground'],[[-15.,-25.,15.,25.]])
    def test03_illegal_surface_contact(self):
        o=nc.expected_objects(self.ir());o['Substrate_3'][5]=11.
        self.assertFalse(gg.check_envelopes(o)['passed'])
    def test04_all_seven(self):self.assertEqual(prep.SEVEN,['P10','P9c','P11','P12','P13','P14','N0'])
    def test05_margin_uses_p9c_not_p9(self):self.assertEqual(ta.PAIRS['etch'],('P9c','P10'))
    def test06_native_error_not_accepted(self):
        self.assertFalse(assess(0,'Parts intersect',[])['passed'])
        self.assertFalse(assess(1,'validation log',['[error] Parts intersect'])['passed'])
        self.assertTrue(assess(1,'0 errors, 1 warning',[])['passed'])
        self.assertFalse(assess(1,'',[])['passed'])
    def fake(self,r,p10=False):
        r.mkdir();(r/'ledger').mkdir();c='S6R10_'+('P10' if p10 else 'P9c')+'__T1';p=c.split('__')[0]
        cfg=dict(execution_revision='R12_STAGE6_R4',batch_geometry_limit=8,total_geometry_limit=200,prior_geometry_total=189,prior_Analyze_total=1807,
            case_specs={c:dict(parent_id=p,attempt_ordinal=1,numerical_retry=False),c+'__NR1':dict(parent_id=p,attempt_ordinal=1,numerical_retry=True)},
            inherited_logical_Analyze={'S6R10_P10__T1':1},inherited_geometry_logicals=['S6R10_P10__T1'])
        write(r/'authorization.json',cfg)
        return c,dict(logical_case=c,parent_id=p,attempt_ordinal=1,numerical_retry=False,design={})
    def test07_p10_remaining13_no_geometry_recharge(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r,True);rec={'Analyze_requested':0}
            for i in range(13):budget.charge(r,c,f'adaptive_{i:02d}',rec,f)
            self.assertFalse(list((r/'ledger').glob('geometry_*.json')))
            with self.assertRaises(NumericalStop):budget.charge(r,c,'adaptive_13',rec,f)
    def test08_new_geometry_exactly_once(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r);budget.charge(r,c,'adaptive_00',{'Analyze_requested':0},f)
            self.assertEqual(len(list((r/'ledger').glob('geometry_*.json'))),1)
            with self.assertRaises(FileExistsError):budget.charge(r,c,'adaptive_00',{'Analyze_requested':0},f)
    def test09_numeric_retry_shares14(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r);rec={'Analyze_requested':0}
            for i in range(13):budget.charge(r,c,f'adaptive_{i:02d}',rec,f)
            f['numerical_retry']=True;rec={'Analyze_requested':0};budget.charge(r,c+'__NR1','adaptive_00',rec,f)
            with self.assertRaises(NumericalStop):budget.charge(r,c+'__NR1','adaptive_01',rec,f)
    def test10_pause_hard(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r);write(r/'PAUSE.json',{})
            with self.assertRaises(RuntimeError):budget.charge(r,c,'adaptive_00',{'Analyze_requested':0},f)
    def test11_old_p9_not_rewritten(self):
        old=read(REPO/'experiments/fold_bandwidth_r10_stage6_r2_20261115/pre_solve/S6R10_P9__T1.json')['design']['cad_ir']
        new=self.ir(.01);self.assertEqual(old['rectangles']['ground'],[[-14.99,-25.,14.99,25.]])
        self.assertEqual(old['geometry_mm'],new['geometry_mm']);self.assertEqual(old['expected_slot_boxes'],new['expected_slot_boxes'])

if __name__=='__main__':unittest.main(verbosity=2)
