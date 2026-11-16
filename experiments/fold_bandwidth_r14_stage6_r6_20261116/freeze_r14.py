"""Offline R14 freeze and complete regression evidence. No native API."""
import ast,json,os,subprocess,sys
from pathlib import Path
from common_stage2 import *
import r13

def freeze():
    old=r13.R5_H
    failure=read(HERE/'freeze/ENTRY_TESTS_R5_FAILURE_V2.json');passed=read(HERE/'freeze/ENTRY_TESTS_R6_PASS_V2.json')
    if not failure['expected_failure_reproduced'] or not passed['passed']:raise RuntimeError('entry proof missing')
    def capture_body(p):return ast.dump(next(n for n in ast.parse(p.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='capture'))
    if capture_body(old/'observer_r13.py')!=capture_body(HERE/'observer_r13.py'):raise RuntimeError('observer logic changed')
    for p in (old/'freeze').glob('*.json'):
        if p.name=='OFFLINE_TESTS.json':continue
        if sha(p)!=sha(HERE/'freeze'/p.name):raise RuntimeError('inherited scientific freeze changed '+p.name)
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['OPENBLAS_NUM_THREADS']='1'
    # Existing offline archive ML dependency directory; never needed by isolated entry tests.
    env['PYTHONPATH']='F:/2026-1/circuit/test/output/fig8_ml_dependencies_20261028'
    runs=[]
    commands=[('R5_55',[sys.executable,'-m','unittest','discover','-s',str(old),'-p','test_r*.py','-v']),
              ('R6_55',[sys.executable,'-m','unittest','discover','-s',str(HERE),'-p','test_r*.py','-v']),
              ('default_11',[sys.executable,'tests/test_research.py']),('archive',[sys.executable,'tools/verify_archive.py'])]
    for label,cmd in commands:
        p=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True,encoding='utf-8',timeout=300)
        runs.append(dict(label=label,command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        print(label,p.returncode,flush=True)
    write(HERE/'freeze/OFFLINE_TESTS.json',dict(at=now(),passed=all(x['returncode']==0 for x in runs),runs=runs,
        entry_failure_sha256=sha(HERE/'freeze/ENTRY_TESTS_R5_FAILURE_V2.json'),entry_pass_sha256=sha(HERE/'freeze/ENTRY_TESTS_R6_PASS_V2.json')))
    if not all(x['returncode']==0 for x in runs):raise RuntimeError('regression failed; do not prepare')
    # No new continuation based on R5 clone: R4 is the only cache source.
    r13.audit_cache_files(r13.SOURCE,{})
    direct=[dict(script='worker_stage2.py',caller='controller_stage2.py:launch',cwd='REPO',argv='python -u worker_stage2.py --runtime ROOT --case CASE'),
            dict(script='observer_r13.py',caller='solve_block.py:solve_stage',cwd='inherited REPO',argv='python -u observer_r13.py RUN OUTPUT READY STOP')]
    subcalls=[]
    for p in HERE.glob('*.py'):
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='subprocess':
                subcalls.append(dict(file=p.name,line=n.lineno,call=ast.unparse(n)))
    write(HERE/'freeze/R14_R6.json',dict(at=now(),status='FROZEN_BEFORE_NATIVE_WORK',plan_commit='a566252',
        plan_sha256=sha(REPO/r13.R14_PLAN),continuation_STOP_sha256=sha(r13.R5_R/'STOP.json'),
        inherited_scientific_freeze_sha256=sha(HERE/'freeze/R13_R5.json'),
        Q25_Q26_verbatim=read(HERE/'freeze/R13_R5.json')['Q25_Q26_verbatim'],
        direct_runtime_python_child_entries=direct,all_subprocess_calls=subcalls,
        extra_external_CLI_entries_tested=passed['entries'],import_tests='python -I fresh child, REPO and unrelated tempfile cwd, no main, no AEDT import/network/subprocess',
        observer_capture_AST_identical=True,observer_dry_run='real -u script CLI, fake owner=current test process, ready identity, stop, rc0 within20s, empty valid JSONL, no engines',
        cache_source=str(r13.SOURCE),cache_manifest_sha256=sha(HERE/'freeze/CACHE_MANIFEST.json'),
        cache_source_file_count=len(read(HERE/'freeze/CACHE_MANIFEST.json')),R5_clone_not_used=True,
        actual_budget_before=dict(geometries=193,Analyze=1846),remaining=dict(new_geometry_max=4,cache_sweep_Analyze=1,ordinary_Analyze_per_geometry=14),
        unchanged_scientific_rules=True,resources=dict(cores=14,tasks=1,serial=True),
        self_fix_cap=2,self_fixes_used=0,self_fix_scope='only pre-charge/pre-Analyze packaging, fresh reproducer and regression then new patch freeze+push before retry; all other R13 strict failures stop',
        no_hook=True,no_direct_points=True,no_stage7=True))
    print('R14_FREEZE_READY',flush=True)
if __name__=='__main__':freeze()
