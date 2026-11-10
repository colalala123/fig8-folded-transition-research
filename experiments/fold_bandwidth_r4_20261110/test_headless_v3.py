import tempfile
from pathlib import Path
import unittest
import headless_worker_v3 as w
import test_headless
test_headless.w=w
HeadlessTests=test_headless.HeadlessTests
class StopGuard(unittest.TestCase):
    def test_old_numeric_stop_blocks_v3_before_config_or_aedt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'STOP_R4_HEADLESS_V2.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'R4 numerical stop'):
                w.execute(root,'S1_BASE_N14')
if __name__=='__main__':unittest.main(verbosity=2)
