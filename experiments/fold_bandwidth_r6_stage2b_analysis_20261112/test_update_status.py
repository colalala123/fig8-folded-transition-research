import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from update_status import snapshot
def put(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x),encoding="utf-8")
class Status(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.r=Path(self.t.name)
        for n in ("ledger","decisions"):(self.r/n).mkdir()
        self.cfg=dict(batch="2b",case_paths={"A__T1":"runs/A/attempt_001"},case_specs={"A__T1":dict(attempt_ordinal=1)},
            prior_geometry_total=49,prior_Analyze_total=415,model_sha256="model",predictions_sha256="pred")
        put(self.r/"authorization.json",self.cfg);self.w=self.r/"runs/A/attempt_001";self.w.mkdir(parents=True)
    def test_unstarted(self):
        q=snapshot(self.r);self.assertEqual(q["geometry_used"],0);self.assertEqual(q["active"],[])
    def test_dead_identity_not_running(self):
        put(self.w/"worker_started.json",dict(pid=3,create_time=1))
        with patch("update_status.same_worker",return_value=False):q=snapshot(self.r)
        self.assertEqual(q["active"],[]);self.assertEqual(len(q["issues"]),1)
    def test_alive_does_not_invent_14core(self):
        put(self.w/"worker_started.json",dict(pid=3,create_time=1))
        with patch("update_status.same_worker",return_value=True):q=snapshot(self.r)
        self.assertFalse(q["active"][0]["adaptive14_observed"])
    def test_request_not_complete(self):
        put(self.r/"ledger/Analyze_000.json",{})
        q=snapshot(self.r);self.assertEqual(q["total_Analyze_requested"],416);self.assertEqual(q["Analyze_validated_completed"],0)
        self.assertNotIn("total_Analyze_validated_completed",q)
    def test_real_ACK_hash_required(self):
        put(self.w/"done.json",{});put(self.w/"review/visual_ack.json",dict(actually_viewed=True,plot_sha256="bad",extraction_sha256="bad"))
        (self.w/"review/S11_S21.png").write_bytes(b"x");put(self.w/"review/extraction_R2.json",{})
        q=snapshot(self.r);self.assertEqual(q["first_prospective_completed"],1);self.assertEqual(q["first_prospective_visual_ACK"],0)
        self.assertTrue(q["issues"])
    def test_wrong_batch(self):
        self.cfg["batch"]="2a";put(self.r/"authorization.json",self.cfg)
        with self.assertRaises(ValueError):snapshot(self.r)
if __name__=="__main__":unittest.main()
