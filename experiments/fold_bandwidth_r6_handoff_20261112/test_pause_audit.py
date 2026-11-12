"""只测试暂停前缀审计的拒绝门槛；不连接HFSS。"""
import json,tempfile,unittest
from pathlib import Path
import audit_paused_prefix as a

class PauseAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.parents=[f"P{i:02d}" for i in range(22)]
        self.cfg=dict(batch="2b",parent_order=self.parents,case_paths={
            p+f"__T{i}":f"runs/{p}/attempt_{i:03d}" for p in self.parents for i in range(1,4)})
        self.put("authorization.json",self.cfg)
        (self.root/"decisions").mkdir()
    def tearDown(self): self.tmp.cleanup()
    def put(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value),encoding="utf-8")
    def paused(self): self.put("PAUSE.json",dict(require_explicit_human_resume=True))
    def test_missing_pause_rejected(self):
        with self.assertRaisesRegex(ValueError,"用户暂停"):a.audit(self.root,self.root/"public")
    def test_stop_not_hidden_by_pause(self):
        self.paused();self.put("STOP.json",{})
        with self.assertRaisesRegex(ValueError,"用户暂停"):a.audit(self.root,self.root/"public")
    def test_explicit_resume_required(self):
        self.put("PAUSE.json",dict(require_explicit_human_resume=False))
        with self.assertRaisesRegex(ValueError,"明确恢复"):a.audit(self.root,self.root/"public")
    def test_gap_in_prefix_rejected(self):
        self.paused();self.put("decisions/P01_FINAL.json",dict(complete=True))
        with self.assertRaisesRegex(ValueError,"严格的已完成前缀"):a.audit(self.root,self.root/"public")
    def test_incomplete_parent_rejected(self):
        self.paused();self.put("decisions/P00_FINAL.json",dict(complete=False))
        with self.assertRaisesRegex(ValueError,"未结项"):a.audit(self.root,self.root/"public")
    def test_next_worker_is_not_ignored(self):
        self.paused();self.put("decisions/P00_FINAL.json",dict(complete=True))
        self.put(self.cfg["case_paths"]["P01__T1"]+"/worker_started.json",{})
        with self.assertRaisesRegex(ValueError,"运行标记"):a.audit(self.root,self.root/"public")
    def test_original_full_batch_auditor_unchanged(self):
        d=a.read(Path(__file__).parent/"AUDIT_DERIVATION.json")
        self.assertEqual(a.m.sha(a.m.REPO/d["source"]),d["source_sha256"])
        expected=(a.m.REPO/d["source"]).read_text(encoding="utf-8")
        for c in d["changes"]:
            self.assertEqual(expected.count(c["old"]),1)
            expected=expected.replace(c["old"],c["new"],1)
        self.assertEqual(expected,Path(a.__file__).read_text(encoding="utf-8"))
if __name__=="__main__":unittest.main()
