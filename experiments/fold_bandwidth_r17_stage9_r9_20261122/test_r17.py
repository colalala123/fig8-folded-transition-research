import copy,unittest,tempfile
from pathlib import Path
import numpy as np
import stage9 as s
from fingerprint import settings,identity,lookup,old_index
from replay_r9 import run
from prepare_r10 import eligibility
from unittest.mock import patch
class R9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=run()
    def test_R9_1(self):self.assertTrue(self.r['replays']['R9-1']['passed'])
    def test_R9_2(self):self.assertTrue(self.r['replays']['R9-2']['passed'])
    def test_R9_3(self):self.assertTrue(self.r['replays']['R9-3']['passed'])
    def test_R9_4(self):self.assertTrue(self.r['replays']['R9-4']['passed'])
    def test_R9_5(self):self.assertTrue(self.r['replays']['R9-5']['passed'])
    def test_distinct_settings(self):
        g=s.T4;b=s.build(g,'W5R');fp=identity(b)
        self.assertNotEqual(fp,identity(s.build(g,'Ddense','CONTROL')))
        self.assertNotEqual(fp,identity(s.build(g,'DC2','CONTROL',-.01,3.6,.851)))
        self.assertNotEqual(fp,identity(s.build(g,'DC3','CONTROL',-.01,3.50,.851)))
        self.assertTrue(lookup(b,old_index())['allowed'])
    def test_window_not_expanded_by_error(self):
        req=s.REQ
        q=copy.deepcopy(s.seed()[0]['q']);sh=q['shape']
        for p in sh['inner_peaks']:p['S11_dB']=req-.1
        for v,pas in [(6.72,False),(6.73,True),(6.76,True),(6.77,False)]:
            sh['central_valley_GHz']=v;self.assertEqual(s.check(q,req,-2)['tuned'],pas)
        sh['central_valley_GHz']=6.74;self.assertFalse(s.check(q,req,-2.0001)['tuned']);sh['inner_peaks'][0]['S11_dB']=req+.001;self.assertFalse(s.check(q,req,-1)['tuned'])
    def test_selection_replay(self):
        x=s.selection({'W4R':(s.W4,s.W4RUNS['C1W'],s.W4)})
        self.assertAlmostEqual(x['candidates']['W4R']['width_GHz'],6.018106797,8)
    def test_conditional(self):
        D={n:dict(complete=True,passed=True,measurement={'BW20_GHz':6.5},corner_test={'passed':True}) for n in s.ORD};D['W6R']['measurement']={'BW20_GHz':6.549}
        with patch('prepare_r10.dec',side_effect=lambda root,n:D[n]):
            self.assertFalse(eligibility(None,'W7R',{})[0]);D['W6R']['measurement']['BW20_GHz']=6.55;self.assertTrue(eligibility(None,'W7R',{})[0]);D['C1W6']['corner_test']['passed']=False;self.assertFalse(eligibility(None,'W7R',{})[0]);D['W5R']['passed']=False;self.assertFalse(eligibility(None,'DC2',{})[0])
    def test_caps(self):
        self.assertEqual(sum(map(len,s.ORD.values())),15);self.assertEqual(s.ORD['W5R'],[4,5,6]);self.assertEqual(s.sha(s.HERE/'observer_r13.py'),s.sha(s.H8/'observer_r13.py'))
        from common_stage2 import dense_next_stage
        self.assertEqual(dense_next_stage([(27,220000,.004)])[0],'final_sweep')
        with self.assertRaises(RuntimeError):dense_next_stage([(28,300001,.001)])
