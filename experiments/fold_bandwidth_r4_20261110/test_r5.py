"""Offline tests: no AEDT connection or launch."""
import unittest
from pathlib import Path
import numpy as np
from staged_mesh_r5 import history,next_stage,check_transition,NumericalStop,LIMITS
from headless_worker_r5 import REPO,HERE,read,saved_setting
from review_r5 import compare_complex

class R5(unittest.TestCase):
    def test_budget(self):
        self.assertEqual((LIMITS['1a'],sum(LIMITS.values())),(4,186))
    def test_refinement_cutoffs(self):
        self.assertEqual(next_stage([]),('adaptive_00',16,30))
        for n,pct in [(44999,30),(45000,10),(79999,10),(80000,5),(99999,5)]:
            self.assertEqual(next_stage([(16,n,.006)])[1:],(17,pct))
    def test_final_boundaries(self):
        for n in (100000,112000):
            self.assertEqual(next_stage([(28,n,.005)])[0],'final_sweep')
        self.assertEqual(next_stage([(25,106000,.0051)])[2],5)
        for row in [(16,112001,.002),(28,99999,.004),(25,106001,.0051)]:
            with self.assertRaises(NumericalStop):next_stage([row])
    def test_history_rejects_changed_and_extra_passes(self):
        before=history('1|100| N/A|\n2|200|.1|')
        after=before+[(3,300,.002)]
        check_transition(before,after,3)
        check_transition(after,after,3,sweep=True)
        for invalid in [[before[0],(2,201,.1),after[2]],after+[(4,350,.001)],before+[(3,200,.002)]]:
            with self.assertRaises(NumericalStop):check_transition(before,invalid,3)
        with self.assertRaises(NumericalStop):check_transition(before,after,3,sweep=True)
    def test_archive_n04_mesh_replay(self):
        st=read(REPO/'data/raw/N04_A18/state.json')
        for a,b in zip(st['mesh_stages'],st['mesh_stages'][1:]):
            p,n=a['actual_passes'],a['actual_elements']
            self.assertEqual(next_stage([(p,n,.006)])[1:],(b['actual_passes'],b['requested']['percent_refinement']))
        self.assertEqual(next_stage([(st['actual_passes'],st['actual_elements'],st['convergence']['final_delta_s'])])[0],'final_sweep')
    def test_native_fixture_settings_and_negative(self):
        project=REPO/'hfss/INV01_A14.aedt'
        saved_setting(project,{'MaximumPasses':22,'MaxDeltaS':.005,'MinimumConvergedPasses':2},
            {'Type':'Interpolating','InterpTolerance':1.0,'RangeStart':'0.01GHz','RangeEnd':'15GHz','RangeStep':'0.01GHz'})
        with self.assertRaises(RuntimeError):saved_setting(project,{'MaximumPasses':16},{})
    def test_complex_phase_sensitive_and_native_band(self):
        f=np.array([1.,2.,3.,4.])
        old=np.ones((4,2),complex)
        new=old+1j*np.array([[1,2],[.004,.006],[.001,.002],[3,4]])
        self.assertEqual(compare_complex(f,new,f,old,2.,3.),[.004,.006])
        with self.assertRaises(ValueError):compare_complex(f,new,f+.001,old,2.,3.)
    def test_first_n04_review_reference(self):
        old=np.genfromtxt(REPO/'data/raw/N04_A18/sparams.csv',delimiter=',',names=True)
        f=old['Freq_GHz']
        ref=np.column_stack([old[f'{k}_real']+1j*old[f'{k}_imag'] for k in ('S11','S21')])
        refdoc=read(REPO/'experiments/fold_bandwidth_review_r5_20261110/out/REVIEW_CHECKS.json')['first_run_vs_archive']
        with np.load(HERE/'headless_results/S1_BASE_N04/full_modes.npz') as d:
            a=compare_complex(d['f_GHz'],d['S'][:,[0,2],0],f,ref,*refdoc['archive_BW15_band_GHz'])
        np.testing.assert_allclose(a,[refdoc['max_abs_dS11'],refdoc['max_abs_dS21']],rtol=0,atol=1e-12)

if __name__=='__main__':unittest.main()
