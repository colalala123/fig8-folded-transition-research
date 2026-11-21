"""Fresh-interpreter entry import and real observer CLI dry-run; no AEDT."""
import argparse,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
import psutil
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ENTRIES=['worker_stage2.py','observer_r13.py','controller_stage2.py','preflight_r11.py',
         'prepare_r10.py','stage8.py','review_stage3.py','manage.py','collect_stage2.py','freeze_r16.py','publication_check.py','decide_r16.py']
IMPORT_CODE="""import importlib.util,json,pathlib,sys
p=pathlib.Path(sys.argv[1]).resolve()
# Explicit script directory emulates script-local imports, not cwd/PYTHONPATH.
sys.path.insert(0,str(p.parent))
def guard(event,args):
    if event in ('socket.connect','subprocess.Popen'):raise RuntimeError('entry import attempted native/network dispatch')
sys.addaudithook(guard)
s=importlib.util.spec_from_file_location('_r14_import_probe',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
assert 'ansys.aedt.core' not in sys.modules,'native application import is forbidden in entry test'
print(json.dumps(dict(imported=p.name,main_executed=False,isolated=bool(sys.flags.isolated))))
"""
def engines():
    return [dict(pid=p.pid,name=p.info['name']) for p in psutil.process_iter(['name'])
            if (p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe')]
def dryrun(folder,cwd):
    assert not engines(),'native process present before test'
    with tempfile.TemporaryDirectory(prefix='r14_observer_') as t:
        w=Path(t);(w/'tmp').mkdir();(w/'evidence').mkdir()
        me=psutil.Process();(w/'owner.json').write_text(json.dumps(dict(pid=me.pid,create_time=me.create_time())),encoding='utf-8')
        out=w/'evidence/empty_solver.jsonl';ready=w/'evidence/observer.ready';stop=w/'evidence/observer.stop'
        cmd=[sys.executable,'-u',str(folder/'observer_r13.py'),str(w),str(out),str(ready),str(stop)]
        env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONIOENCODING']='utf-8'
        with (w/'observer.log').open('w',encoding='utf-8') as log:
            p=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+15;observed=[]
            while not ready.exists() and p.poll() is None and time.monotonic()<deadline:
                observed+=engines();time.sleep(.05)
            r=json.loads(ready.read_text(encoding='utf-8')) if ready.exists() else None
            # Windows venv python.exe may be a launcher parent of the real interpreter.
            actual=psutil.Process(r['pid']) if r else None
            ancestors=[x.pid for x in actual.parents()] if actual else []
            ready_identity=bool(r and (r['pid']==p.pid or p.pid in ancestors) and abs(r['create_time']-actual.create_time())<.01
                                and str(folder/'observer_r13.py') in actual.cmdline())
            start=time.monotonic();stop.touch()
            try:rc=p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                # Test child only; never kills an application or unrelated process.
                p.terminate();p.wait(timeout=10);rc='timeout'
            elapsed=time.monotonic()-start
        observed+=engines()
        lines=out.read_text(encoding='utf-8').splitlines() if out.exists() else None
        parsed=[json.loads(s) for s in lines] if lines is not None else None
        d=dict(returncode=rc,ready=r,launcher_pid=p.pid,ready_ancestor_pids=ancestors,ready_identity=ready_identity,stop_exit_seconds=elapsed,
               output_exists=out.exists(),jsonl_records=parsed,native_processes_seen=observed,
               log=(w/'observer.log').read_text(encoding='utf-8'),main_ran=True,real_command=cmd,
               cwd=str(cwd),passed=rc==0 and ready_identity and elapsed<=20 and parsed==[] and not observed)
        return d
def run(folder):
    folder=folder.resolve();assert not engines(),'native processes active, do not test'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONIOENCODING']='utf-8'
    records=[]
    with tempfile.TemporaryDirectory(prefix='r14_unrelated_cwd_') as t:
        for script in ENTRIES:
            for cwd in (REPO,Path(t)):
                p=subprocess.run([sys.executable,'-I','-c',IMPORT_CODE,str(folder/script)],cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
                records.append(dict(script=script,cwd=str(cwd),isolated=True,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
        dry=[dryrun(folder,cwd) for cwd in (REPO,Path(t))]
    assert not engines(),'native processes appeared during offline entry tests'
    return dict(folder=str(folder),entries=ENTRIES,imports=records,observer_dry_runs=dry,
        passed=all(x['returncode']==0 for x in records) and all(x['passed'] for x in dry))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--expect-old-failure',action='store_true');a=ap.parse_args()
    result=run(a.folder)
    if a.expect_old_failure:
        failed=[x for x in result['imports'] if x['returncode']]
        result['expected_failure_reproduced']=(len(failed)==2 and all(x['script']=='observer_r13.py' and "No module named 'common_r6'" in x['stderr'] for x in failed) and all(not x['passed'] and "No module named 'common_r6'" in x['log'] for x in result['observer_dry_runs']))
        success=result['expected_failure_reproduced']
    else:success=result['passed']
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(folder=str(a.folder),passed=result['passed'],expected_failure=result.get('expected_failure_reproduced'),failed_imports=[x['script'] for x in result['imports'] if x['returncode']],dry_run_passes=[x['passed'] for x in result['observer_dry_runs']]),ensure_ascii=False))
    sys.exit(0 if success else 1)
