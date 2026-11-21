"""Stage 8 independent freeze and append-only runtime setup. Never imports AEDT."""
import argparse,os,subprocess,sys,shutil
from prepare_r10 import *
PLAN_COMMIT='576d4938ecaad4ab0058beced37cdf0a8a934def'
def source():
    r=stage8.ROOT7;h=stage8.H7
    st=read(h/'CURRENT_STATUS.json')
    if not st['stop']['normal_completion'] or (st['geometry_total'],st['actual_Analyze_total'])!=(200,1923):raise RuntimeError('R7 not closed')
    manifest=read(h/'FINAL_MANIFEST.json')
    for k,v in manifest.items():
        if sha(h/k)!=v:raise RuntimeError('historical R7 mismatch '+k)
    assert len(list((r/'ledger').glob('geometry_*.json')))==4 and len(list((r/'ledger').glob('Analyze_*.json')))==43
    assert read(r/'STOP.json')==read(h/'final/CLOSURE.json')==read(r/'COMPLETED.json')
    expected=subprocess.check_output(['git','show',PLAN_COMMIT+':'+stage8.PLAN],cwd=REPO)
    import hashlib
    assert hashlib.sha256(expected).hexdigest()==sha(REPO/stage8.PLAN)
    assert sha(HERE/'observer_r13.py')==sha(h/'observer_r13.py')
    return len(manifest)
