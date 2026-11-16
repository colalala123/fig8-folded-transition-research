"""R15 offline final audit/normal closure. No solver or network calls."""
import collections,datetime,json,os,sys
from pathlib import Path
import psutil
REPO=Path(__file__).resolve().parents[1];H=REPO/'experiments/fold_bandwidth_r15_stage7_r7_20261116'
sys.path.insert(0,str(H))
from common_stage2 import read,sha,case_dir
from prepare_r10 import ROOT
import manage

def save(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)

def main():
    out=H/'final';assert not (ROOT/'STOP.json').exists(),'Already stopped; no repeat closure'
    cfg=read(ROOT/'authorization.json');res=read(out/'RESULTS.json')
    assert read(out/'POST_TESTS.json')['passed'] and read(out/'ENTRY_TESTS_POST_RUN.json')['passed']
    qa=read(out/'VISUAL_QA.json');assert qa['actually_viewed'] and qa['sha256']==sha(out/'CURVES.png')
    for p in cfg['parent_order']:assert read(ROOT/'decisions'/(p+'_FINAL.json'))['complete']
    frozen={**cfg['code_hashes'],**cfg['frozen_hashes'],**cfg['plan_hashes']}
    for rel,digest in frozen.items():assert sha(REPO/rel)==digest,rel
    for path,digest in cfg['historical_hashes'].items():assert sha(path)==digest,path
    native=[];workers=[]
    for p in psutil.process_iter(['name','cmdline','create_time']):
        name=(p.info['name'] or '').lower();cmd=' '.join(p.info['cmdline'] or []).replace('\\','/').lower()
        if name in ('ansysedt.exe','hf3d.exe'):native.append(dict(pid=p.pid,name=name,create_time=p.info['create_time']))
        if p.pid!=os.getpid() and name in ('python.exe','pythonw.exe') and any(x in cmd for x in ('worker_stage2.py','observer_r13.py','controller_stage2.py')) and (str(ROOT).replace('\\','/').lower() in cmd or H.name.lower() in cmd):workers.append(dict(pid=p.pid,name=name,create_time=p.info['create_time']))
    assert not native and not workers,(native,workers)
    ledger=[read(p) for p in (ROOT/'ledger').glob('Analyze_*.json')];geo=[read(p) for p in (ROOT/'ledger').glob('geometry_*.json')]
    counts=dict(collections.Counter(x['case'] for x in ledger));assert len(geo)<=6 and len(ledger)<=90
    assert all(x['cores']==14 and x['tasks']==1 for x in ledger)
    assert res['budget']['new_geometries']==len(geo) and res['budget']['new_Analyze']==len(ledger)
    cases=[];identities=[];intervals=[]
    for case,count in counts.items():
        w=case_dir(ROOT,case,cfg);pub=H/'results'/case;cap=20 if cfg['case_specs'][case]['parent_id']=='S7R15_W4Rdense' else 14
        assert count<=cap
        for rel,digest in read(pub/'MANIFEST.json').items():assert sha(pub/rel)==digest,(case,rel)
        s=read(pub/'SUMMARY.json');rec=s['record'];assert rec['new_Analyze_requested']==count
        assert rec['solve_completed'] and rec['numerical_pass']
        assert s['cleanup']['released'] and s['cleanup']['scratch_restored']
        ack=read(w/'review/visual_ack.json');assert ack['actually_viewed'] and ack['plot_sha256']==sha(w/'review/S11_S21.png') and ack['extraction_sha256']==sha(w/'review/extraction_R2.json')
        review=read(w/'review/REVIEW_STAGE3.json');assert review['numerical_pass'] and review['final_sweep_history_unchanged']
        assert read(w/'supervised_start.json')['actual_14core_1group']
        assert read(H/'validation'/case/'PASS.json')['passed']
        for p in (w/'evidence').glob('*_role_check.json'):assert read(p)['passed'],str(p)
        for p in [w/'owner.json',w/'worker_started.json',*list((w/'evidence').glob('*.ready'))]:
            if not p.exists():continue
            d=read(p);pid=d.get('pid');ct=d.get('create_time')
            if pid is None or ct is None:continue
            same=psutil.pid_exists(pid) and abs(psutil.Process(pid).create_time()-ct)<.01
            assert not same,('owned process still alive',p,pid)
            identities.append(dict(case=case,source=p.name,pid=pid,create_time=ct,same_identity_alive=False))
        start=read(w/'worker_started.json')['at'];end=rec['finished_at'];intervals.append((start,end,case))
        cases.append(dict(case=case,record=rec,cleanup=s['cleanup'],roles=s['roles'],public_manifest_verified=True,actual_view_ack_verified=True))
    intervals.sort();assert all(a[1]<b[0] for a,b in zip(intervals,intervals[1:])),intervals
    unused=[c for c in cfg['case_specs'] if c not in counts];assert all(not case_dir(ROOT,c,cfg).exists() for c in unused)
    at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    closure=dict(at=at,normal_completion=True,technical_failure=False,user_paused=False,reason='R15 stage7 completed and reviewed; no stage8 authorization',new_geometries=len(geo),new_Analyze=len(ledger),cumulative_geometries=196+len(geo),cumulative_Analyze=1880+len(ledger),geometry_cap=202,per_case_new_Analyze=counts,unused_cases_not_prepared=unused,unused_allowance_is_not_new_authorization=True,runtime_self_fixes=[],stage8_authorized=False,next_action='Await human review; no automatic dispatch')
    save(ROOT/'STOP.json',closure);save(ROOT/'COMPLETED.json',closure);save(out/'CLOSURE.json',closure)
    st=manage.status(ROOT);assert st['stop']['normal_completion']
    save(out/'FINAL_AUDIT.json',dict(at=at,passed=True,cases=cases,process_identity_checks=identities,native_processes=native,owned_workers=workers,frozen_hashes_verified=len(frozen),historical_hashes_verified=len(cfg['historical_hashes']),ledger_count=len(ledger),serial_intervals=intervals,unused_cases=unused,public_case_manifests_verified=len(cases),closure_sha256=sha(out/'CLOSURE.json'),report_builder_sha256=sha(REPO/'tools/report_r15_stage7.py'),finalizer_sha256=sha(Path(__file__))))
    with (out/'REPORT.md').open('a',encoding='utf-8') as f:f.write('\n## 最终复核\n\n收尾离线测试、归档校验、独立解释器导入和观察器空跑均通过。各点角色、看图ACK、原生结果清单、串行时间区间及全部冻结/历史哈希均已核对。已写入正常完成STOP及COMPLETED；这不是技术故障或用户暂停，不得自动接续阶段8。详见POST_TESTS.json、FINAL_AUDIT.json和CLOSURE.json。\n')
    with (H/'README.md').open('a',encoding='utf-8') as f:f.write('\n## 阶段7已完成并停止\n\n[中文报告](final/REPORT.md)、[机器可读结果](final/RESULTS.json)、[正常闭账](final/CLOSURE.json)、[最终审计](final/FINAL_AUDIT.json)。本轮'+str(len(geo))+'几何/'+str(len(ledger))+' Analyze，累计'+str(196+len(geo))+'/202几何。未用额度不作新授权。\n')
    with (H/'CURRENT_STATUS.md').open('a',encoding='utf-8') as f:f.write('\n正常完成闭账；不进入阶段8。见final/REPORT.md。\n')
    print(json.dumps(closure,ensure_ascii=False))
if __name__=='__main__':main()
