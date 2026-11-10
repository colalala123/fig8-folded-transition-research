"""R1's 30 tests adapted to R2, plus new edge/regression tests. Offline only."""
import copy
import unittest
import numpy as np
import chain
from common import HERE, OLD, R1, REPO, read, sha
from geometry import slot_boxes, compare_boxes
from portability import regenerate_registry, compare_typed
from extract_run import power_metrics, extract, grid, basin_audit
from analyze_stage1 import analyze, metrics_from_extraction
from presubmit import presubmit


def synthetic_stage1():
    """Explicit fake observations for algorithm tests, never solver evidence."""
    records={r['id']:r for r in read(R1/'freeze_r1/predictions_frozen.json')['designs']}
    c=read(R1/'STAGE1_CRITERIA.json')
    def row(id,x=0.):
        metrics={k:float(j+2*x+3*x*x) for j,k in enumerate(c['noise_metrics'])}
        return dict(id=id,geometry_mm=copy.deepcopy(records[id]['geometry_mm']),metrics=metrics,
                    mesh_cells=105000,MaxDeltaS=.005,sweep_low_GHz=.01,sweep_high_GHz=15.)
    return dict(label='SYNTHETIC NOT HFSS',archive=[row(i) for i in c['baseline_ids']],
                baseline=[row(i) for i in c['baseline_ids']],
                perturbations=[row(f'S1_WS_{j:02d}',x) for j,x in enumerate(c['width_delta_mm'])])


