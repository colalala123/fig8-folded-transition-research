"""Close only an already terminal R17. Never calls an Ansys API or dispatches anything."""
import sys, json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import psutil
from common_stage2 import HERE,REPO,read,sha,write,now,case_dir
from stage9 import ROOT as RT,ORD,PREFIX
from prepare_r10 import dec
from freeze_r17 import source
from fingerprint import lookup,identity
from manage import status,measurement
from validation_gate import verify_one
from publication_check import verify_blobs
def audit():
    source();cfg=read(RT/'authorization.json')
    if (RT/'PAUSE.json').exists() or (RT/'STOP.json').exists():raise RuntimeError('runtime already stopped/paused')
    d={n:dec(RT,n) for n in ORD};assert all(x['complete'] for x in d.values())
    for mapping,base in [('historical_hashes',None),('code_hashes',REPO),('frozen_hashes',REPO),('plan_hashes',REPO)]:
        for k,v in cfg[mapping].items():
            if sha((base/k) if base else k)!=v:raise RuntimeError('hash '+k)
    gathered={};ledger=RT/'ledger';allg=list(ledger.glob('geometry_*.json'));alla=list(ledger.glob('Analyze_*.json'));rows=read(HERE/'freeze/COMPLETED_INPUT_INDEX.json')['rows'].copy()
    claimed=set();ranges=[];used={}
    for c,sp in cfg['case_specs'].items():
        w=case_dir(RT,c,cfg)
        if not w.exists():continue
        assert (w/'worker_started.json').is_file() and (w/'launcher_claim.json').is_file()
        f=read(w/'input/freeze.json');sig=lookup(f['design'],rows);assert sig['allowed'] and sig==f['fingerprint']
        rows.append(dict(case=c,signature=sig['signature']));pub=read(RT/'publications'/(c+'.json'))
        verify_one(RT,c,cfg);check=dict(verify_one(RT,c,cfg));check[(HERE/'pre_solve'/(c+'.json')).relative_to(REPO).as_posix()]=sha(w/'input/freeze.json')
        verify_blobs(pub['commit'],check)
        rr=read(w/'RUN_RECORD.json');g=ledger/('geometry_'+c+'.json');ar=sorted(ledger.glob('Analyze_'+c+'_*.json'))
        assert g.is_file() and len(ar)==rr['Analyze_requested']<= (20 if f['design']['dense_confirmation'] else 14)
        assert rr['cleanup']['released'] and rr['cleanup']['scratch_restored']
        actual=read(w/'evidence/actual_start_observed.json');assert actual['actual_14core_1group'] and actual['observation']['verified_owned_ancestry']
        if (w/'done.json').exists():
            measurement(w);r=read(w/'review/REVIEW_STAGE3.json');assert r['numerical_pass'] and r['final_sweep_history_unchanged'] and len(r['role_checks'])==len(ar)
        else:assert (w/'NUMERICAL_MISSING.json').exists()
        p=HERE/'results'/c
        for k,v in read(p/'MANIFEST.json').items():assert sha(p/k)==v,(c,k)
        ranges.append([read(w/'worker_started.json')['at'],rr['finished_at'],c])
        used[c]=len(ar);gathered[c]=dict(publication=pub['commit'],signature=sig['signature'],actual_14core=True,Analyze=len(ar),mesh=rr.get('mesh_cells'),delta_s=rr.get('delta_s'),numerical_pass=rr['numerical_pass'])
    ranges.sort();assert all(a[1]<=b[0] for a,b in zip(ranges,ranges[1:]))
    assert len(used)==len(allg)<=15 and len(alla)==sum(used.values())<=216 and all(read(g)['case'] in used for g in allg)
    assert not [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe')]
    return dict(passed=True,at=now(),historical_hashes_checked=len(cfg['historical_hashes']),code_hashes_checked=len(cfg['code_hashes']),frozen_hashes_checked=len(cfg['frozen_hashes']),native_engines_at_close=[],serial_no_overlap=True,worker_spans=ranges,points=gathered,per_case_new_Analyze=used,new_geometries=len(used),new_Analyze=len(alla),prior_geometries=206,prior_Analyze=1984,cumulative_geometries=206+len(used),cumulative_Analyze=1984+len(alla),unissued_slots=[c for c in cfg['case_specs'] if c not in used],posttests=True)
def close():
    f=HERE/'final';assert (f/'REPORT.md').is_file() and (f/'RESULTS.json').is_file() and read(f/'OFFLINE_TESTS.json')['passed'] and read(f/'ENTRY_TESTS.json')['passed']
    a=audit();write(f/'FINAL_AUDIT.json',a)
    c=dict(at=now(),normal_completion=True,stop_after_stage=9,further_stage_authorized=False,geometry_cap=221,self_fixes=[],**{k:a[k] for k in ('prior_geometries','prior_Analyze','new_geometries','new_Analyze','cumulative_geometries','cumulative_Analyze','per_case_new_Analyze','unissued_slots')})
    for p in [f/'CLOSURE.json',RT/'COMPLETED.json',RT/'STOP.json']:write(p,c)
    status(RT)
if __name__=='__main__':close()
