"""阶段2进度账本纯文件测试，不连接HFSS。"""
import tempfile
import unittest
from pathlib import Path
import checkpoint_stage2 as cp
from common_stage2 import read,write,LIMITS
class Checkpoint(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='fig8_checkpoint_test_')
        self.r=Path(self.tmp.name);self.old=cp.HERE;cp.HERE=self.r/'public'
        (self.r/'ledger').mkdir();self.w=self.r/'runs/D/attempt_001';(self.w/'evidence').mkdir(parents=True)
        write(self.r/'authorization.json',dict(case_paths={'D__T1':'runs/D/attempt_001'},prior_Analyze_total=91,prior_geometry_total=14))
    def tearDown(self):cp.HERE=self.old;self.tmp.cleanup()
    def test_only_closed_roles_count(self):
        for i in range(9):
            label=f'adaptive_{i:02d}'
            write(self.w/'evidence'/(label+'_role_check.json'),dict(passed=True))
            write(self.w/'evidence'/(label+'_result.json'),dict(passes=16+i,mesh_cells=100000,delta_s=.003))
        for i in range(10):write(self.r/'ledger'/f'Analyze_D__T1_{i:02d}.json',dict(index=i))
        write(self.r/'ledger/geometry_D__T1.json',dict(case='D__T1'))
        cp.snapshot(self.r,100)
        q=read(cp.HERE/'checkpoints/Analyze_100/SNAPSHOT.json')
        self.assertEqual(q['cumulative_checkpoint_count'],100)
        self.assertEqual(q['requested_total'],101);self.assertEqual(q['geometry_total'],15)
    def test_no_early_checkpoint(self):
        with self.assertRaises(RuntimeError):cp.snapshot(self.r,100)
        self.assertFalse((cp.HERE/'checkpoints').exists())
    def test_prior_batch_threshold_rejected(self):
        with self.assertRaises(RuntimeError):cp.snapshot(self.r,90)
if __name__=='__main__':unittest.main()