def reg(out,post=False):
    out.mkdir(exist_ok=True);env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',PYTHONPATH='F:/2026-1/circuit/test/output/fig8_ml_dependencies_20261028')
    cmds=[]
    for name,folder,pat in [('R6',REPO/'experiments/fold_bandwidth_r14_stage6_r6_20261116','test_r*.py'),('R7',stage8.H7,'test_r15.py'),('R8',HERE,'test_r16.py')]:
        cmds.append((name,[sys.executable,'-m','unittest','discover','-s',str(folder),'-p',pat,'-v']))
    cmds+= [('default',[sys.executable,'tests/test_research.py']),('archive',[sys.executable,'tools/verify_archive.py']),('fresh_entry_dry_runs',[sys.executable,str(HERE/'entry_tests_r14.py'),str(HERE),str(out/'ENTRY_TESTS.json')])]
    results=[]
    for name,cmd in cmds:
        p=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True,encoding='utf-8',timeout=600)
        results.append(dict(label=name,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(name,p.returncode,flush=True)
        if p.returncode:print(p.stderr[-2000:],flush=True)
    d=dict(at=now(),passed=all(x['returncode']==0 for x in results),runs=results);write(out/'OFFLINE_TESTS.json',d)
    if not d['passed']:raise RuntimeError('offline tests failed')
def frozen_data():
    m=stage8.margin();assert abs(m['Gamma_req']-.073324)<1e-12 and abs(m['P_req_dB']+22.70)<=.005
    designs={};deriv={};w4=read(stage8.W4/'INPUT.json')['design']['geometry_mm']
    for n in ('W5R','W6R'):
        designs[PREFIX+n],deriv[n]=stage8.t1(n,m)
    for n in ('C2W','C3W'):
        designs[PREFIX+n]=stage8.build(w4,n,'CONTROL',**stage8.corners(n,m),selected_nominal_case='S7R15_W4R__T2')
    plan=(REPO/stage8.PLAN).read_text(encoding='utf-8')
    return dict(plan_commit=PLAN_COMMIT,margin=m,W4R_edge_replay=stage8.replay(),Q31_Q35_verbatim=plan[plan.index('## 4. 新登记'):plan.index('## 5. 报告')],designs=designs,T1_derivation=deriv,
        status='immutable before first native work',defaults='h0=.813 tol=.038; both stages incl conditional W6R',resources=dict(cores=14,groups=1,serial=True,ordinary_mesh=[100000,112000],max_delta=.005,new_dense=False,hook=False,direct_points=False),
        budget=dict(previous_geometry=200,previous_Analyze=1923,stage_max_geometry=10,cumulative_geometry_limit=212,effective_max_total_if_all_ten=210,new_Analyze_cap=140,per_case_Analyze_cap=14,slots=SLOTS),
        policy=dict(nominal_target=[6.74,0,m['P_req_dB']-.1],center_window=[6.73,6.75],both_peak_window=[m['P_req_dB']-.2,m['P_req_dB']],D_max=.2,S21_min_dB=-2,followup='same-width measured trials only; finite selective Broyden with R7 J and caps. T1 is extrapolated without inventing an observed W5/W6 seed. Closest by max normalized valley/D/individual peak error, not by BW.',conditional='C1W5 after tuned or closest measured finite W5R. W6R iff W5R tuned; no replacement for failed W6R screen. C1W6 iff W6R tuned and gain at least 0.050 GHz. Numerical missing independent subject to data dependencies, no invented result; strict integrity failure stops all.',delta_mesh=.002336,edge_linear_predictions_MHz={'C2W':[58,-209],'C3W':[103,-80]},W4R_common_target_correction_GHz_per_dB=.170,self_fix_max_precharge_packaging=2,observer='byte-identical to R7',runtime_children=['worker_stage2.py','observer_r13.py']))
def freeze():
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed'] or not read(HERE/'freeze/ENTRY_TESTS.json')['passed']:raise RuntimeError('tests')
    n=source();d=frozen_data();write(HERE/'freeze/R16_R8.json',{**d,'source_manifest_hashes_checked':n,'at':now()})
    print(d['margin'],d['T1_derivation'])
def prepare():
    if ROOT.exists():raise RuntimeError('runtime already exists; do not reset')
    f=read(HERE/'freeze/R16_R8.json');source()
    if any(f[k]!=v for k,v in frozen_data().items()):raise RuntimeError('freeze not reproducible')
    old=read(stage8.ROOT7/'authorization.json')
    cfg={k:copy.deepcopy(old[k]) for k in ('aedt_install','historical_hashes','code_hashes','plan_hashes','frozen_hashes','technical_recovery_policy')}
    h=stage8.H7;r=stage8.ROOT7
    for k,v in read(h/'FINAL_MANIFEST.json').items():cfg['historical_hashes'][str(h/k)]=v
    for p in [h/'FINAL_MANIFEST.json',r/'authorization.json',r/'COMPLETED.json',r/'STOP.json',*sorted((r/'ledger').glob('*.json'))]:cfg['historical_hashes'][str(p)]=sha(p)
    cfg.update(at=now(),human_authorized=True,batch='8',execution_revision='R16_STAGE8_R8',plan_commit=PLAN_COMMIT,user_authorization='R16 section 0, 8A + conditional 8B; 10 new ordinary geometries, cumulative <=212; R14 strictly limited precharge repairs',prior_geometry_total=200,prior_Analyze_total=1923,batch_geometry_limit=10,total_geometry_limit=212,batch_max_Analyze_from_geometry_caps=140,per_geometry_Analyze_limit=14,cores=14,tasks=1,serial=True,no_hook=True,inherited_geometry_logicals=[],inherited_logical_Analyze={},case_specs={},case_paths={},required_preflight_cases=[],parent_order=[PREFIX+n for n in ORDER],cache_case=None,designs=f['designs'],self_fix_cap=2)
    for n,k in SLOTS.items():
        p=PREFIX+n
        for i in range(1,k+1):
            c=p+f'__T{i}';cfg['case_specs'][c]=dict(parent_id=p,attempt_ordinal=i,numerical_retry=False);cfg['case_paths'][c]=f'runs/{p}/attempt_{i:03d}'
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    cfg['plan_hashes'][stage8.PLAN]=sha(REPO/stage8.PLAN)
    cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline') for p in (HERE/folder).glob('*.json')})
    ROOT.mkdir()
    for sub in ('ledger','decisions','model_freeze','publications','preflights'):(ROOT/sub).mkdir()
    write(ROOT/'authorization.json',cfg);shutil.copyfile(r/'sweep_role_confirmation.json',ROOT/'sweep_role_confirmation.json')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=['regress','freeze','prepare','posttests']);a=p.parse_args()
    if a.cmd in ('regress','posttests'):reg(HERE/('freeze' if a.cmd=='regress' else 'final'))
    else:globals()[a.cmd]()
