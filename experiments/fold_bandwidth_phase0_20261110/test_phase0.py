"""Offline-only tests. Needs pinned archive requirements plus jsonschema==4.26.0."""
import copy
import json
import unittest
import numpy as np
from jsonschema import Draft202012Validator, ValidationError
import chain
from audit import HERE, REPO, read, sha

P=read(HERE/'freeze/predictions_frozen.json')
SCHEMA=read(HERE/'RUN_RECORD_SCHEMA.json')


def example_record():
    q=P['designs'][0];g=q['geometry_mm'];d=chain.derived(g)
    return dict(schema_version='fig8-fold-run-v1',run_id='EXAMPLE_NOT_STARTED',stage=1,
      experiment='baseline',family=q['family'],data_role='training',parent_run_id=None,topology='folded',
      geometry_mm=g,derived={**{k:d[k] for k in ('a_mm','g_mm','L_parameter_sum_mm','L_polyline_center_mm','rho_parameter_sum','eta')},
                            'tip_microstrip_x_mm':d['arm_tip_to_microstrip_x_mm'],'tip_tip_x_mm':d['arm_tip_to_arm_tip_x_mm']},
      material=dict(er=3.55,tan_delta=.0027,h_mm=.813,t_mm=.035,metal='copper'),
      target=dict(low_GHz=3.92,high_GHz=9.52,S11_max_dB=-20,S21_min_dB=-2,center_GHz=6.72,center_tolerance_GHz=.03,peak_gap_max_dB=.5,n_valleys=3),
      authorization=dict(solver_authorized=False,user_message_reference=None,hook_target_authorized=None),
      budget=dict(Analyze_limit=None,Analyze_requested=0,geometry_attempt=1,geometry_attempt_limit=1),
      frozen_prediction=dict(file='freeze/predictions_frozen.json',sha256=sha(HERE/'freeze/predictions_frozen.json'),model_hashes=P['source_hashes'],
                             frozen_at_UTC='2026-11-10T00:00:00Z',kind='exploratory_prior'),
      solver=dict(AEDT_version=None,cores_requested=14,cores_observed=None,tasks=1,groups=1,serial=True,
                  mesh_cells=None,adaptive_passes=None,final_deltaS=None,elapsed_seconds=None,
                  mesh_evidence=None,process_evidence=None,sweep_settings=dict(f_low_GHz=.01,f_high_GHz=15)),
      curve_evidence=[],results=None,status=dict(lifecycle='planned',solve_completed=None,numerical_pass=None,design_pass=None,visual_ACK=None,failure_kind=None),events=[])


