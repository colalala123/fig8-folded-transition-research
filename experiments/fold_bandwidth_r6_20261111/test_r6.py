"""离线回归：不启动HFSS、不发网络消息。"""
import unittest
import json
import re
from common_r6 import *
from roles_r6 import *

def record(t):
    return dict(command_tail=t,verified_owned_ancestry=True,isolated_scratch=True)

class Roles(unittest.TestCase):
    def test_ports_no_core_requirement(self):
        for t in ['-port_adapt 0','-port_solve -max_processors 2']:
            self.assertEqual(evaluate([record(t),record('-solve_broadband_adapt 1 -max_processors 14 -numParallelGroups 1')],'adaptive_00')['errors'],[])
    def test_sweep_two_cores_valid(self):
        q=evaluate([record('-solve -max_processors 2 -numParallelGroups 1')],'final_sweep')
        self.assertTrue(q['passed']);self.assertEqual(q['lower_core_sweep_count'],1)
    def test_adaptive_requires_fourteen(self):
        self.assertFalse(evaluate([record('-solve_broadband_adapt -max_processors 2 -numParallelGroups 1')],'adaptive_01')['passed'])
    def test_unknowns_not_confused_with_prefixes(self):
        for s in ['-solve_frequency_sweep','-port_solve_fake','-solve -port_adapt','']:
            self.assertEqual(classify(s)['role'],'unknown')
    def test_invalid_sweep_options(self):
        for s in ['-solve','-solve -max_processors 15 -numParallelGroups 1','-solve -max_processors 14 -numParallelGroups 2']:
            self.assertFalse(evaluate([record(s)],'final_sweep')['passed'])
    def test_stage_requirement(self):
        self.assertFalse(evaluate([record('-port_adapt 0')],'adaptive_00')['passed'])
        self.assertFalse(evaluate([record('-solve -max_processors 14 -numParallelGroups 1')],'adaptive_00')['passed'])
        self.assertFalse(evaluate([],'final_sweep')['passed'])
    def test_scratch_and_ancestry(self):
        q=record('-solve_broadband_adapt -max_processors 14 -numParallelGroups 1')
        for field in ('verified_owned_ancestry','isolated_scratch'):
            self.assertFalse(evaluate([{**q,field:False}],'adaptive_01')['passed'])
    def test_path_prefix_removed(self):
        self.assertEqual(tail_of_command(['123','file',"-exedir 'D:/Program Files/Ansys/' -port_adapt 2"]),'-port_adapt 2')
        self.assertEqual(tail_of_command(['-solve']), '')
    def test_budget(self):
        self.assertEqual((LIMITS['1a'],sum(LIMITS.values())),(5,187))
    def test_archive_roles(self):
        from collections import Counter
        count=Counter()
        for p in sorted((REPO/'data/raw').glob('*/state.json')):
            for seg in read(p)['segments']:
                for obs in seg.get('observations',[]):
                    for q in obs:
                        t=tail_of_command(q.get('cmdline'))
                        c=classify(t);count[(c['role'],c['max_processors'])]+=1
                        self.assertNotEqual(c['role'],'unknown')
                        if c['role']=='-solve_broadband_adapt':self.assertEqual(c['max_processors'],14)
        self.assertEqual(count[('-port_adapt',None)],3)
        self.assertEqual(count[('-port_solve',2)],2)
        self.assertEqual(count[('-solve',2)],1)

if __name__=='__main__':unittest.main()
