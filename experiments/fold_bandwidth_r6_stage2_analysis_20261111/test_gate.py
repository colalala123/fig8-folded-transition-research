"""不启动AEDT的合成数据门槛测试。"""
import unittest
from gate import staircase, summarize

def row(case, a, g=.55, parent="S2_E1_N14", good=True, unique=True, source="stage2a_selected"):
    return dict(case=case,actual_a_mm=a,actual_g_mm=g,parent_id=parent,source=source,
                topology="folded",length_calibrated=good,numerical_pass=True,fit_unique_under_R2=unique)

class Tests(unittest.TestCase):
    def test_duplicates_do_not_inflate(self):
        self.assertEqual(staircase([row("a",1.8),row("b",1.8)],"actual_a_mm")["distinct_calibrated_count"],1)
    def test_arm_shortening_leaves_fixed_a_stair(self):
        q=staircase([row("x",1.7,.4,parent="S2_E2_N14")],"actual_g_mm")
        self.assertEqual(q["distinct_calibrated_count"],0)
        self.assertEqual(q["excluded_off_stair_cases"],["x"])
    def test_bad_shape_not_counted(self):
        self.assertEqual(staircase([row("x",1.0,good=False)],"actual_a_mm")["distinct_calibrated_count"],0)
    def test_nonunique_not_silently_fit(self):
        q=staircase([row("x",1.0,unique=False)],"actual_a_mm")
        self.assertEqual(q["distinct_calibrated_count"],1)
        self.assertEqual(q["distinct_fit_eligible_count"],0)
    def test_missing_parent_blocks(self):
        q=summarize([],list(range(15)),list(range(14)))
        self.assertFalse(q["count_conditions_met"])
    def test_no_solver_authorization(self):
        q=summarize([row(str(i),i) for i in range(5)],list(range(15)),list(range(15)))
        self.assertFalse(q["may_launch_2b"])
    def test_cross_points_not_stair_members(self):
        q=staircase([row("x",1.0,parent="S2_E3_00")],"actual_a_mm")
        self.assertEqual(q["distinct_calibrated_count"],0)
    def test_archival_reference_eligible(self):
        q=staircase([row("N14_A18",1.8,parent=None,source="archive_reference")],"actual_g_mm")
        self.assertEqual(q["distinct_calibrated_count"],1)

if __name__=="__main__":
    unittest.main()
