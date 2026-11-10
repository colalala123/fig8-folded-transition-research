import unittest
import headless_worker_v2 as w
import test_headless

# Run the same complete offline suite against v2, plus the native name regression.
test_headless.w=w
HeadlessTests=test_headless.HeadlessTests
class PortNames(unittest.TestCase):
    def test_wave_port_native_name(self):
        for kind in ['Wave Port','WavePort']:
            self.assertTrue(w.is_wave_port(kind))
        for kind in ['Lumped Port','Radiation','',None]:
            self.assertFalse(w.is_wave_port(kind))
if __name__=='__main__':unittest.main(verbosity=2)
