"""Pure offline accounting/release regression; uses disposable fake ledgers."""
import copy,sys,tempfile,unittest
from pathlib import Path
import budget_stage2 as b
from common_stage2 import read,write,NumericalStop,dense_next_stage
import prepare_r10 as p,manage,runtime_stage2

class RuntimeTests(unittest.TestCase):
    def fake(self,root):
        root.mkdir();(root/'ledger').mkdir();c='S6R10_P1__T1'
        f=dict(logical_case=c,parent_id='S6R10_P1',attempt_ordinal=1,numerical_retry=False,design=dict(dense_confirmation=False))
        cfg=dict(execution_revision='R10_STAGE6_R2',batch_geometry_limit=19,total_geometry_limit=200,prior_geometry_total=181,
            case_specs={c:dict(parent_id='S6R10_P1',attempt_ordinal=1,numerical_retry=False),c+'__NR1':dict(parent_id='S6R10_P1',attempt_ordinal=1,numerical_retry=True)})
        write(root/'authorization.json',cfg);return c,f
    def test_01_finite_schema(self):
        self.assertEqual(len(p.INITIAL),15);self.assertEqual(len(p.ORDER),23)
        self.assertEqual(p.ORDER[:15],[f'P{i}' for i in range(1,15)]+['N0']);self.assertEqual(p.ORDER[-2:],['W3','W4'])
    def test_02_primary_exactly_once(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r);rec={'Analyze_requested':0};b.charge(r,c,'adaptive_00',rec,f)
            self.assertEqual(rec['Analyze_requested'],1);self.assertEqual(len(list((r/'ledger').glob('geometry_*.json'))),1)
            with self.assertRaises(FileExistsError):b.charge(r,c,'adaptive_00',{'Analyze_requested':0},f)
    def test_03_unregistered_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r)
            with self.assertRaises(RuntimeError):b.charge(r,c+'BAD','adaptive_00',{'Analyze_requested':0},f)
    def test_04_retry_shared_cap(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r);rec={'Analyze_requested':0}
            for i in range(13):b.charge(r,c,f'adaptive_{i:02d}',rec,f)
            f['numerical_retry']=True;b.charge(r,c+'__NR1','adaptive_00',{'Analyze_requested':0},f)
            with self.assertRaises(NumericalStop):b.charge(r,c+'__NR1','adaptive_01',{'Analyze_requested':1},f)
            self.assertEqual(len(list((r/'ledger').glob('geometry_*.json'))),1)
    def test_05_final_once(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r);rec={'Analyze_requested':0};b.charge(r,c,'adaptive_00',rec,f);b.charge(r,c,'final_sweep',rec,f)
            with self.assertRaises(RuntimeError):b.charge(r,c,'final_sweep',rec,f)
    def test_06_pause_is_hard_gate(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)/'r';c,f=self.fake(r);write(r/'PAUSE.json',{'human':True})
            with self.assertRaises(RuntimeError):b.charge(r,c,'adaptive_00',{'Analyze_requested':0},f)
            with self.assertRaises(RuntimeError):runtime_stage2.verify_release(r,c)
    def test_07_dense_limits(self):
        self.assertEqual(dense_next_stage([]),('adaptive_00',16,30));self.assertEqual(dense_next_stage([(27,208000,.0018)]),('final_sweep',27,None))
        with self.assertRaises(NumericalStop):dense_next_stage([(28,240001,.001)])
    def test_08_baseline_real_archive(self):
        b0=manage.baseline();bd=manage.baseline(True)
        self.assertTrue(b0['actual_view_ack']);self.assertAlmostEqual(b0['high_peak_dB'],-20.6866488858579)
        self.assertAlmostEqual(bd['high_peak_dB']-b0['high_peak_dB'],.25582492568600657)
    def test_09_cost_carry_exact(self):
        c=[f'S6R10_P{i}__T1' for i in range(1,9)];g=[dict(logical_case=x) for x in c]
        a=[dict(logical_case=x) for x,n in zip(c,[10,10,11,12,10,12,11,11]) for _ in range(n)]
        self.assertEqual(p.carry_totals(g,a),(181,1720,19))
    def test_10_carry_wrong_identity_rejected(self):
        c=[f'S6R10_P{i}__T1' for i in range(1,9)];g=[dict(logical_case=x) for x in c]
        a=[dict(logical_case=x) for x,n in zip(c,[10,10,11,12,10,12,11,11]) for _ in range(n)];a[-1]['logical_case']='S6R10_P9__T1'
        with self.assertRaises(RuntimeError):p.carry_totals(g,a)
    def test_11_carry_hidden_overrun_rejected(self):
        c=[f'S6R10_P{i}__T1' for i in range(1,9)];g=[dict(logical_case=x) for x in c]
        a=[dict(logical_case=c[0]) for _ in range(80)]+[dict(logical_case=x) for x in c[1:]]
        with self.assertRaises(RuntimeError):p.carry_totals(g,a)

if __name__=='__main__':unittest.main(verbosity=2)