class R2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.freeze=read(R1/'freeze_r1/predictions_frozen.json')
        cls.records=cls.freeze['designs'];cls.ids={r['id']:r for r in cls.records}

    def test_01_length_convention_80(self):
        errors=[]
        for r in read(REPO/'model/DATASET.json')['rows']:
            g=r['geometry']
            errors.append(abs(chain.forward(g,length_form='centerline')['fs_GHz']-
                              chain.forward(g,length_form='parameter_sum')['fs_GHz']))
        self.assertLess(max(errors),1e-9)

    def test_02_center_coefficient_shift(self):
        dm,ds=chain.corrections(1.8,.4,1.8)
        self.assertAlmostEqual(ds,1.9644-.4017*1.8-1.2118*.4-.5389*1.8,places=14)
        with self.assertRaises(ValueError):chain.corrections(1.8,.4,1.8,'wrong')

    def test_03_registry_counts(self):
        self.assertEqual(len(self.records),79)
        self.assertEqual(self.freeze['counts']['original_folded_pass'],70)
        self.assertEqual(self.freeze['counts']['by_batch'],{'1a':3,'1b':9,'2a':15,'2b':22,'3':22,'4':8,'5':0})
        self.assertTrue(all(r['screen']['screen_pass'] for r in self.records))

    def test_04_rho_restored_not_gate(self):
        prior=read(OLD/'freeze/EXCLUSIONS.json')
        self.assertEqual(len(prior),5)
        for r in prior:
            q=self.ids[r['id']]
            self.assertGreaterEqual(q['screen']['rho'],.5)
            self.assertTrue(q['screen']['screen_pass'])
            self.assertFalse(q['screen']['rho_is_gate'])

    def test_05_clearance_feed_and_disconnection(self):
        g=dict(Wm=1.7,Ws=.4,Lm=6.6,Ls1=10.,Ls2=1.35,Ls3=4.1)
        q=chain.geometry_screen(g)
        self.assertEqual(q['central_line_width_mm'],1.82)
        self.assertFalse(q['screen_pass'])
        self.assertIn('tip_tip_clearance_below_line_width_plus_1.626mm',q['reasons'])
        g['Ls1']=21
        self.assertIn('slot_board_margin_below_5mm',chain.geometry_screen(g)['reasons'])

    def test_06_straight_initials(self):
        for family,expected in [('N04',16.673),('N14',16.624),('N08',16.485)]:
            r=self.ids['S2_E0_'+family]
            self.assertEqual(r['geometry_mm']['Ls1'],expected)
            self.assertEqual(len(slot_boxes(r['geometry_mm'],'straight_control')),2)
            self.assertGreater(r['straight_prior']['pure_half_wave_mm'],expected)

    def test_07_straight_equal_ripple_initial(self):
        for family in ('N04','N14'):
            r=self.ids['S3_EQ_'+family+'_00'];g=r['geometry_mm']
            self.assertAlmostEqual(g['Ws']*1000,round(g['Ws']*1000),places=10)
            self.assertLess(abs(r['prediction']['equal_frequency_inner_peak_dB']+21),.03)
            self.assertEqual(g,self.ids[r['id']+'_LOSSLESS']['geometry_mm'])

    def test_08_boundary_controls(self):
        for id in ('S3_BOUNDARY_N14_STRAIGHT','S3_BOUNDARY_N14_A18'):
            r=self.ids[id]
            self.assertEqual(r['boundary_half_x_mm'],20)
            self.assertEqual(r['geometry_mm'],self.ids[r['parent']]['geometry_mm'])
            self.assertEqual(r['material_role'],self.ids[r['parent']]['material_role'])
            self.assertEqual(r['max_Analyze_requests_proposed'],1)

    def test_09_roles_and_no_solver_permission(self):
        self.assertFalse(self.freeze['solver_authorized'])
        self.assertFalse(self.freeze['budgets_authorized'])
        self.assertEqual(self.freeze['proposed_total_Analyze_cap'],185)
        for r in self.records:
            self.assertFalse(r['solver_authorized'])
            if r['batch']=='2b' or r['stage']==4:
                self.assertEqual(r['first_attempt_role'],'prospective_test')
                self.assertTrue(r['future_prospective_freeze_required'])
            if r['topology']=='straight_control':self.assertTrue(r['future_run_directory'].startswith('uniform_control/'))

    def test_10_frozen_hashes(self):
        q=read(R1/'freeze_r1/FREEZE_HASHES.json')
        for name,digest in q['source_hashes'].items():self.assertEqual(sha(REPO/name),digest,name)
        for name,digest in q['artifacts'].items():self.assertEqual(sha(R1/'freeze_r1'/name),digest,name)

    def test_11_registry_regeneration(self):
        self.assertEqual(compare_typed(regenerate_registry(),self.records),[])

    def test_12_INV_boxes_all_60_coordinates(self):
        g=dict(Wm=1.91362018,Ws=.345967019,Lm=6.58449979,Ls1=12.6199947,
               Ls2=1.2419340379884205,Ls3=1.74596701899421)
        native=[dict(name=b['name'],parameters_mm={k:float(v.removesuffix('mm')) for k,v in b['parameters'].items()})
                for b in read(OLD/'audit_results/GEOMETRY_EVIDENCE.json')['blocks']]
        self.assertEqual(len(native),10)
        self.assertTrue(compare_boxes(slot_boxes(g),native)['passed'])
        bad=copy.deepcopy(native);bad[0]['parameters_mm']['XPosition']+=.001
        self.assertFalse(compare_boxes(slot_boxes(g),bad)['passed'])
        self.assertFalse(compare_boxes(slot_boxes(g),native+[native[0]])['passed'])
        self.assertFalse(compare_boxes(slot_boxes(g),native[:-1])['passed'])

    def test_13_all_box_tables_match(self):
        boxes=read(R1/'freeze_r1/SLOT_BOXES.json')
        self.assertEqual(len(boxes),79)
        for r in boxes:
            self.assertEqual(slot_boxes(r['geometry_mm'],r['topology']),r['boxes'])
            self.assertTrue(all(min(b['parameters_mm'][k] for k in ('XSize','YSize','ZSize'))>0 for b in r['boxes']))

    def test_14_straight_not_degenerate_fold(self):
        g=chain.straight(1.8,.4)
        with self.assertRaises(ValueError):slot_boxes(g,'folded')
        self.assertTrue(chain.geometry_screen(g,'straight_control')['screen_pass'])
        g['Ls2']=.1
        with self.assertRaises(ValueError):slot_boxes(g,'straight_control')

    def test_15_split_BW20_null_not_envelope(self):
        f=np.linspace(.1,13.3,4001);s,t=chain.circuit(f,1,1.7,6.72,6.72)
        q=chain.bands(f,s,t)['BW20']
        self.assertEqual(q['components'],3);self.assertIsNone(q['BW_GHz'])
        self.assertFalse(q['fit_eligible']);self.assertGreater(q['outer_span_GHz'],q['main_component_BW_GHz'])

    def test_16_connected_BW20_valid(self):
        f=np.linspace(.1,13.3,4001);s,t=chain.circuit(f,1,1.49,6.72,6.72)
        q=chain.bands(f,s,t)['BW20']
        self.assertEqual(q['components'],1);self.assertTrue(q['hard_constraint_valid'])
        self.assertIsNotNone(q['BW_GHz'])

    def test_17_full_modal_power_all_channels(self):
        f=np.linspace(2,12,20);S=np.zeros((20,4,4),complex)
        S[:,:,0]=np.sqrt([.01,.04,.8,.05]);z=S[:,[0,2],0];p=np.ones((20,4),bool)
        q=power_metrics(f,z,S,p,'power_waves')
        np.testing.assert_allclose(q['all_mode_remaining'],.1,atol=1e-14)
        np.testing.assert_allclose(q['fundamental_unaccounted'],.19,atol=1e-14)

    def test_18_modal_propagation_and_unknown_normalization(self):
        f=np.linspace(2,12,20);S=np.zeros((20,4,4),complex);S[:,:,0]=np.sqrt([.01,.04,.8,.05])
        z=S[:,[0,2],0];p=np.ones((20,4),bool);p[:,1]=False;p[0,0]=False
        q=power_metrics(f,z,S,p,'power_waves')
        self.assertIsNone(q['all_mode_remaining'][0]);self.assertAlmostEqual(q['all_mode_remaining'][1],.14)
        self.assertFalse(q['mode2_propagating']['port1'][1])
        with self.assertRaises(ValueError):power_metrics(f,z,S,p,'unknown')
        with self.assertRaises(ValueError):power_metrics(f,z,S,p.astype(int),'power_waves')
        with self.assertRaises(ValueError):power_metrics(f,z,S[:,:2,:2],p,'power_waves')

    def test_19_missing_modes_never_zero_filled(self):
        f=np.arange(2.,12.1,.1);z=np.ones((len(f),2))*.2
        q=power_metrics(f,z)
        self.assertIsNone(q['all_mode_remaining']);self.assertIsNone(q['mode2_propagating'])

    def test_20_power_not_clipped(self):
        f=np.arange(2.,12.1,.1);S=np.ones((len(f),4,4),complex)
        q=power_metrics(f,S[:,[0,2],0],S,np.ones((len(f),4),bool),'power_waves')
        self.assertEqual(q['all_mode_remaining'][0],-3.)

    def test_21_archive_replay(self):
        q=read(HERE/'replay_r2/REPLAY_CHECK.json')
        self.assertTrue(q['legacy_compatible_pass']);self.assertEqual(q['numeric_comparisons'],3120)
        self.assertLess(q['max_abs_legacy_difference'],1e-8)
        self.assertLess(q['max_selected_multistart_parameter_difference'],1e-6)
        self.assertFalse(q['archive_full_mode_available'])

    def test_22_multistart_selected_minimum(self):
        for q in read(HERE/'replay_r2/EXTRACTED_80.json'):
            c=q['circuit'];cost=c['starts'][c['best_start']]['cost']
            self.assertEqual(cost,min(s['cost'] for s in c['starts'] if s['success']))
            best=c['starts'][c['best_start']]
            others=[s for s in c['starts'] if s['success'] and max(abs(np.asarray(s['parameters'])-np.asarray(best['parameters']))/abs(np.asarray(best['parameters'])))>.01]
            self.assertEqual(c['extraction_nonunique'],any(s['cost']<=1.05*best['cost'] for s in others))
            self.assertEqual(len(c['starts']),6)
            self.assertEqual(sum(s['start_kind']=='independent' for s in c['starts']),5)
            self.assertEqual(sum(s['start_kind']=='refinement' for s in c['starts']),1)
            self.assertTrue(all(s['basin_id'] is not None for s in c['starts'] if s['success']))

    def test_23_extract_synthetic_whole_run(self):
        f=np.linspace(.01,15,1500);s,t=chain.circuit(f,1,1.49,6.622,6.588)
        S=np.zeros((len(f),4,4),complex);S[:,0,0]=s;S[:,2,0]=t
        q=extract(f,np.c_[s,t],dict(case='SYNTHETIC',geometry=self.ids['S1_BASE_N14']['geometry_mm']),
                  S,np.ones((len(f),4),bool),'power_waves')
        self.assertLess(q['circuit']['rms_linear'],1e-7)
        np.testing.assert_allclose(q['power']['all_mode_remaining'],0,atol=1e-12)

    def test_24_grid_and_input_rejection(self):
        with self.assertRaises(ValueError):grid([3,2],np.zeros((2,2)))
        with self.assertRaises(ValueError):grid(np.linspace(3,10,20),np.zeros((20,2)))
        with self.assertRaises(ValueError):grid(np.linspace(2,12,20),np.zeros((19,2)))

    def test_25_stage1_quadratic_and_linear_separate(self):
        q=analyze(synthetic_stage1())
        self.assertTrue(q['offline_ready_for_review']);self.assertFalse(q['solver_authorized'])
        noise=q['perturbation_noise']['BW15_GHz']
        self.assertGreater(noise['linear_residual_sd'],0)
        self.assertLess(noise['quadratic_residual_sd'],1e-12)
        self.assertAlmostEqual(noise['small_pair_slope_corrected_difference'],0,places=12)
        self.assertEqual(q['zero_repeat_minus_baseline']['BW15_GHz'],0)

    def test_26_stage1_each_peak_gate_not_mean(self):
        d=synthetic_stage1();d['baseline'][0]['metrics']['inner_peak_low_dB']+=.11
        d['baseline'][0]['metrics']['inner_peak_high_dB']-=.11
        self.assertFalse(analyze(d)['baseline_comparability_passed'])

    def test_27_stage1_all_required_gates(self):
        for k,v in [('central_valley_GHz',.0101),('BW15_GHz',.0101)]:
            d=synthetic_stage1();d['baseline'][0]['metrics'][k]+=v
            self.assertFalse(analyze(d)['offline_ready_for_review'])
        for k,v in [('mesh_cells',112001),('MaxDeltaS',.05),('sweep_high_GHz',12)]:
            d=synthetic_stage1();d['baseline'][0][k]=v
            self.assertFalse(analyze(d)['numerical_checks_passed'])

    def test_28_stage1_missing_duplicate_and_wrong_geometry(self):
        d=synthetic_stage1();d['perturbations'][0]=d['perturbations'][1]
        with self.assertRaises(ValueError):analyze(d)
        d=synthetic_stage1();d['perturbations'][0]['geometry_mm']['Ws']+=.001
        with self.assertRaises(ValueError):analyze(d)

    def test_29_stage1_null_noise_no_imputation(self):
        d=synthetic_stage1();d['perturbations'][0]['metrics']['BW20_GHz']=None
        q=analyze(d);self.assertFalse(q['perturbation_noise']['BW20_GHz']['available'])
        self.assertTrue(q['offline_ready_for_review'])
        d['perturbations'][0]['metrics']['BW15_GHz']=None
        self.assertFalse(analyze(d)['offline_ready_for_review'])

    def test_30_symmetric_slope_noise_difference(self):
        d=synthetic_stage1();d['perturbations'][5]['metrics']['BW15_GHz']+=.003
        q=analyze(d)['perturbation_noise']['BW15_GHz']
        self.assertGreater(abs(q['small_pair_slope_corrected_difference']),.0029)
        self.assertAlmostEqual(q['small_pair_slope_corrected_difference'],q['small_pair_quadratic_slope_corrected_difference'],places=12)

    def test_31_reviewer_27_53_restored_7(self):
        r=read(HERE/'replay_r2/REPLAY_CHECK.json')
        self.assertEqual(r['R2_BW20_valid_count'],27);self.assertEqual(r['R2_BW20_null_count'],53)
        self.assertEqual(r['restored_cases'],['N04_A18','N10_A18','N10_A18_M','N10_A18_S','N11_A18_S','N17_A18_C1','N21_A18'])
        self.assertTrue(read(HERE/'replay_r2/REVIEWER_COMPARISON.json')['all_80_passed'])
        self.assertEqual(r['nonunique_flags'],0)
        self.assertGreater(r['minimum_other_basin_cost_ratio'],2.96)

    def test_32_secondary_band_does_not_invalidate_any_main_band(self):
        f=np.array([3.,4.,5.,6.,7.,8.,9.,10.,11.,12.,13.])
        db=np.array([-10,-10,-25,-25,-25,-25,-10,-10,-25,-25,-10.])
        s=10**(db/20);t=np.ones(len(f))
        shape=dict(central_valley_GHz=6.,inner_peaks=[dict(GHz=5.5),dict(GHz=7.5)])
        b=chain.bands(f,s,t,shape=shape)
        for key in ('BW15','BW20','BW_joint'):
            self.assertTrue(b[key]['main_band_valid'])
            self.assertEqual(b[key]['secondary_component_count'],1)
            self.assertFalse(b[key]['edge_censored'])
        self.assertLess(b['BW20']['BW_GHz'],b['BW20']['outer_span_GHz'])

    def test_33_main_is_central_valley_not_fixed_reference(self):
        f=np.array([3.,4.,5.,6.,7.,8.,9.,10.,11.,12.,13.])
        s=10**(np.array([-10,-10,-25,-25,-10,-10,-25,-25,-25,-10,-10])/20)
        shape=dict(central_valley_GHz=10.,inner_peaks=[dict(GHz=9.),dict(GHz=11.)])
        q=chain.bands(f,s,np.ones(len(f)),shape=shape)['BW20']
        self.assertTrue(q['main_band_valid']);self.assertGreater(q['low_GHz'],8.)

    def test_34_missing_peaks_null_and_sweep_censor(self):
        f=np.linspace(3,12,10);s=np.full(10,.01);t=np.ones(10)
        for shape in [dict(central_valley_GHz=6.72),dict(inner_peaks=[dict(GHz=5),dict(GHz=8)])]:
            self.assertIsNone(chain.bands(f,s,t,shape=shape)['BW20']['BW_GHz'])
        shape=dict(central_valley_GHz=6.72,inner_peaks=[dict(GHz=5),dict(GHz=8)])
        q=chain.bands(f,s,t,shape=shape)['BW20']
        self.assertTrue(q['main_band_valid']);self.assertTrue(q['edge_censored']);self.assertFalse(q['fit_eligible'])

    def test_35_joint_requires_transmission_through_peaks(self):
        f=np.arange(3.,13.);s=np.full(10,.01);t=np.ones(10);t[2]=.1
        shape=dict(central_valley_GHz=7.,inner_peaks=[dict(GHz=5),dict(GHz=9)])
        b=chain.bands(f,s,t,shape=shape)
        self.assertTrue(b['BW20']['main_band_valid']);self.assertFalse(b['BW_joint']['main_band_valid'])

    def test_36_distinct_basin_cost_threshold(self):
        def start(p,c):return dict(success=True,parameters=p,cost=c)
        cases=[start([1,1,6,6],1.),start([1+1e-8,1,6,6],1.000000001),start([1.02,1,6,6],1.04)]
        q=basin_audit(cases);self.assertTrue(q['extraction_nonunique'])
        self.assertEqual(cases[0]['basin_id'],cases[1]['basin_id'])
        self.assertNotEqual(cases[0]['basin_id'],cases[2]['basin_id'])
        cases[2]['cost']=1.06
        self.assertFalse(basin_audit(cases)['extraction_nonunique'])

    def test_37_basin_zero_cost_and_failed_start(self):
        cases=[dict(success=True,parameters=[1,1,6,6],cost=0.),dict(success=True,parameters=[2,1,6,6],cost=1.),dict(success=False,parameters=[3,1,6,6],cost=0.)]
        q=basin_audit(cases);self.assertFalse(q['extraction_nonunique'])
        self.assertTrue(q['minimum_other_basin_ratio_infinite']);self.assertIsNone(cases[2]['basin_id'])
        cases[1]['cost']=0.
        self.assertTrue(basin_audit(cases)['extraction_nonunique'])

    def test_38_gate_initial_passthrough(self):
        for r in self.records:
            g=r['geometry_mm'];a=g['Ls3']-g['Ws'] if r['topology']=='folded' else 0.
            q=presubmit(g,a,False,r['topology'],r['boundary_half_x_mm'])
            self.assertTrue(q['can_submit']);self.assertEqual(q['geometry_mm'],g)
            self.assertFalse(q['adjusted']);self.assertFalse(q['solver_authorized'])

    def test_39_tuning_reduces_to_maximal_grid_arm(self):
        g=copy.deepcopy(self.ids['S3_EQ_N04_04']['geometry_mm']);g['Ls1']-=.02
        q=presubmit(g,3.,True)
        self.assertTrue(q['can_submit']);self.assertTrue(q['adjusted'])
        self.assertEqual(q['nominal_a_mm'],3.);self.assertLess(q['actual_a_mm'],3.)
        self.assertFalse(q['next_grid_allowed']);self.assertEqual(q['additional_attempts'],0)
        for k in g:
            if k!='Ls3':self.assertEqual(q['geometry_mm'][k],g[k])
        self.assertAlmostEqual(q['actual_a_mm']*1000,round(q['actual_a_mm']*1000))

    def test_40_recheck_each_new_geometry_and_tuning_required(self):
        g=copy.deepcopy(self.ids['S3_EQ_N04_04']['geometry_mm'])
        self.assertTrue(presubmit(g,3.)['can_submit']);g['Ls1']-=.02
        self.assertFalse(presubmit(g,3.)['can_submit'])
        q=presubmit(g,3.,True);new=copy.deepcopy(q['geometry_mm']);new['Ls1']-=.01
        self.assertLess(presubmit(new,3.,True)['actual_a_mm'],q['actual_a_mm'])

    def test_41_gate_cannot_fix_board_or_nonpositive_gap(self):
        g=copy.deepcopy(self.ids['S3_EQ_N04_04']['geometry_mm']);g['Ls1']=21.
        self.assertFalse(presubmit(g,3.,True)['can_submit'])
        g['Ls1']=10.;g['Ls2']=2*g['Ws']
        self.assertFalse(presubmit(g,3.,True)['can_submit'])
        g['Ls2']=2*g['Ws']+.55;g['Ls1']=1.
        self.assertFalse(presubmit(g,3.,True)['can_submit'])

    def test_42_typed_portability_tolerance(self):
        ref=dict(s='a',b=True,i=1,f=1.,nearzero=0.,n=None,l=[2.])
        q=copy.deepcopy(ref);q['f']+=3.8e-15;q['nearzero']=5e-13
        self.assertEqual(compare_typed(q,ref),[])
        for key,val in [('s','b'),('b',1),('i',1.),('f',1.00001),('nearzero',2e-12),('n',False),('l',[2.,3.])]:
            q=copy.deepcopy(ref);q[key]=val
            self.assertTrue(compare_typed(q,ref))
        q=copy.deepcopy(ref);q['f']=float('nan');self.assertTrue(compare_typed(q,ref))

    def test_43_stage1_conversion_requires_R2(self):
        q=read(HERE/'replay_r2/EXTRACTED_80.json')[0]
        m=metrics_from_extraction(q)
        self.assertEqual(m['BW20_GHz'],q['bandwidths']['BW20']['BW_GHz'])
        q['schema_version']='R1-extracted-run-v1'
        with self.assertRaises(ValueError):metrics_from_extraction(q)


if __name__=='__main__':unittest.main(verbosity=2)
