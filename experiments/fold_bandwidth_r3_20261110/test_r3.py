import copy
import unittest
from pathlib import Path
from prepare_stage3 import build,HERE,REPO,read
from stage3_metrics import evaluate,slope_for_family


def sample(mean=-20.3,bw=6.,gap=0.,center=6.72):
    return dict(schema_version='R2-extracted-run-v1',shape=dict(shape_valid=True,central_valley_GHz=center,
        inner_peaks=[dict(S11_dB=mean-gap/2),dict(S11_dB=mean+gap/2)]),bandwidths=dict(BW20=dict(BW_GHz=bw,edge_censored=False)))


class R3Tests(unittest.TestCase):
    def test_registry(self):
        rows,checks,old=build();self.assertEqual(len(rows),20);self.assertEqual(len(old),20)
        self.assertTrue(all(c['passed'] for c in checks));self.assertTrue(all(r['screen']['can_submit'] for r in rows))
        self.assertEqual(sorted({r['actual_a_mm'] for r in rows}),[0.,.6,1.4,2.2,2.9])
        self.assertEqual(sum(r['max_Analyze'] for r in rows)+2,42)
    def test_box_count(self):
        rows,_,_=build();self.assertEqual(sum(len(r['boxes']) for r in rows),168)
    def test_thresholds(self):
        self.assertTrue(evaluate(sample(-20.3,gap=.5),'N04')['tuned'])
        self.assertTrue(evaluate(sample(-20.6),'N04')['tuned'])
        for q in [sample(-20.61),sample(-19.99),sample(-20.1,gap=.3),sample(center=6.76),sample(-20.3,gap=.51)]:
            self.assertFalse(evaluate(q,'N04')['tuned'])
    def test_prior_and_sign(self):
        q=evaluate(sample(-20.5),'N04');self.assertAlmostEqual(q['normalized_BW20_at_minus20p3_GHz'],6.03)
        self.assertEqual(q['slope']['source'],'prior_150MHz_per_dB')
    def test_family_fit(self):
        records=[dict(family='N04',design_id=str(i),extraction=sample(m,6+.2*(m+20.3))) for i,m in enumerate([-20.5,-20.3,-20.1])]
        records.append(dict(family='N14',design_id='different',extraction=sample(-20.2,8)))
        q=evaluate(sample(-20.5,5.96),'N04',records)
        self.assertAlmostEqual(q['slope']['slope_GHz_per_dB'],.2);self.assertAlmostEqual(q['normalized_BW20_at_minus20p3_GHz'],6)
    def test_missing_band_and_censor(self):
        for q in [sample(bw=None),sample()]:
            if q['bandwidths']['BW20']['BW_GHz'] is not None:q['bandwidths']['BW20']['edge_censored']=True
            self.assertIsNone(evaluate(q,'N04')['normalized_BW20_at_minus20p3_GHz'])
    def test_rank_and_duplicate(self):
        rows=[dict(family='N04',design_id=str(i),extraction=sample()) for i in range(3)]
        self.assertEqual(slope_for_family('N04',rows)['source'],'prior_150MHz_per_dB')
        with self.assertRaises(ValueError):slope_for_family('N04',rows+[rows[0]])
    def test_schema_and_shape(self):
        q=sample();q['schema_version']='old'
        with self.assertRaises(ValueError):evaluate(q,'N04')
        q=sample();q['shape']['inner_peaks']=[];self.assertFalse(evaluate(q,'N04')['tuned'])
    def test_reviewer_rerun(self):
        q=read(HERE/'review_rerun/COMPARISON.json');self.assertTrue(q['passed'])


if __name__=='__main__':unittest.main(verbosity=2)
