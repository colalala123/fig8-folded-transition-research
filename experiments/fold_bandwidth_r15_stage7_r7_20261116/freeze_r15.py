"""R15 offline freeze, regression and immutable runtime preparation. No native API."""
import argparse,ast,copy,json,os,shutil,subprocess,sys
from common_stage2 import *
import stage7
from prepare_r10 import ROOT

def source_checks():
    st=read(stage7.PRIOR_H/'CURRENT_STATUS.json')
    if (st['geometry_total'],st['actual_Analyze_total'])!=(196,1880) or not st['stop']['normal_completion']:raise RuntimeError('R6 not normally closed at196/1880')
    for rel,h in read(stage7.PRIOR_H/'FINAL_MANIFEST.json').items():
        if sha(stage7.PRIOR_H/rel)!=h:raise RuntimeError('R6 archive changed '+rel)
    if len(list((stage7.PRIOR_R/'ledger').glob('geometry_*.json')))!=3 or len(list((stage7.PRIOR_R/'ledger').glob('Analyze_*.json')))!=34:raise RuntimeError('R6 cost changed')
    return True

def draft():
    source_checks();m=stage7.margin();d,t=stage7.t1(m);table=stage7.margin_table()
    # This file is not an authorization or frozen solve input.
    value=dict(status='OFFLINE_DRAFT_NOT_AUTHORIZED_FOR_SOLVE',plan_commit='db8596b',margin=m,table_checks=table,T1=d,T1_derivation=t,
        blocked_on_table_row=[x for x in table if not x['within_0p005']],new_Analyze=0,
        Q27_Q30_verbatim=(REPO/stage7.PLAN).read_text(encoding='utf-8').split('## 4. 新登记的预测')[1].split('## 5. 报告')[0])
    write(HERE/'DRAFT_R15.json',value)
    # J used for subsequent suggestions is the chosen direct measured B1 J, not the nearby proxy.
    (HERE/'offline/SENSITIVITY.json').write_text(json.dumps(dict(J0=t['coordinate_J'],source='B1 P1-P6 central differences; R15 T1 choice',rows='Lm,Lc,Ws',cols='center,D,L'),indent=2)+'\n',encoding='utf-8')
    return dict(draft=True,table_problem=value['blocked_on_table_row'],T1=d['geometry_mm'])

