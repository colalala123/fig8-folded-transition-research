"""Stage 9 immutable offline freeze, historical evidence verification and single runtime setup."""
import os,sys,subprocess,shutil,hashlib,copy,argparse
from common_stage2 import *
import stage9 as s
from replay_r9 import run
from fingerprint import old_index
def source():
    h=s.H8;r=s.ROOT8
    assert read(r/'STOP.json')==read(r/'COMPLETED.json')==read(h/'final/CLOSURE.json')
    a=read(r/'STOP.json');assert a['normal_completion'] and (a['cumulative_geometries'],a['cumulative_Analyze'])==(206,1984)
    assert len(list((r/'ledger').glob('geometry_*.json')))==6 and len(list((r/'ledger').glob('Analyze_*.json')))==61
    for k,v in read(h/'FINAL_MANIFEST.json').items():
        if sha(h/k)!=v:raise RuntimeError('R8 source changed '+k)
    assert sha(HERE/'observer_r13.py')==sha(h/'observer_r13.py')
    assert hashlib.sha256(subprocess.check_output(['git','show',s.COMMIT+':'+s.PLAN],cwd=REPO)).hexdigest()==sha(REPO/s.PLAN)
def regress(out):
    out.mkdir(exist_ok=True);env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',PYTHONPATH='F:/2026-1/circuit/test/output/fig8_ml_dependencies_20261028')
    runs=[]
    for label,cmd in [(name,['-m','unittest','discover','-s',str(path),'-p',pattern,'-v']) for name,path,pattern in [('R9',HERE,'test_r17.py'),('R8',s.H8,'test_r16.py'),('R7',s.stage8.H7,'test_r15.py'),('R6',REPO/'experiments/fold_bandwidth_r14_stage6_r6_20261116','test_r*.py')]]+[('default',['tests/test_research.py']),('archive',['tools/verify_archive.py']),('fresh_entries',[str(HERE/'entry_tests_r14.py'),str(HERE),str(out/'ENTRY_TESTS.json')])]:
        p=subprocess.run([sys.executable,*cmd],cwd=REPO,env=env,capture_output=True,text=True,encoding='utf-8',timeout=600)
        runs.append(dict(label=label,code=p.returncode,stdout=p.stdout,stderr=p.stderr));print(label,p.returncode,flush=True)
        if p.returncode:print(p.stderr[-2400:],flush=True);break
    d=dict(passed=len(runs)==7 and all(r['code']==0 for r in runs),runs=runs,at=now());write(out/'OFFLINE_TESTS.json',d)
    if not d['passed']:raise RuntimeError('offline gate failed; do not start HFSS')
def freeze():
    source();p=HERE/'freeze';rows=old_index();write(p/'COMPLETED_INPUT_INDEX.json',dict(rows=rows,scope='all completed archived R1-R8 CAD + earlier forward studies; legacy six-parameter collisions held conservatively; current R9 terminal inputs checked live'))
    r=run();write(p/'REPLAY.json',r)
    if not r['passed']:raise RuntimeError('R9 replay failed; do not solve')
    regress(p)
    plan=(REPO/s.PLAN).read_text(encoding='utf-8')
    write(HERE/'appendices/W5R.json',dict(J_initial=s.J0.tolist(),source='B1 measured J0; W5R T1-T3 chronological historical trials'))
    write(p/'R17_R9.json',dict(at=now(),plan_commit=s.COMMIT,margin=s.M,target=s.TARGET,acceptance=dict(center_GHz=[6.73,6.76],both_peaks_dB=[s.REQ-.2,s.REQ],abs_D_max=.2,S21_min_dB=-2),previous=[206,1984],geometry_cap=221,new_geometry_cap=15,cases=s.ORD,per_geometry_Analyze_limit={'ordinary':14,'dense':20},stage_api_cap=216,no_hook=True,serial_cores=14,groups=1,policy_3_verbatim=plan.split('## 3. 方案',1)[1].split('## 4. 新登记',1)[0],Q36_Q41_verbatim=plan[plan.index('## 4. 新登记'):plan.index('## 5. 报告')],publication='push R9 + tests before any native work; width appendices/selected predictions published before respective native solve; no R10 or additional geometry authorized'))
def prepare():
    source();r=s.ROOT;h=s.H8;oldroot=s.ROOT8
    if r.exists():raise RuntimeError('runtime exists; no reset')
    f=read(HERE/'freeze/R17_R9.json');assert read(HERE/'freeze/OFFLINE_TESTS.json')['passed'] and read(HERE/'freeze/ENTRY_TESTS.json')['passed'] and read(HERE/'freeze/REPLAY.json')['passed']
    assert run()==read(HERE/'freeze/REPLAY.json') and old_index()==read(HERE/'freeze/COMPLETED_INPUT_INDEX.json')['rows']
    old=read(oldroot/'authorization.json')
    cfg={k:copy.deepcopy(old[k]) for k in ('aedt_install','historical_hashes','code_hashes','plan_hashes','frozen_hashes','technical_recovery_policy')}
    for k,v in read(h/'FINAL_MANIFEST.json').items():cfg['historical_hashes'][str(h/k)]=v
    for p in [h/'FINAL_MANIFEST.json',oldroot/'authorization.json',oldroot/'STOP.json',oldroot/'COMPLETED.json',*sorted((oldroot/'ledger').glob('*.json'))]:cfg['historical_hashes'][str(p)]=sha(p)
    cfg.update(at=now(),human_authorized=True,batch='9',execution_revision='R17_STAGE9_R9',plan_commit=s.COMMIT,user_authorization='R17 stage 9 default h0/tol_h. Do not start before replay and freeze/push. R14 narrow precharge self-fix only.',prior_geometry_total=206,prior_Analyze_total=1984,batch_geometry_limit=15,total_geometry_limit=221,batch_max_Analyze_from_geometry_caps=216,per_geometry_Analyze_limit=14,dense_Analyze_limit=20,cores=14,tasks=1,serial=True,no_hook=True,inherited_geometry_logicals=[],inherited_logical_Analyze={},case_specs={},case_paths={},required_preflight_cases=[],parent_order=[s.PREFIX+n for n in s.ORD],cache_case=None,self_fix_cap=2)
    for n,ords in s.ORD.items():
        p=s.PREFIX+n
        for i in ords:
            c=p+f'__T{i}';cfg['case_specs'][c]=dict(parent_id=p,attempt_ordinal=i,numerical_retry=False);cfg['case_paths'][c]=f'runs/{p}/attempt_{i:03d}'
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')});cfg['plan_hashes'][s.PLAN]=sha(REPO/s.PLAN);cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for sub in ('freeze','offline') for p in (HERE/sub).glob('*.json')})
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip();remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/fold-bandwidth-r4-execution'],cwd=REPO,text=True).split()[0]
    if commit!=remote:raise RuntimeError('R9 not yet pushed')
    from publication_check import verify_blobs
    verify_blobs(commit,{**cfg['code_hashes'],**cfg['frozen_hashes'],**cfg['plan_hashes']})
    r.mkdir()
    for sub in ('ledger','decisions','model_freeze','publications','preflights'):(r/sub).mkdir()
    write(r/'authorization.json',cfg);shutil.copyfile(oldroot/'sweep_role_confirmation.json',r/'sweep_role_confirmation.json')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('cmd',choices=['freeze','prepare','posttests']);a=ap.parse_args()
    if a.cmd=='posttests':regress(HERE/'final')
    else:globals()[a.cmd]()
