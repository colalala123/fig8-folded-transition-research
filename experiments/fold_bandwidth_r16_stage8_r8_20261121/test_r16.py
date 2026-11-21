"""Offline R8: thresholds, conditional skips, edge replay, budget and immutable design reconstruction."""
import math,unittest,tempfile
from pathlib import Path
import numpy as np
from common_stage2 import read,write
import stage8 as s
from prepare_r10 import make_input
from budget_stage2 import charge
from freeze_r16 import frozen_data
def q(v=6.74,d=.10,maxpk=None):
    top=s.margin()['P_req_dB']-.02 if maxpk is None else maxpk
    return {'shape':{'shape_valid':True,'central_valley_GHz':v,'inner_peaks':[{'GHz':5.,'S11_dB':top-d},{'GHz':8.,'S11_dB':top}]},'bandwidths':{'BW20':{'BW_GHz':6.5}}}
class R8(unittest.TestCase):
    def test_req(self):
        m=s.margin();self.assertAlmostEqual(m['Gamma_req'],.073324,12);self.assertLessEqual(abs(m['P_req_dB']+22.70),.005)
    def test_tol(self):
        self.assertLess(s.margin(tol=.051)['P_req_dB'],s.margin()['P_req_dB'])
        for v in [0,-.01,1,float('nan')]:
            with self.assertRaises(ValueError):s.margin(tol=v)
    def test_edges(self):
        e=s.edges([1,2,3,4,5,6,7],[-19,-21,-23,-19,-18,-24,-17],3)
        self.assertEqual(e['low_GHz'],1.5);self.assertEqual(e['high_GHz'],3.75)
    def test_touch(self):
        e=s.edges([1,2,3,4,5],[-10,-20,-25,-20,-10],3);self.assertEqual((e['low_GHz'],e['high_GHz']),(2,4))
    def test_invalid_trace(self):
        with self.assertRaises(ValueError):s.edges([1,2,2],[-21]*3,2)
        for v in [None,4,1.5]:self.assertIsNone(s.edges([1,2,3],[-10,-21,-19],v))
        self.assertIsNone(s.edges([1,2,3],[-21,-21,-19],2));self.assertIsNone(s.edges([1,2,3],[-10,-10,-10],2))
    def test_replay(self):self.assertEqual(len(s.replay()),3)
    def test_intersection(self):
        items=[dict(low_GHz=i/10,high_GHz=6+i/10) for i in range(5)];b=s.intersect(items);self.assertEqual(b['width_GHz'],5.6);self.assertIsNone(s.intersect(items[:-1]));items[3]=None;self.assertIsNone(s.intersect(items))
    def test_disjoint(self):
        x=[dict(low_GHz=1,high_GHz=3)]*4+[dict(low_GHz=4,high_GHz=5)];self.assertTrue(s.intersect(x)['empty'])
    def test_8a(self):
        m=s.margin();self.assertEqual(s.corners('C2W',m),dict(e=-.01,h=.851,er=3.6));self.assertEqual(s.corners('C3W',m),dict(e=-.01,h=.851,er=3.5))
    def test_c1(self):
        for n in ('C1W5','C1W6'):self.assertEqual(s.corners(n,s.margin()),dict(e=.01,h=.775,er=3.5))
    def test_corner_adjust(self):
        m=dict(low_peak_dB=-22.,high_peak_dB=-20.05,shape_valid=True)
        self.assertFalse(s.corner_test(m,False)['passed']);self.assertEqual(s.corner_test(m,True)['mesh_source'],'own_W4R');self.assertIsNone(s.corner_test(None,False))
    def test_thresholds(self):
        m=s.margin()['P_req_dB'];self.assertTrue(s.check(q(),m,-2)['tuned']);self.assertTrue(s.check(q(v=6.73),m,-1)['tuned'])
        for k in [q(v=6.72),q(v=6.76),q(d=.24),q(maxpk=m+.001)]:self.assertFalse(s.check(k,m,-1)['tuned'])
        for a in [None,-2.01]:self.assertFalse(s.check(q(),m,a)['tuned'])
    def test_t1(self):
        m=s.margin()
        for n,wm in [('W5R',2.8),('W6R',2.95)]:
            d,p=s.t1(n,m);g=d['geometry_mm'];self.assertEqual(g['Wm'],wm);self.assertGreater(g['Ws'],p['reference_geometry_mm']['Ws']);self.assertAlmostEqual(g['Ls2'],2*g['Ws']+.55);self.assertAlmostEqual(g['Ls3'],g['Ws']+1.8);self.assertTrue(d['screen']['can_submit']);self.assertFalse(d['dense_confirmation'])
    def test_frozen_echo(self):
        f=frozen_data();self.assertEqual(f['budget']['effective_max_total_if_all_ten'],210)
        for i in range(31,36):self.assertIn('| Q'+str(i)+' |',f['Q31_Q35_verbatim'])
        d=f['designs']['S8R16_C2W'];self.assertEqual(d['cad_ir']['board_policy'],'fixed_milled_outline')
    def test_gates(self):
        a={'W5R':dict(passed=False,selected_case='closest',measurement=dict(BW20_GHz=6.5))}
        self.assertTrue(s.permission('C1W5',a)[0]);self.assertFalse(s.permission('W6R',a)[0]);a['W5R']['passed']=True;self.assertTrue(s.permission('W6R',a)[0])
        for bw,ok in [(6.54999,False),(6.55,True),(6.6,True)]:
            a['W6R']=dict(passed=True,measurement=dict(BW20_GHz=bw));self.assertEqual(s.permission('C1W6',a)[0],ok)
        a['W6R']['passed']=False;self.assertFalse(s.permission('C1W6',a)[0])
    def test_actual_input(self):
        f=frozen_data()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'decisions').mkdir();(root/'model_freeze').mkdir();(root/'ledger').mkdir();p='S8R16_C2W';c=p+'__T1'
            cfg=dict(designs=f['designs'],case_paths={c:'runs/C2W/001'},case_specs={c:dict(parent_id=p,attempt_ordinal=1,numerical_retry=False)},execution_revision='R16_STAGE8_R8',batch_geometry_limit=10,total_geometry_limit=212,prior_geometry_total=200,prior_Analyze_total=1923)
            write(root/'authorization.json',cfg)
            (root/'offline_copy/pre_solve').mkdir(parents=True)
            from unittest.mock import patch
            with patch('prepare_r10.HERE',root/'offline_copy'):
                self.assertTrue(make_input(root,p,1)['needs_solve'])
                with self.assertRaises(RuntimeError):make_input(root,p,1)
            v=read(root/'runs/C2W/001/input/freeze.json');rec=dict(Analyze_requested=0);charge(root,c,'adaptive_00',rec,v);self.assertEqual(rec['Analyze_requested'],1)
            with self.assertRaises((RuntimeError,FileExistsError)):charge(root,c,'adaptive_00',dict(Analyze_requested=0),v)
            write(root/'PAUSE.json',{'paused':True})
            with self.assertRaises(RuntimeError):charge(root,c,'adaptive_01',rec,v)
    def test_observer(self):self.assertEqual(s.sha(s.HERE/'observer_r13.py'),s.sha(s.H7/'observer_r13.py'))
