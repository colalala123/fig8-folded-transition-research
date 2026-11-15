"""R13 offline regressions: no AEDT, processes, dispatch or network."""
import copy,importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from common_stage2 import *
import r13,budget_stage2 as budget

def r4_budget():
    s=importlib.util.spec_from_file_location('immutable_r4_budget',r13.PRIOR_H/'budget_stage2.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class R13Tests(unittest.TestCase):
    def cfg(self):
        return dict(execution_revision='R13_STAGE6_R5',human_authorized=True,plan_commit='0c55fdc',
            plan_hashes={r13.PLAN:sha(REPO/r13.PLAN)},cache_stop_sha256=sha(r13.PRIOR_R/'STOP.json'),
            cache_history=read(HERE/'freeze/R13_R5.json')['cache_history'],cache_case=r13.CACHE_CASE,
            batch_geometry_limit=4,total_geometry_limit=200,prior_geometry_total=193,prior_Analyze_total=1846)
    def freeze(self):
        return dict(resume=True,inherited_Analyze=12,logical_case=r13.CACHE_CASE,
            cache_source_manifest_sha256=sha(HERE/'freeze/CACHE_MANIFEST.json'),design=read(r13.SOURCE/'input/freeze.json')['design'])
    def test01_only_authorized_stop(self):
        c=self.cfg();f=self.freeze();self.assertTrue(r13.verify_cache_input(Path('.'),f,c))
        for k,v in [('execution_revision','R12_STAGE6_R4'),('human_authorized',False),('plan_commit','ead3d02'),('cache_stop_sha256','x')]:
            q=copy.deepcopy(c);q[k]=v
            with self.assertRaises(RuntimeError):r13.verify_cache_input(Path('.'),f,q)
        for k,v in [('resume',False),('inherited_Analyze',11),('logical_case','another')]:
            q=copy.deepcopy(f);q[k]=v
            with self.assertRaises(RuntimeError):r13.verify_cache_input(Path('.'),q,c)
    def test02_all_history_rows_fixed(self):
        c=self.cfg();h=[tuple(x) for x in c['cache_history']];self.assertTrue(r13.verify_history(h,c))
        for i,item in [(26,(28,247756,.0023507)),(26,(27,247757,.0023507)),(5,(6,5928,.11358))]:
            q=h.copy();q[i]=item
            with self.assertRaises(RuntimeError):r13.verify_history(q,c)
        with self.assertRaises(RuntimeError):r13.verify_history(h+h[-1:],c)
    def test03_r4_still_refuses_refinement(self):
        with self.assertRaises(NumericalStop):dense_next_stage([(27,247756,.0023507)])
    def test04_same_geometry_thirteenth_exactly_once(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/'ledger').mkdir();cfg=self.cfg();case=r13.CACHE_CASE
            cfg['case_specs']={case:dict(parent_id='S6R10_B1Rdense',attempt_ordinal=1,numerical_retry=False)}
            write(r/'authorization.json',cfg);f=self.freeze();f.update(parent_id='S6R10_B1Rdense',attempt_ordinal=1,numerical_retry=False)
            rec=dict(Analyze_requested=12);budget.charge(r,case,'final_sweep',rec,f)
            self.assertEqual(rec['Analyze_requested'],13);self.assertEqual(len(list((r/'ledger').glob('geometry_*'))),0)
            self.assertEqual(len(list((r/'ledger').glob('Analyze_*'))),1)
            with self.assertRaises(RuntimeError):budget.charge(r,case,'final_sweep',rec,f)
            with self.assertRaises(RuntimeError):budget.charge(r,case,'adaptive_12',dict(Analyze_requested=12),f)
    def test05_no_adaptive_role(self):
        def obs(role):return dict(command_tail=f'{role} -max_processors 14 -numParallelGroups 1',verified_owned_ancestry=True,isolated_scratch=True)
        self.assertTrue(r13.verify_sweep_roles([obs('-solve')])['passed'])
        with self.assertRaises(RuntimeError):r13.verify_sweep_roles([obs('-solve'),obs('-solve_broadband_adapt')])
        with self.assertRaises(RuntimeError):r13.verify_sweep_roles([obs('-solve'),obs('-port_adapt')])
        q=obs('-solve');q['verified_owned_ancestry']=False
        with self.assertRaises(RuntimeError):r13.verify_sweep_roles([q])
    def test06_three_statistical_labels_and_fallback(self):
        a=read(HERE/'freeze_6B/R10_2.json')['analysis'];n=dict(low_peak_dB=-22.5076,high_peak_dB=-22.6056)
        corner=dict(low_peak_dB=-21.,high_peak_dB=-20.3)
        for db,label in [(-22.4,'统计稳健（含网格残差）'),(-22.15,'统计稳健（不含网格残差，边缘）'),(-21.9,'不满足统计稳健')]:
            d=dict(low_peak_dB=db,high_peak_dB=db-.1);x=r13.confirmation(n,d,corner,a);self.assertEqual(x['statistical_label'],label)
        x=r13.confirmation(n,None,corner,a);self.assertEqual(x['corner_bias_used'],.00276);self.assertIn('未经本设计确认',x['worst_corner_label'])
        x=r13.confirmation(n,dict(low_peak_dB=-23,high_peak_dB=-23.1),corner,a);self.assertEqual(x['own_nonnegative_mesh_dGamma'],0)
    def test07_Q25_Q26_verbatim_and_sweep_equality(self):
        f=read(HERE/'freeze/R13_R5.json');plan=(REPO/r13.PLAN).read_text(encoding='utf-8')
        self.assertEqual(f['Q25_Q26_verbatim'],plan.split('## 4. 新登记的预测')[1].split('## 5. 报告')[0])
        self.assertEqual(f['nominal_T3_final_sweep'],f['cache_final_sweep']);self.assertEqual(f['source_adaptive_settings']['MaximumPasses'],27)
        self.assertEqual(f['nominal_T3_full_sweep_section'],f['retained_cache_full_sweep_section_enabled'])
    def test08_new_geometry_cap_four(self):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/'ledger').mkdir();c=self.cfg();case='S6R10_W4__T2';p='S6R10_W4'
            c['case_specs']={case:dict(parent_id=p,attempt_ordinal=2,numerical_retry=False)};write(r/'authorization.json',c)
            for i in range(4):write(r/'ledger'/f'geometry_{i}.json',{})
            f=dict(logical_case=case,parent_id=p,attempt_ordinal=2,numerical_retry=False,design={})
            with self.assertRaises(RuntimeError):budget.charge(r,case,'adaptive_00',dict(Analyze_requested=0),f)

if __name__=='__main__':unittest.main(verbosity=2)
