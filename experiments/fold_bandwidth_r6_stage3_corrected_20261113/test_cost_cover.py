"""保留原批五个几何，禁止修正版重置预算或生成第四次。"""
import unittest,tempfile
from pathlib import Path
from common_stage2 import *
from budget_stage2 import charge
class CostCover(unittest.TestCase):
    def setup(self,td,prior=0):
        root=Path(td);(root/'ledger').mkdir()
        write(root/'authorization.json',dict(batch='3',limits=LIMITS,case_paths={'new':'runs/new'},parent_order=['p'],
            designs={'p':dict(max_Analyze=3)},prior_geometry_total=105,stage3_prior_geometry=5,
            prior_parent_geometry={'p':prior}))
        return root,dict(Analyze_requested=0),dict(parent_id='p',attempt_ordinal=3,design=dict(data_role='tuned_data'))
    def test_no_fourth(self):
        with tempfile.TemporaryDirectory() as td:
            root,r,f=self.setup(td,3)
            with self.assertRaises(RuntimeError):charge(root,'new','adaptive_00',r,f)
            self.assertEqual(list((root/'ledger').iterdir()),[])
    def test_last_original_slot(self):
        with tempfile.TemporaryDirectory() as td:
            root,r,f=self.setup(td,2);charge(root,'new','adaptive_00',r,f)
            self.assertEqual(r['Analyze_requested'],1)
            self.assertEqual(len(list((root/'ledger').glob('geometry*'))),1)
    def test_37_plus_old5_is_full(self):
        with tempfile.TemporaryDirectory() as td:
            root,r,f=self.setup(td)
            for i in range(37):write(root/'ledger'/f'geometry_old{i}.json',dict(parent_id='other'))
            with self.assertRaises(RuntimeError):charge(root,'new','adaptive_00',r,f)
            self.assertFalse((root/'ledger/geometry_new.json').exists())
if __name__=='__main__':unittest.main()
