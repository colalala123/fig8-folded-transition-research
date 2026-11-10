import tempfile
import unittest
from scratch_guard import configure_scratch,restore_scratch

class FakeApp:
    temp_directory='previous'
    def set_temporary_directory(self,p):self.temp_directory=p;return True
class ScratchTests(unittest.TestCase):
    def test_set_readback_restore(self):
        with tempfile.TemporaryDirectory() as d:
            app=FakeApp();q=configure_scratch(app,d);self.assertTrue(q['verified'])
            self.assertTrue(restore_scratch(app,q));self.assertEqual(app.temp_directory,'previous')
    def test_bad_readback_rejected(self):
        class Bad(FakeApp):
            def set_temporary_directory(self,p):return True
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'readback'):configure_scratch(Bad(),d)
    def test_other_preference_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            app=FakeApp();q=configure_scratch(app,d);app.temp_directory='someone_else'
            with self.assertRaisesRegex(RuntimeError,'externally'):restore_scratch(app,q)
            self.assertEqual(app.temp_directory,'someone_else')
if __name__=='__main__':unittest.main(verbosity=2)