def regress():
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['OPENBLAS_NUM_THREADS']='1';env['PYTHONPATH']='F:/2026-1/circuit/test/output/fig8_ml_dependencies_20261028'
    cmds=[('R6_55',[sys.executable,'-m','unittest','discover','-s',str(stage7.PRIOR_H),'-p','test_r*.py','-v']),
          ('R7_new',[sys.executable,'-m','unittest','discover','-s',str(HERE),'-p','test_r15.py','-v']),
          ('default_11',[sys.executable,'tests/test_research.py']),('archive',[sys.executable,'tools/verify_archive.py']),
          ('fresh_entries',[sys.executable,str(HERE/'entry_tests_r14.py'),str(HERE),str(HERE/'freeze/ENTRY_TESTS_R7.json')])]
    logs=[]
    for name,cmd in cmds:
        p=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True,encoding='utf-8',timeout=300)
        logs.append(dict(label=name,command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(name,p.returncode,flush=True)
    proof=dict(at=now(),passed=all(d['returncode']==0 for d in logs),runs=logs)
    write(HERE/'freeze/OFFLINE_TESTS.json',proof)
    if not proof['passed']:raise RuntimeError('Offline tests failed; no native work')
    return proof['passed']

def freeze():
    source_checks();d=read(HERE/'DRAFT_R15.json');table=stage7.margin_table();bad=[x for x in table if not x['within_0p005']]
    active=[r for r in table if r['tol_h_mm']==d['margin']['tol_h_mm'] and r['mode']==d['margin']['mode']]
    if len(active)!=1 or not active[0]['within_0p005']:raise RuntimeError('R15 active P_req differs from selected table row by more than0.005; stop before native work')
    policy=dict(active_inputs='User-authorized default h0=.813, tol_h=.038, corner mode',active_row_within_tolerance=True,
        inactive_discrepancy_disclosed=bad,nondefault_row_not_authorized_or_used=True,
        note='No formula/table value changed. The selected default row satisfies R15 tolerance; no assumed human waiver for the unused .025mm row.')
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed'] or not read(HERE/'freeze/ENTRY_TESTS_R7.json')['passed']:raise RuntimeError('tests missing')
    if d['margin']!=stage7.margin() or d['T1']!=stage7.t1(stage7.margin())[0]:raise RuntimeError('draft not reproducible')
    capture=lambda p:ast.dump(next(x for x in ast.parse(p.read_text(encoding='utf-8-sig')).body if isinstance(x,ast.FunctionDef) and x.name=='capture'))
    assert capture(HERE/'observer_r13.py')==capture(stage7.PRIOR_H/'observer_r13.py')
    f=dict(at=now(),status='R15_R7_FROZEN_BEFORE_NATIVE',plan_commit='db8596b',margin=d['margin'],table_checks=table,
        table_exception_policy=policy if bad else None,designs={'S7R15_W4R':d['T1']},T1_derivation=d['T1_derivation'],Q27_Q30_verbatim=d['Q27_Q30_verbatim'],
        dense_rule=dict(min_cells_with_delta=200000,max_delta=.002,forced_sweep_cells=220000,safety_stop_above=300000,max_passes=34,max_Analyze=20,refinement_percent='30 below150000;10 below185000;5 otherwise'),
        ordinary=dict(min_cells=100000,max_cells=112000,max_delta=.005,max_Analyze=14),
        budget=dict(prior_geometries=196,prior_Analyze=1880,new_geometry_cap=6,total_geometry_cap=202,max_new_Analyze=90),
        resources=dict(cores=14,tasks=1,serial=True,no_hook=True),observer_capture_AST_identical=True,
        child_entries=read(HERE/'freeze/ENTRY_TESTS_R7.json')['entries'],direct_runtime_children=['worker_stage2.py','observer_r13.py'],
        finite_tuning=dict(total_attempts=4,target_center=6.735,center_range=[6.72,6.75],D_max=.2,peak_window=[d['margin']['P_req_dB']-.2,d['margin']['P_req_dB']],T2_T4_caps=[.06,.4,.13],fallback='nearest reviewed W4R by normalized target error; numerical missing terminates tuning and controls use best available or frozen T1 geometry, no nominal truth invented'),
        self_fix_cap=2,self_fixes_used=0,self_fix_scope='R14 section3 pre-charge packaging only; fresh reproducer+regression+patched freeze push before retry; all other strict errors stop',
        no_direct_frequency_points=True,no_stage8=True)
    write(HERE/'freeze/R15_R7.json',f)
    return dict(frozen=True,margin=f['margin'],T1=d['T1']['geometry_mm'])

def prepare():
    if ROOT.exists():raise RuntimeError('R7 runtime already exists; no reset')
    f=read(HERE/'freeze/R15_R7.json');source_checks()
    cfg=copy.deepcopy(read(stage7.PRIOR_R/'authorization.json'))
    historical=cfg['historical_hashes']
    for rel,h in read(stage7.PRIOR_H/'FINAL_MANIFEST.json').items():historical[str(stage7.PRIOR_H/rel)]=h
    for p in [stage7.PRIOR_H/'FINAL_MANIFEST.json',stage7.PRIOR_R/'STOP.json',stage7.PRIOR_R/'COMPLETED.json',stage7.PRIOR_R/'authorization.json',*list((stage7.PRIOR_R/'ledger').glob('*.json'))]:historical[str(p)]=sha(p)
    cfg.update(at=now(),human_authorized=True,execution_revision='R15_STAGE7_R7',plan_commit='db8596b',user_authorization='Human accepts R15 section0, stage7 W4R<=4,C1W,dense<=1; total geometry cap202; R14 pre-charge packaging exception only',
        prior_geometry_total=196,prior_Analyze_total=1880,batch_geometry_limit=6,total_geometry_limit=202,batch_max_Analyze_from_geometry_caps=90,
        inherited_geometry_logicals=[],inherited_logical_Analyze={},inherited_closed_parents=[],cancelled_parents=[],case_paths={},case_specs={},required_preflight_cases=[],
        parent_order=['S7R15_W4R','S7R15_C1W','S7R15_W4Rdense'],cache_case=None,designs=f['designs'],self_fix_cap=2)
    for stale in ('cache_source','cache_stop_sha256','cache_history','continuation_STOP_sha256'):cfg.pop(stale,None)
    for n,count in [('W4R',4),('C1W',1),('W4Rdense',1)]:
        parent='S7R15_'+n
        for i in range(1,count+1):
            c=parent+f'__T{i}';cfg['case_paths'][c]=f'runs/{parent}/attempt_{i:03d}';cfg['case_specs'][c]=dict(parent_id=parent,attempt_ordinal=i,numerical_retry=False)
    cfg['plan_hashes'][stage7.PLAN]=sha(REPO/stage7.PLAN)
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline') for p in (HERE/folder).glob('*.json')})
    if (HERE/'TABLE_POLICY_APPROVAL.json').exists():cfg['frozen_hashes'][(HERE/'TABLE_POLICY_APPROVAL.json').relative_to(REPO).as_posix()]=sha(HERE/'TABLE_POLICY_APPROVAL.json')
    ROOT.mkdir()
    for n in ('ledger','decisions','model_freeze','publications','preflights'):(ROOT/n).mkdir()
    write(ROOT/'authorization.json',cfg);shutil.copyfile(stage7.PRIOR_R/'sweep_role_confirmation.json',ROOT/'sweep_role_confirmation.json')
    return dict(prepared=True,case_slots=len(cfg['case_specs']))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['draft','regress','freeze','prepare']);a=ap.parse_args();print(globals()[a.command]())
