"""Offline tests; no application or process calls."""
import ast
from pathlib import Path
import unittest
import headless_worker as w

class HeadlessTests(unittest.TestCase):
    def test_scoped_template_change(self):
        original=(w.REPO/'hfss/INV01_A14.aedt').read_text(encoding='utf-8')
        changed=w.patch_template(original);a=w.model_block(original);b=w.model_block(changed)
        self.assertEqual(original[:a.start()],changed[:b.start()])
        self.assertEqual(original[a.end():],changed[b.end():])
        self.assertIn('MaximumPasses=32',b.group())
        self.assertIn('PercentRefinement=15',b.group())
        with self.assertRaises(ValueError):w.patch_template(changed)

    def test_duplicate_rejected(self):
        original=(w.REPO/'hfss/INV01_A14.aedt').read_text(encoding='utf-8')
        a=w.model_block(original)
        bad=original[:a.start()]+a.group().replace("RangeEnd='15GHz'","RangeEnd='15GHz'\nRangeEnd='15GHz'")+original[a.end():]
        with self.assertRaises(ValueError):w.patch_template(bad)

    def test_numerical_gate(self):
        t='Converged : Yes\n1|100000|0.005|\n'
        self.assertTrue(w.convergence(t)['numerical_pass'])
        for other in [t.replace('100000','99999'),t.replace('100000','112001'),t.replace('0.005','0.00501'),t.replace('Yes','No')]:
            self.assertFalse(w.convergence(other)['numerical_pass'])

    def test_exactly_one_blocking_analyze(self):
        tree=ast.parse(Path(w.__file__).read_text(encoding='utf-8'))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='analyze_setup']
        self.assertEqual(len(calls),1)
        self.assertTrue(next(k.value.value for k in calls[0].keywords if k.arg=='blocking'))
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='AnalyzeAll' for n in ast.walk(tree)))

    def test_budget_no_borrowing(self):
        self.assertEqual(sum(w.LIMITS.values()),185);self.assertEqual(w.LIMITS['1a'],3)

    def test_native_box_reader(self):
        # Parser consumes actual serialized operand records, not generated expectations.
        original=w.REPO/'hfss/INV01_A14.aedt'
        boxes=w.native_boxes(original)
        self.assertEqual(len(boxes),10)
        self.assertEqual(len({b['name'] for b in boxes}),10)

if __name__=='__main__':unittest.main(verbosity=2)
