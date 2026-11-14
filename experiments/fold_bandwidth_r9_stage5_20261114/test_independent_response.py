"""Offline regression tests for the independent raw-CSV replay; no AEDT/network."""
import unittest,json
from pathlib import Path
from independent_response import *
H=Path(__file__).resolve().parent
class Tests(unittest.TestCase):
    def test_scalar_threshold_interpolation(self):
        self.assertEqual(components(np.array([0.,1.,2.]),np.array([-20.,-10.,-20.]),-15),[(0.,.5),(1.5,2.)])
    def test_transmission_sign_and_true_inner_peak(self):
        p=H/'results/S5R9_B3__T1';q=json.loads((p/'review/extraction_R2.json').read_text(encoding='utf-8'));r=metrics(*load_csv(p/'native/full_modes.csv'))
        self.assertTrue(r['three_valley']);self.assertEqual(r['peak_hi_GHz'],8.84)
        self.assertAlmostEqual(r['peak_hi_dB'],max(z['S11_dB'] for z in q['shape']['inner_peaks']),12)
        self.assertIsNone(r['BW20']);self.assertAlmostEqual(r['BW15'],q['bandwidths']['BW15']['BW_GHz'],12)
    def test_all_published_cases(self):
        cs=sorted((H/'results').glob('*/review/extraction_R2.json'));self.assertEqual(len(cs),22)
        for p in cs:
            q=json.loads(p.read_text(encoding='utf-8'));r=metrics(*load_csv(p.parent.parent/'native/full_modes.csv'));lo,hi=sorted(q['shape']['inner_peaks'],key=lambda z:z['GHz'])
            self.assertTrue(r['three_valley']);self.assertAlmostEqual(r['valley_GHz'],q['shape']['central_valley_GHz'],12);self.assertAlmostEqual(r['D_dB'],hi['S11_dB']-lo['S11_dB'],12)
            for b in ('BW15','BW20'):
                v=q['bandwidths'][b]['BW_GHz'];self.assertEqual(v is None,r[b] is None)
                if v is not None:self.assertAlmostEqual(v,r[b],12)
if __name__=='__main__':unittest.main()
