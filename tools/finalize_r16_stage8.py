"""Stage 8 fail-closed offline ledger + evidence audit; never starts or stops AEDT."""
import collections,os,sys,json,subprocess
from pathlib import Path
import psutil
from analyze_r16_stage8 import H,ROOT,REPO,stage8,manage,case_dir,read,sha,now
from report_r16_stage8 import write_x,F

def final():
    assert not (ROOT/'STOP.json').exists() and not (ROOT/'PAUSE.json').exists()
    cfg=read(ROOT/'authorization.json');res=read(F/'RESULTS.json');qa=read(F/'VISUAL_QA.json')
    for name in ('OFFLINE_TESTS','ENTRY_TESTS'):assert read(F/(name+'.json'))['passed'],name
    assert qa['actually_viewed'] and all(qa['sha256'][n]==sha(F/n) for n in ('CURVES.png','WIDTH_LAW.png'))
    native=[];workers=[]
    for p in psutil.process_iter(['name','cmdline','create_time']):
        name=(p.info['name'] or '').lower();cmd=' '.join(p.info['cmdline'] or []).replace('\\','/').lower()
        if name in ('ansysedt.exe','hf3d.exe'):native.append([p.pid,name,p.info['create_time']])
        if p.pid!=os.getpid() and name in ('python.exe','pythonw.exe') and (str(ROOT).replace('\\','/').lower() in cmd or H.name.lower() in cmd) and any(x in cmd for x in ('worker_stage2.py','observer_r13.py','controller_stage2.py')):workers.append([p.pid,name,p.info['create_time']])
    assert not workers and not native,(workers,native)
    code={**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}
    for name,digest in code.items():assert sha(REPO/name)==digest,name
    for path,digest in cfg['historical_hashes'].items():assert sha(path)==digest,path
    dec={n:read(ROOT/'decisions'/(stage8.PREFIX+n+'_FINAL.json')) for n in stage8.ORDER}
    assert dec==res['decisions'] and all(d['complete'] for d in dec.values())
    for n in stage8.ORDER:
        ok,why=stage8.permission(n,dec)
        if not ok:assert dec[n].get('skipped') and not dec[n]['selected_case'],(n,why)
    dg=[read(p) for p in (ROOT/'ledger').glob('geometry_*.json')];da=[read(p) for p in (ROOT/'ledger').glob('Analyze_*.json')];counts=dict(collections.Counter(d['case'] for d in da))
    assert len(dg)<=10 and len(da)<=140 and all(count<=14 for count in counts.values())
    assert len(set(x['case'] for x in dg))==len(dg) and set(x['case'] for x in dg)==set(counts)
    assert res['budget']['new_geometries']==len(dg) and res['budget']['new_Analyze']==len(da)
    assert all(x['cores']==14 and x['tasks']==1 and not x['dense_confirmation'] for x in da)
    intervals=[];cases=[];seen=[]
    for case,count in counts.items():
        w=case_dir(ROOT,case,cfg);pub=H/'results'/case;sm=read(pub/'SUMMARY.json');rec=sm['record']
        for name,digest in read(pub/'MANIFEST.json').items():assert sha(pub/name)==digest,(case,name)
        assert rec['new_Analyze_requested']==count and sm['cleanup']['released'] and sm['cleanup']['scratch_restored']
        assert read(w/'supervised_start.json')['actual_14core_1group']
        assert read(H/'validation'/case/'PASS.json')['passed']
        proof=read(ROOT/'publications'/(case+'.json'))
        assert proof['remote_verified'] and proof['freeze_sha256']==sha(w/'input/freeze.json') and proof['authorization_sha256']==sha(ROOT/'authorization.json')
        subprocess.run(['git','merge-base','--is-ancestor',proof['commit'],'HEAD'],cwd=REPO,check=True)
        start=read(w/'worker_started.json')['at'];assert proof['at']<=start
        stages=sorted([x for x in da if x['case']==case],key=lambda x:x['index'])
        assert [r['index'] for r in stages]==list(range(count)) and all(r['at']>=start for r in stages)
        for f in (w/'evidence').glob('*_role_check.json'):assert read(f)['passed'],str(f)
        if rec['numerical_pass'] is True:
            assert rec['solve_completed'] and (w/'done.json').exists()
            ack=read(w/'review/visual_ack.json');assert ack['actually_viewed'] and ack['plot_sha256']==sha(w/'review/S11_S21.png') and ack['extraction_sha256']==sha(w/'review/extraction_R2.json')
            review=read(w/'review/REVIEW_STAGE3.json');assert review['numerical_pass'] and review['final_sweep_history_unchanged']
            assert stages[-1]['stage']=='final_sweep' and all((w/'evidence'/(r['stage']+'_role_check.json')).is_file() for r in stages)
        else:assert rec['numerical_pass'] is False and (w/'NUMERICAL_MISSING.json').is_file() and (w/'failure.txt').is_file()
        for f in [w/'worker_started.json',w/'owner.json',*list((w/'evidence').glob('*.ready'))]:
            if not f.is_file():continue
            q=read(f);pid=q['pid'];ct=q['create_time']
            try:same=abs(psutil.Process(pid).create_time()-ct)<.01
            except psutil.NoSuchProcess:same=False
            assert not same,(case,pid,ct)
            seen.append(dict(case=case,source=f.name,pid=pid,create_time=ct,same_identity_alive=False))
        intervals.append([start,rec['finished_at'],case])
        cases.append(dict(case=case,record=rec,publication=proof,roles=sm['roles'],manifest_verified=True))
    intervals.sort();assert all(a[1]<b[0] for a,b in zip(intervals,intervals[1:])),intervals
    unused=[c for c in cfg['case_specs'] if c not in counts]
    for case in unused:assert not case_dir(ROOT,case,cfg).exists(),case
    assert len(cases)==len(res['trials'])
    # All scientific, budget and process checks above precede creation of normal-closure markers.
    at=now();cl=dict(at=at,normal_completion=True,technical_failure=False,user_paused=False,reason='R16 stage 8 finite sequence complete incl. declared conditional skips; no further authority',prior_geometries=200,prior_Analyze=1923,new_geometries=len(dg),new_Analyze=len(da),cumulative_geometries=200+len(dg),cumulative_Analyze=1923+len(da),geometry_cap=212,distinct_simulated_configurations=res['budget']['distinct_simulated_configurations'],duplicate_full_configuration_groups=res['budget']['duplicate_full_configuration_groups'],duplicate_cost_charged=res['budget']['extra_Analyze_on_duplicate_inputs'],per_case_new_Analyze=counts,unused_cases_not_prepared=unused,unused_allowance_is_not_new_authorization=True,runtime_self_fixes=[],stage9_authorized=False,next_action='Await human review; no automatic dispatch')
    for p in (ROOT/'STOP.json',ROOT/'COMPLETED.json',F/'CLOSURE.json'):write_x(p,cl)
    st=manage.status(ROOT);assert st['stop']==cl
    tools=['analyze_r16_stage8.py','report_r16_stage8.py',Path(__file__).name]
    write_x(F/'FINAL_AUDIT.json',dict(at=at,passed=True,checked_cases=cases,finished_intervals=intervals,nonoverlap=True,historical_hashes_verified=len(cfg['historical_hashes']),frozen_code_plan_hashes_verified=len(code),process_identities=seen,live_owned_workers=workers,native_processes_observed=native,closure_sha256=sha(F/'CLOSURE.json'),report_tools_sha256={n:sha(REPO/'tools'/n) for n in tools}))
    with (H/'README.md').open('a',encoding='utf-8') as f:f.write('\n## 阶段 8 已完成并停止\n\n[中文报告](final/REPORT.md) · [可复算结果](final/RESULTS.json) · [最终审计](final/FINAL_AUDIT.json) · [闭账](final/CLOSURE.json)。未进入阶段 9。\n')
    with (H/'CURRENT_STATUS.md').open('a',encoding='utf-8') as f:f.write('\n正常闭账、不再派发。见 [中文报告](final/REPORT.md)。\n')
    files={p.relative_to(H).as_posix():sha(p) for p in sorted(H.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='FINAL_MANIFEST.json' and p.suffix!='.pyc'}
    write_x(H/'FINAL_MANIFEST.json',files);print(json.dumps(cl,ensure_ascii=False))
if __name__=='__main__':final()
