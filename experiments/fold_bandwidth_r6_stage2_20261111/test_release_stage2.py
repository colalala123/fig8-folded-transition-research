"""2a门槛离线测试，不导入/创建PyAEDT实例。"""
import copy
import tempfile
import unittest
from pathlib import Path
from common_stage2 import *
from prepare_stage2 import initial_designs,prepare,tuned_design
from runtime_stage2 import verify_release
import geometry

class Release(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='fig8_stage2_test_')
        self.r=Path(self.tmp.name)
        self.pred=copy.deepcopy(initial_designs()[0]);self.parent=self.pred['id'];self.case=self.parent+'__T1'
        self.analysis=self.r/'analysis.json';write(self.analysis,dict(batch1b_outputs_complete=True))
        self.cfg=dict(human_authorized=True,batch='2a',limits=LIMITS,total_geometry_limit=187,
            code_hashes={},historical_hashes={},plan_hashes={},stage1_analysis=str(self.analysis),
            parent_order=[self.parent],designs={self.parent:self.pred},
            case_paths={self.case:'uniform_control/'+self.parent+'/attempt_001'},
            case_specs={self.case:dict(parent_id=self.parent,attempt_ordinal=1)})
        self.w=case_dir(self.r,self.case,self.cfg);(self.w/'input').mkdir(parents=True)
        write(self.r/'authorization.json',self.cfg)
        self.f=dict(authorization_sha256=sha(self.r/'authorization.json'),resume=False,inherited_Analyze=0,
            parent_id=self.parent,attempt_ordinal=1,source_hashes={},design=copy.deepcopy(self.pred),nominal_a_mm=self.pred['screen']['a_mm'],
            expected_boxes=geometry.slot_boxes(self.pred['geometry_mm'],self.pred['topology']))
        self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):
        # Fixtures only: tested production writer remains exclusive.
        import json
        (self.w/'input/freeze.json').write_text(json.dumps(self.f),encoding='utf-8')
    def test_valid_cold_freeze(self):self.assertEqual(verify_release(self.r,self.case)[1]['parent_id'],self.parent)
    def test_prior_start_blocks(self):
        write(self.w/'worker_started.json',dict(pid=123))
        with self.assertRaises(RuntimeError):verify_release(self.r,self.case)
    def test_resume_not_silently_released(self):
        self.f['resume']=True;self.save()
        with self.assertRaises(RuntimeError):verify_release(self.r,self.case)
    def test_prediction_tampering_blocks(self):
        self.f['design']['prediction']['equal_frequency_inner_peak_dB']=999;self.save()
        with self.assertRaises(RuntimeError):verify_release(self.r,self.case)
    def test_slot_boxes_tampering_blocks(self):
        self.f['expected_boxes'][0]['parameters_mm']['XSize']+=.1;self.save()
        with self.assertRaises(RuntimeError):verify_release(self.r,self.case)
    def test_stop_blocks(self):
        write(self.r/'STOP.json',dict(reason='test'))
        with self.assertRaises(RuntimeError):verify_release(self.r,self.case)
    def test_incomplete_1b_blocks_preparation_without_output(self):
        import json
        self.analysis.write_text(json.dumps(dict(batch1b_outputs_complete=False)),encoding='utf-8')
        dest=self.r/'not_created'
        with self.assertRaises(RuntimeError):prepare(self.r,dest,self.analysis)
        self.assertFalse(dest.exists())
    def test_tuned_record_uses_actual_screen_and_path(self):
        from presubmit import presubmit
        g={**self.pred['geometry_mm'],'Lm':6.7,'Ls1':16.5}
        screen=presubmit(g,0.,topology='straight_control')
        suggestion=dict(geometry_mm=g,prediction={'test_only':True},screen=screen,actual_a_mm=0.)
        q=tuned_design(self.pred,suggestion,self.parent,'test_curve_sha','uniform_control/TEST/attempt_002',0.)
        self.assertEqual(q['screen'],screen['screen_after'])
        self.assertEqual(q['initial_screen'],self.pred['screen'])
        self.assertEqual(q['future_run_directory'],'uniform_control/TEST/attempt_002')
        self.assertEqual(q['data_role'],'tuned_data')
        self.assertNotEqual(q['geometry_mm'],self.pred['geometry_mm'])
    def test_wrong_nominal_arm_rejected(self):
        self.f['nominal_a_mm']=1.;self.save()
        with self.assertRaises(RuntimeError):verify_release(self.r,self.case)
    def test_fifteen_only(self):
        a=initial_designs()
        self.assertEqual(len(a),15);self.assertEqual(sum(r['topology']=='straight_control' for r in a),1)
        self.assertEqual(sum(r['experiment']=='E1' for r in a),5)
        self.assertEqual(sum(r['experiment']=='E2' for r in a),5)
        self.assertEqual(sum(r['experiment']=='E3' for r in a),4)
if __name__=='__main__':unittest.main()
