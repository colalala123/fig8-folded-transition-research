"""新2b门槛离线测试。使用临时记录及Git输出替身，不启动HFSS或网络。"""
import copy,json,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from common_stage2 import *
import runtime_stage2 as rt
import geometry

class Release(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="fig8_2b_release_test_")
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        reg=read(REPO/"experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json")
        self.pred=copy.deepcopy(next(r for r in reg["designs"] if r["batch"]=="2b"))
        self.pred.update(data_role="prospective_test",first_attempt_role_immutable=True)
        self.parent=self.pred["id"];self.case=self.parent+"__T1"
        audit=self.root/"audit.json";snap=self.root/"snapshot.json"
        write(audit,dict(passed=True,parents=15));write(snap,dict(summary=dict(count_conditions_met=True)))
        self.cfg=dict(human_authorized=True,batch="2b",limits=LIMITS,total_geometry_limit=187,
            code_hashes={},historical_hashes={},plan_hashes={},prior_batch_audit=str(audit),prior_batch_snapshot=str(snap),
            parent_order=[self.parent],designs={self.parent:self.pred},case_paths={self.case:"uniform_control/test/attempt_001"},
            case_specs={self.case:dict(parent_id=self.parent,attempt_ordinal=1)})
        write(self.root/"authorization.json",self.cfg)
        self.w=case_dir(self.root,self.case,self.cfg);(self.w/"input").mkdir(parents=True)
        self.f=dict(authorization_sha256=sha(self.root/"authorization.json"),resume=False,inherited_Analyze=0,
            parent_id=self.parent,attempt_ordinal=1,source_hashes={},design=copy.deepcopy(self.pred),
            nominal_a_mm=0.,expected_boxes=geometry.slot_boxes(self.pred["geometry_mm"],self.pred["topology"]))
        self.save()
    def save(self):
        (self.w/"input/freeze.json").write_text(json.dumps(self.f),encoding="utf-8")
    def check(self):
        with patch.object(rt,"verify_prediction_publication",return_value=None):
            return rt.verify_release(self.root,self.case)
    def test_valid_fixture(self):self.assertEqual(self.check()[1]["parent_id"],self.parent)
    def test_no_actual_publication_proof_rejects(self):
        with self.assertRaises(FileNotFoundError):rt.verify_release(self.root,self.case)
    def test_first_role_cannot_be_tuned(self):
        self.f["design"]["data_role"]="tuned_data";self.save()
        with self.assertRaises(RuntimeError):self.check()
    def test_resume_rejects(self):
        self.f["resume"]=True;self.save()
        with self.assertRaises(RuntimeError):self.check()
    def test_existing_worker_rejects(self):
        write(self.w/"worker_started.json",{})
        with self.assertRaises(RuntimeError):self.check()
    def test_bad_CAD_rejects(self):
        self.f["expected_boxes"][0]["parameters_mm"]["XSize"]+=.01;self.save()
        with self.assertRaises(RuntimeError):self.check()
    def test_pause_rejects(self):
        write(self.root/"PAUSE.json",dict(reason="test"))
        with self.assertRaises(RuntimeError):self.check()
    def test_incomplete_prior_gate_rejects(self):
        p=Path(self.cfg["prior_batch_snapshot"])
        p.write_text(json.dumps(dict(summary=dict(count_conditions_met=False))),encoding="utf-8")
        with self.assertRaises(RuntimeError):self.check()

class Publication(unittest.TestCase):
    def fixture(self):
        blob=b"frozen example";h=hashlib.sha256(blob).hexdigest()
        cfg=dict(model_path="m.json",model_sha256=h,predictions_path="p.json",predictions_sha256=h)
        proof=dict(remote_verified=True,branch="codex/fold-bandwidth-r4-execution",authorization_sha256=h,
            files_sha256={"m.json":h,"p.json":h},commit="test-commit")
        return blob,h,cfg,proof
    def test_immutable_blob_matches(self):
        blob,h,cfg,proof=self.fixture()
        with patch.object(rt,"read",return_value=proof),patch.object(rt,"sha",return_value=h),patch.object(rt.subprocess,"check_output",return_value=blob) as call:
            rt.verify_prediction_publication(Path("temporary_test_root"),cfg)
            self.assertEqual(call.call_count,2)
    def test_remote_flag_required(self):
        blob,h,cfg,proof=self.fixture();proof["remote_verified"]=False
        with patch.object(rt,"read",return_value=proof):
            with self.assertRaises(RuntimeError):rt.verify_prediction_publication(Path("temporary_test_root"),cfg)
    def test_changed_committed_blob_rejects(self):
        blob,h,cfg,proof=self.fixture()
        with patch.object(rt,"read",return_value=proof),patch.object(rt,"sha",return_value=h),patch.object(rt.subprocess,"check_output",return_value=b"changed"):
            with self.assertRaises(RuntimeError):rt.verify_prediction_publication(Path("temporary_test_root"),cfg)

if __name__=="__main__":unittest.main()
