"""Offline-only R10 regression tests. Never import AEDT or dispatch anything."""
import copy, json, math, sys, unittest
from pathlib import Path
import numpy as np
import cad_ir, offline_r10 as off, native_control as nc, tolerance_analysis as ta

class R10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.d=off.generate('clip_cut_faces','height_8h_width_fixed');cls.ps={r['design']:r for r in cls.d['stage6A']}
    def test_01_budget_scope(self):
        b=self.d['budget'];self.assertEqual(b['previous_geometry']+b['new_geometry_cap'],b['cumulative_cap']);self.assertEqual((b['previous_geometry'],b['previous_Analyze']),(173,1633));self.assertFalse(self.d['authorizes_solver'])
    def test_02_fifteen_order(self):self.assertEqual([r['design'] for r in self.d['stage6A']],[f'P{i}' for i in range(1,15)]+['N0'])
    def test_03_all_screens(self):
        for r in self.d['stage6A']+[self.d['W3_T4'],self.d['W4_T1']]:self.assertTrue(r['screen']['can_submit'],r['id'])
    def test_04_fixed_a_g_ws(self):
        for n in ('P1','P2','N0'):
            g=self.ps[n]['geometry_mm'];dd=off.chain.dimensions(g);self.assertAlmostEqual(dd['a_mm'],1.8);self.assertAlmostEqual(dd['g_mm'],.55)
        self.assertAlmostEqual(off.chain.dimensions(self.ps['P1']['geometry_mm'])['L_centerline_mm']-off.chain.dimensions(self.ps['P1']['base_geometry_mm'])['L_centerline_mm'],.04)
    def test_05_only_J_for_first_six(self):
        for i in range(1,15):self.assertEqual(self.ps[f'P{i}']['prediction']['status'],'J局部预测' if i<=6 else '无预测')
    def test_06_j_predicts_peaks(self):
        b=next(s for s in off.read(off.OLD/'final/SELECTED.json') if s['parent']=='S5R9_B1')
        K=np.array(off.read(off.OLD/'final/TOLERANCE.json')['designs']['S5R9_B1']['J_Lm_Ls1_Ws_fixed_a_g'])
        for n,key,sign in [('P1',2,1),('P2',2,-1),('P3',0,1),('P4',0,-1),('P5',1,1),('P6',1,-1)]:
            pred=self.ps[n]['prediction'];y=np.array([b['center'],b['D'],b['L']])+sign*.02*K[key]
            self.assertAlmostEqual(pred['central_valley_GHz'],y[0]);self.assertAlmostEqual(pred['low_peak_dB'],y[2]-y[1]/2);self.assertAlmostEqual(pred['high_peak_dB'],y[2]+y[1]/2)
    def test_07_e0_identity(self):
        ir=cad_ir.build(self.ps['P1']['base_geometry_mm'],port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed')
        for k,v in ir['base_geometry_mm'].items():self.assertAlmostEqual(v,ir['geometry_mm'][k])
        self.assertEqual(ir['profiles'],ir['source_profiles']);self.assertEqual(len(ir['expected_slot_boxes']),10)
    def test_08_etch_is_union_offset(self):
        for n,e in [('P9',.01),('P10',-.01)]:
            ir=self.ps[n]['cad_ir'];b=ir['base_geometry_mm'];g=ir['geometry_mm']
            self.assertAlmostEqual(g['Wm'],b['Wm']-2*e);self.assertAlmostEqual(g['Ws'],b['Ws']+2*e)
            self.assertAlmostEqual(ir['feed_width_mm'],1.82-2*e);self.assertAlmostEqual(ir['stub_shoulder_y_mm'],e)
            self.assertAlmostEqual(ir['stub_open_end_y_mm'],b['Lm']-e);self.assertFalse(ir['canonical_six_dimensions_sufficient'])
            self.assertAlmostEqual(max(p[1] for p in ir['profiles']['bottom']),25.)
            self.assertAlmostEqual(min(p[1] for p in ir['profiles']['top']),-25.)
    def test_09_etch_distance_every_physical_edge(self):
        for n in ('P9','P10'):
            ir=self.ps[n]['cad_ir'];e=ir['etch_e_mm']
            for key,edges in ir['edge_distance_proof'].items():
                for ed in edges:self.assertAlmostEqual(ed['signed_inward_distance_mm'],0. if ed['simulation_cut_face'] else -e if key=='slot' else e)
    def test_10_partition_roundtrip(self):
        for n in ('P9','P10'):
            ir=self.ps[n]['cad_ir']
            for k,rr in ir['rectangles'].items():self.assertEqual(cad_ir.union_profile(rr),ir['profiles'][k])
    def test_11_er_h_signs(self):
        self.assertEqual([self.ps[n]['cad_ir']['er'] for n in ('P11','P12')],[3.5,3.6])
        self.assertEqual([self.ps[n]['cad_ir']['h_mm'] for n in ('P13','P14')],[.775,.851])
        for n in ('P11','P12','P13','P14'):self.assertEqual(self.ps[n]['cad_ir']['tand'],.0027)
    def test_12_h_port_scaling(self):
        for n in ('P13','P14'):
            ir=self.ps[n]['cad_ir'];o=nc.expected_objects(ir)
            self.assertAlmostEqual(ir['port_height_mm'],8*ir['h_mm']);self.assertEqual(ir['port_width_mm'],15.04)
            self.assertAlmostEqual(o['Substrate_3'][2],.035+ir['h_mm']);self.assertAlmostEqual(o['Substrate_18'][5],-.035-ir['h_mm'])
    def test_13_all_sources_hash_match(self):
        for p,h in self.d['source_sha256'].items():self.assertEqual(off.sha(off.REPO/p),h)
    def test_14_numeric_width_ladders(self):
        rows=self.d['training']['rows'];self.assertEqual(len(rows),95);self.assertEqual(len(self.d['training']['stage5_added']),9)
        rr=[r for r in rows if abs(r['Wm']-2.35)<1e-9 and abs(r['g']-.55)<1e-8]
        self.assertEqual(len({r['group'] for r in rr}),1)
        for f in self.d['cross_validation']['folds']:
            self.assertEqual(set(f['case_ids']),{r['case'] for r in rows if r['group']==f['held_out_whole_numeric_Wm_ladder']})
    def test_15_model_rank_and_no_hfss_claim(self):
        self.assertEqual(self.d['parameter_model']['rank'],10);self.assertTrue(math.isfinite(self.d['parameter_model']['condition_number']))
        self.assertFalse(next(r for r in self.d['training']['rows'] if r['case']=='S5R9_W3__T3')['balanced_for_bandwidth'])
    def test_16_W3_history_and_W4_width(self):
        sg=off.tuning.propose_history(off.histories('S5R9_W3'),1.8,'folded');self.assertEqual(sg,self.d['W3_T4']['tuning'])
        self.assertEqual(self.d['W4_T1']['geometry_mm']['Wm'],2.65)
    def test_17_Q_verbatim(self):
        for n in range(11,17):self.assertIn(f'Q{n}',self.d['Q11_Q16_verbatim'])
        p=(off.REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R10.md').read_text(encoding='utf-8');self.assertEqual(self.d['Q11_Q16_verbatim'],p.split('## 4. 审核方登记的预测')[1].split('## 5.')[0])
    def measurement(self,peak=-20.6866488858579):return dict(center_GHz=6.73,low_peak_dB=peak-.1,high_peak_dB=peak,BW20_GHz=6.45,S21_min_dB=-1.1,numerical_review_passed=True,actual_view_ack=True)
    def test_18_missing_is_not_zero(self):self.assertFalse(ta.stage6a(self.measurement(),{})['release_R10_2'])
    def test_19_unreviewed_refused(self):
        b=self.measurement();b['actual_view_ack']=False
        with self.assertRaises(ValueError):ta.stage6a(b,{})
    def test_20_RSS_noise_and_thresholds(self):
        b=self.measurement();m={n:copy.deepcopy(b) for p in ta.PAIRS.values() for n in p};m['N0']=copy.deepcopy(b)
        for n,rise in [('P9',.2),('P11',.1),('P13',.3)]:m[n]['high_peak_dB']+=rise
        a=ta.stage6a(b,m);self.assertAlmostEqual(a['M_dB'],math.sqrt(.14));self.assertAlmostEqual(a['P_req_dB'],-20-math.sqrt(.14)-.256-.1)
        m['N0']['high_peak_dB']+=.101;self.assertFalse(ta.stage6a(b,m)['complete'])
        m.update(P1dense=copy.deepcopy(b),P2dense=copy.deepcopy(b));a=ta.stage6a(b,m);self.assertAlmostEqual(a['M_dB'],math.sqrt(.14)+.101)
    def test_21_linearity(self):
        b=self.measurement();p=copy.deepcopy(b);m=copy.deepcopy(b);p['high_peak_dB']+=.5;m['high_peak_dB']-=.5
        self.assertFalse(ta.linearity(b,p,m)['high_peak_dB']['clearly_nonlinear']);m['high_peak_dB']=b['high_peak_dB']+.3
        self.assertTrue(ta.linearity(b,p,m)['high_peak_dB']['clearly_nonlinear'])
    def test_22_dense_bias_no_free_margin(self):
        n=self.measurement(-21);d=self.measurement(-21.1);c=self.measurement(-20.1)
        r=ta.robust_confirmation(n,d,c,.3);self.assertEqual(r['own_upward_mesh_bias_dB'],0.);self.assertTrue(r['passed'])
        d['high_peak_dB']=-20.7;r=ta.robust_confirmation(n,d,c,.3);self.assertAlmostEqual(r['own_upward_mesh_bias_dB'],.3);self.assertFalse(r['passed'])
    def test_23_native_readback_rejects_mismatch(self):
        ir=self.ps['P9']['cad_ir'];o={n:dict(bounding_box=b,material='copper',solve_inside=False) for n,b in nc.expected_objects(ir).items()}
        for n in ('Substrate_1','Substrate_2'):o[n].update(solve_inside=True,material='Rogers RO4003 (tm)')
        vv={n:[list(p)+[0.] for k in ('ground','slot') for p in ir['profiles'][k]] for n in ('Substrate_7','Substrate_9')}
        ports={}
        for name,y,z in [('1',-25.,.883),('2',25.,-.883)]:ports[name]=dict(NumModes=2,DoDeembed=False,Modes={'Mode1':dict(UseIntLine=True,CharImp='Zpi',IntLine=dict(Start=[0,y,z],End=[0,y,0])),'Mode2':dict(UseIntLine=False,CharImp='Zpi')})
        mats={n:dict(er=3.55,tand=.0027) for n in ('Substrate_1','Substrate_2')}
        self.assertTrue(nc.validate_observed(ir,o,vv,ports,mats)['passed'])
        o['Substrate_4']['bounding_box'][0]-=.001
        with self.assertRaises(RuntimeError):nc.validate_observed(ir,o,vv,ports,mats)

if __name__=='__main__':unittest.main(verbosity=2)
