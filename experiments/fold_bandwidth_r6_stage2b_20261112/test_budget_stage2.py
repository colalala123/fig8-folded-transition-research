"""预算与路径纯离线测试；不创建AEDT。"""
import tempfile
import unittest
from pathlib import Path
from common_stage2 import *
from budget_stage2 import charge
class Budget(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name);(self.r/'ledger').mkdir()
        self.cfg=dict(batch='2b',limits=LIMITS,prior_geometry_total=14,case_paths={f'D__T{i}':f'runs/D__T{i}' for i in range(1,5)},parent_order=['D'])
        write(self.r/'authorization.json',self.cfg)
    def tearDown(self):self.tmp.cleanup()
    def freeze(self,i=1):return dict(parent_id='D',attempt_ordinal=i,design=dict(data_role='planned_training' if i==1 else 'tuned_data'))
    def test_geometry_only_once_across_stages(self):
        r=dict(Analyze_requested=0);charge(self.r,'D__T1','adaptive_00',r,self.freeze())
        charge(self.r,'D__T1','adaptive_01',r,self.freeze());charge(self.r,'D__T1','final_sweep',r,self.freeze())
        self.assertEqual(len(list((self.r/'ledger').glob('geometry_*.json'))),1)
        self.assertEqual(len(list((self.r/'ledger').glob('Analyze_*.json'))),3)
    def test_request_after_sweep_rejected(self):
        r=dict(Analyze_requested=0);charge(self.r,'D__T1','adaptive_00',r,self.freeze())
        charge(self.r,'D__T1','final_sweep',r,self.freeze())
        with self.assertRaises(RuntimeError):charge(self.r,'D__T1','final_sweep',r,self.freeze())
    def test_fourth_geometry_rejected(self):
        for i in range(1,4):charge(self.r,f'D__T{i}','adaptive_00',dict(Analyze_requested=0),self.freeze(i))
        with self.assertRaises(RuntimeError):charge(self.r,'D__T4','adaptive_00',dict(Analyze_requested=0),self.freeze(4))
    def test_duplicate_start_not_overwritten(self):
        charge(self.r,'D__T1','adaptive_00',dict(Analyze_requested=0),self.freeze())
        with self.assertRaises(FileExistsError):charge(self.r,'D__T1','adaptive_00',dict(Analyze_requested=0),self.freeze())
    def test_max_fourteen_calls(self):
        r=dict(Analyze_requested=0)
        for i in range(13):charge(self.r,'D__T1',f'adaptive_{i:02d}',r,self.freeze())
        charge(self.r,'D__T1','final_sweep',r,self.freeze())
        with self.assertRaises(RuntimeError):charge(self.r,'D__T1','adaptive_12',r,self.freeze())
    def test_invalid_initial_stage_leaves_no_ledger(self):
        for label in ['final_sweep','adaptive_01','bogus']:
            with self.assertRaises(RuntimeError):charge(self.r,'D__T1',label,dict(Analyze_requested=0),self.freeze())
        self.assertEqual(list((self.r/'ledger').glob('*.json')),[])
    def test_skipped_adaptive_stage_rejected(self):
        r=dict(Analyze_requested=0);charge(self.r,'D__T1','adaptive_00',r,self.freeze())
        with self.assertRaises(RuntimeError):charge(self.r,'D__T1','adaptive_02',r,self.freeze())
        self.assertEqual(len(list((self.r/'ledger').glob('Analyze_*.json'))),1)
    def test_pause_prevents_next_stage_and_charging(self):
        r=dict(Analyze_requested=0);charge(self.r,'D__T1','adaptive_00',r,self.freeze())
        write(self.r/'PAUSE.json',dict(reason='test pause'))
        with self.assertRaises(RuntimeError):charge(self.r,'D__T1','adaptive_01',r,self.freeze())
        self.assertEqual(len(list((self.r/'ledger').glob('Analyze_*.json'))),1)
    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):case_dir(self.r,'E',dict(case_paths={'E':'../outside'}))
if __name__=='__main__':unittest.main()