class Phase0Tests(unittest.TestCase):
    def test_01_reproduction(self):
        q=read(HERE/'audit_results/REPRODUCTION.json')
        self.assertTrue(q['passed']);self.assertEqual(q['n_numeric'],398)
        self.assertLess(q['max_abs_difference'],1e-7)

    def test_02_lossless_power(self):
        f=np.linspace(.01,13,2000);s,t=chain.circuit(f,1.05,1.48,6.622,6.588)
        np.testing.assert_allclose(abs(s)**2+abs(t)**2,1,atol=1e-12)

    def test_03_continuous_band(self):
        f=np.linspace(.001,13.439,30001);s,t=chain.circuit(f,1,1.49,6.72,6.72)
        numeric=chain.bands(f,s,t)['BW20']['BW_GHz']
        q=chain.closed_band(1.49,1,6.72,-20)
        self.assertEqual(q['components'],1);self.assertAlmostEqual(q['BW_GHz'],numeric,places=4)

    def test_04_split_band(self):
        f=np.linspace(.001,13.439,30001);s,t=chain.circuit(f,1,1.7,6.72,6.72)
        q=chain.closed_band(1.7,1,6.72,-20)
        self.assertEqual(q['components'],3);self.assertGreater(q['outer_span_GHz'],2*q['BW_GHz'])
        self.assertAlmostEqual(q['BW_GHz'],chain.bands(f,s,t)['BW20']['BW_GHz'],places=4)

    def test_05_p_below_one(self):
        q=chain.closed_band(.9,1,6.72,-20)
        self.assertEqual(q['components'],1);self.assertGreater(q['BW_GHz'],0)
        with self.assertRaises(ValueError):chain.ripple_db(.9)

    def test_06_intersection_off_grid(self):
        f=np.array([0.,1.]);s=10**(np.array([-21.,-19.])/20);t=10**(np.array([-3.,1.])/20)
        q=chain.bands(f,s,t,centre=.4)['BW_joint']
        self.assertAlmostEqual(q['low_GHz'],.25);self.assertAlmostEqual(q['high_GHz'],.5)
        self.assertIsNone(chain.bands(f,s,t,centre=.1)['BW_joint']['BW_GHz'])

    def test_07_length_roundtrip(self):
        g=chain.lengths(1.85,.38,1.4,.55)
        q=chain.forward(g)
        self.assertAlmostEqual(q['fm_GHz'],6.622,places=9);self.assertAlmostEqual(q['fs_GHz'],6.588,places=9)

    def test_08_inverse_ideal_roundtrip(self):
        q=chain.inverse(6,ripple=-21,a=1.4,gap=.55,exploratory=True)
        t=q['ideal_target'];c=chain.closed_band(t['P_eff'],t['zm_eff'],6.72,-20)
        self.assertAlmostEqual(c['BW_GHz'],6,places=9)
        self.assertAlmostEqual(chain.ripple_db(t['P_eff']),-21,places=9)
        self.assertAlmostEqual(q['forward']['P_eff'],t['P_eff'],places=8)
        self.assertFalse(q['solver_authorized'])

    def test_09_unknown_gap_refused(self):
        g=chain.lengths(1.85,.38,1.4,.7)
        with self.assertRaises(ValueError):chain.forward(g)
        self.assertIn('gap_effect_unidentified',chain.forward(g,exploratory=True)['warnings'])
        with self.assertRaises(ValueError):chain.inverse(6,a=0)

    def test_10_invalid_inputs(self):
        for args in [(-1,1,6.72,-20),(1.5,0,6.72,-20),(1.5,1,6.72,1)]:
            with self.assertRaises(ValueError):chain.closed_band(*args)
        for b in (-1,0,14,float('nan')):
            with self.assertRaises(ValueError):chain.inverse(b)

    def test_11_cad_static_convention(self):
        e=read(HERE/'audit_results/GEOMETRY_EVIDENCE.json')
        self.assertEqual(e['sha256'],sha(REPO/e['project']));self.assertEqual(len(e['blocks']),10)
        g=read(REPO/'results/inverse_case/FINAL_RESULTS.json')['geometry']
        b={r['name']:r['parameters'] for r in e['blocks']}
        num=lambda part,k:float(b['StructureBSlot_top_'+part][k].replace('mm',''))
        ws=g['Ws'];d=chain.derived(g)
        self.assertAlmostEqual(num('main','XSize'),g['Ls1'],places=7)
        self.assertAlmostEqual(num('right_connector','YSize'),g['Ls2']-ws,places=7)
        self.assertAlmostEqual(num('right_leg','XSize'),g['Ls3']-ws,places=7)
        ymain=num('main','YPosition')+ws/2
        yleg=num('right_leg','YPosition')+ws/2
        mainspan=g['Ls1']-ws
        arms=2*(g['Ls3']-ws/2)
        self.assertAlmostEqual(mainspan+2*(ymain-yleg)+arms,d['L_polyline_center_mm'],places=7)
        self.assertFalse(e['live_CAD_verified'])

    def test_12_clearance_gate(self):
        g=chain.lengths(1.85,.38,3,2)
        self.assertFalse(chain.geometry_screen(g)['screen_pass'])
        self.assertTrue(chain.geometry_screen(chain.lengths(1.85,.38,1.4,.55))['screen_pass'])

    def test_13_freeze_integrity(self):
        q=read(HERE/'freeze/FREEZE_HASHES.json')
        for k,v in q['source_hashes'].items():self.assertEqual(sha(REPO/k),v)
        for k,v in q['artifacts'].items():self.assertEqual(sha(HERE/'freeze'/k),v)

    def test_14_no_authorized_jobs(self):
        self.assertEqual(P['proposal_counts'],{'1':12,'2':37,'3':20,'4':8})
        self.assertEqual(P['new_Analyze_requests'],0);self.assertFalse(P['solver_authorized'])
        self.assertTrue(all(not r['solver_authorized'] for r in P['designs']))
        self.assertEqual(sum(r['release_status']=='excluded_from_proposed_runlist' for r in P['designs']),5)

    def test_15_fixed_width_is_fixed(self):
        b={r['family']:r['geometry'] for r in read(HERE/'freeze/BASE_FAMILIES.json')['bases']}
        for r in P['designs']:
            if r['stage'] in (2,4):
                self.assertEqual(r['geometry_mm']['Wm'],b[r['family']]['Wm'])
                self.assertEqual(r['geometry_mm']['Ws'],b[r['family']]['Ws'])

    def test_16_reserved_not_training(self):
        for r in P['designs']:
            if r['stage']==4:
                self.assertEqual(r['data_role'],'prospective_reserved')
                self.assertTrue(r['future_prospective_freeze_required'])
                self.assertIn('final_post_stage3_model_and_prospective_prediction_not_available',r['blocking_reasons'])

    def test_17_family_cv(self):
        q=read(HERE/'audit_results/GROUP_CV.json')
        self.assertEqual(len(q['predictions']),78)
        cases=[]
        for f in q['folds']:
            self.assertFalse(set(f['train_families'])&set(f['test_families']))
            self.assertFalse(set(f['train_cases'])&set(f['test_cases']));cases+=f['test_cases']
        self.assertEqual(len(set(cases)),78)
        self.assertLess(q['point_weighted']['MAE'],.13)
        self.assertLess(q['point_weighted']['max_abs'],.32)

    def test_18_schema(self):
        Draft202012Validator.check_schema(SCHEMA)
        Draft202012Validator(SCHEMA).validate(example_record())

    def test_19_schema_rejects_fake_completion(self):
        q=example_record();q['status']['lifecycle']='completed'
        with self.assertRaises(ValidationError):Draft202012Validator(SCHEMA).validate(q)
        q=example_record();q['status']['lifecycle']='running'
        with self.assertRaises(ValidationError):Draft202012Validator(SCHEMA).validate(q)

    def test_20_schema_rejects_prior_as_prospective(self):
        q=example_record();q['data_role']='prospective_test'
        with self.assertRaises(ValidationError):Draft202012Validator(SCHEMA).validate(q)

    def test_21_multistart_is_not_uniqueness_proof(self):
        q=read(HERE/'audit_results/MULTISTART.json')
        self.assertEqual(len(q['cases']),80)
        self.assertTrue(all(r['n_starts']==6 for r in q['cases']))
        self.assertTrue(all(not r['global_uniqueness_proven'] for r in q['cases']))


if __name__=='__main__':unittest.main(verbosity=2)
