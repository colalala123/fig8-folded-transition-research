"""Explicit R10 offline review/publication/finite decisions. No solver API."""
import argparse,hashlib,json,os,subprocess
import numpy as np
from prepare_r10 import *
import tolerance_analysis as ta

def publication(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);dest=root/'publications'/(case+'.json')
    if dest.exists():
        d=read(dest)
        if d['freeze_sha256']!=sha(w/'input/freeze.json') or d['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('existing publication mismatch')
        return d
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/fold-bandwidth-r4-execution'],cwd=REPO,text=True).split()[0]
    if commit!=remote:raise RuntimeError('HEAD not pushed')
    files={**cfg['code_hashes'],**cfg['frozen_hashes'],(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix():sha(w/'input/freeze.json'),(HERE/'freeze/OFFLINE_TESTS.json').relative_to(REPO).as_posix():sha(HERE/'freeze/OFFLINE_TESTS.json')}
    for rel,h in files.items():
        if hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('published blob mismatch '+rel)
    from validation_gate import validation_files
    for rel,h in validation_files(root,case,cfg).items():
        if hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('validation not pushed '+rel)
    d=dict(at=now(),commit=commit,remote_verified=True,authorization_sha256=sha(root/'authorization.json'),freeze_sha256=sha(w/'input/freeze.json'))
    write(dest,d);return d

def ack(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if not read(w/'review/REVIEW_STAGE3.json')['numerical_pass']:raise RuntimeError('numerical failure')
    # Only invoke after tools.view_image has returned the actual plot to model.
    d=dict(at=now(),actually_viewed=True,viewer='tools.view_image; actual S11/S21 inspected',plot_sha256=sha(w/'review/S11_S21.png'),extraction_sha256=sha(w/'review/extraction_R2.json'))
    write(w/'review/visual_ack.json',d);return d

def measurement(w,archive=False):
    q=read(w/'review/extraction_R2.json');y=state(q);a=read(w/'review/visual_ack.json')
    if not a['actually_viewed'] or a['plot_sha256']!=sha(w/'review/S11_S21.png') or a['extraction_sha256']!=sha(w/'review/extraction_R2.json'):raise RuntimeError('real-view ACK mismatch')
    r=read(w/'review/REVIEW_STAGE3.json')
    if not r['numerical_pass']:raise RuntimeError('numerical review failed')
    if y is None:return dict(numerical_review_passed=True,actual_view_ack=True,shape_valid=False)
    b=q['bandwidths']['BW20'];z=np.load(w/'native/full_modes.npz',allow_pickle=False)
    mn=None
    if b.get('BW_GHz') is not None:
        mask=(z['f_GHz']>=b['low_GHz'])&(z['f_GHz']<=b['high_GHz']);mn=float(np.min(20*np.log10(np.maximum(abs(z['S'][mask,2,0]),1e-15))))
    return dict(center_GHz=float(y[0]),low_peak_dB=float(y[2]-y[1]/2),high_peak_dB=float(y[2]+y[1]/2),
        BW20_GHz=b.get('BW_GHz'),S21_min_dB=mn,numerical_review_passed=True,actual_view_ack=True,shape_valid=True,
        BW15_GHz=q['bandwidths']['BW15'].get('BW_GHz'),BW15_star_GHz=(q['bandwidths']['BW15']['BW_GHz']-.125*(y[2]+20.3)) if q['bandwidths']['BW15'].get('BW_GHz') is not None else None)

def baseline(dense=False):return measurement(OLD/'results'/('S5R9_B1dense__T1' if dense else 'S5R9_B1__T2'),True)

def finish(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);fz=read(w/'input/freeze.json');p=fz['parent_id'];n=p.removeprefix('S6R10_');m=measurement(w)
    # Numerical perturbations are observations, not optimization targets.
    passing=True;complete=True;next_i=None
    if n in ('W3','W4','B1R'):
        q=read(w/'review/extraction_R2.json')
        passing=ta.robust_nominal_pass(m,read(HERE/'freeze_6B/R10_2.json')['analysis']['P_req_dB']) if n=='B1R' and m['shape_valid'] else classify(q)['tuned'] if n!='B1R' else False
        last=4 if n=='W3' else 2 if n=='W4' else 3
        if not passing and fz['attempt_ordinal']<last:
            sg=suggestion(root,p,cfg)
            if sg['needs_solve']:complete=False;next_i=fz['attempt_ordinal']+1
    elif n=='B1Rdense':
        from r12 import statistical_pass
        passing=m['shape_valid'] and statistical_pass(m,read(HERE/'freeze_6B/R10_2.json')['analysis'])
    elif n=='C1R':
        bd=read(root/'decisions/S6R10_B1R_FINAL.json');dd=read(root/'decisions/S6R10_B1Rdense_FINAL.json')
        nominal=measurement(case_dir(root,bd['selected_case'],cfg));dense=measurement(case_dir(root,dd['selected_case'],cfg))
        from r12 import confirmation
        conf=confirmation(nominal,dense,m,read(HERE/'freeze_6B/R10_2.json')['analysis']);passing=conf['both_passed']
        write(root/'decisions/ROBUST_CONFIRMATION.json',conf)
    if n=='B1R' and complete and not passing:
        write(root/'STOP.json',dict(at=now(),case=case,reason='R12 B1R finite tuning exhausted or clearance-limited; stop, no additions'))
    if not complete:return dict(complete=False,next_ordinal=next_i,measurement=m)
    d=dict(at=now(),parent_id=p,complete=True,passed=bool(passing),selected_case=case,measurement=m,
        usable_for_law=bool(passing) if n in ('W3','W4') else None,kind=fz['design']['kind'],
        data_role=fz['design']['data_role'],note='Control completion does not mean -20dB or manufacturing pass; see role-specific metrics.')
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):
        dest.parent.mkdir(exist_ok=True);write(dest,d)
    return d

def skip(root,p,reason):
    cfg=read(root/'authorization.json')
    if p not in cfg['parent_order']:raise RuntimeError('unknown parent')
    if any((case_dir(root,c,cfg)/'worker_started.json').exists() for c,s in cfg['case_specs'].items() if s['parent_id']==p):raise RuntimeError('cannot skip dispatched parent')
    allowed=False
    if p in ('S6R10_P1dense','S6R10_P2dense'):allowed=not read(root/'decisions/6A_PRIMARY.json')['conditional_dense_required']
    elif p in ('S6R10_B1R','S6R10_B1Rdense','S6R10_C1R'):
        analysis=read(HERE/'freeze_6B/R10_2.json')['analysis'];allowed=analysis['stage6B_decision']!='try_B1R_max_three'
        if p!='S6R10_B1R' and (root/'decisions/S6R10_B1R_FINAL.json').exists():allowed=allowed or not read(root/'decisions/S6R10_B1R_FINAL.json')['passed']
    elif p=='S6R10_W4':allowed=not read(root/'decisions/S6R10_W3_FINAL.json')['passed'] or not cfg['designs'][p]['screen']['can_submit']
    if not allowed:raise RuntimeError('skip condition not met')
    d=dict(at=now(),parent_id=p,complete=True,passed=False,skipped=True,reason=reason)
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):dest.parent.mkdir(exist_ok=True);write(dest,d)
    return d

def missing(root,logical):
    cfg=read(root/'authorization.json');original=case_dir(root,logical,cfg);retry=case_dir(root,logical+'__NR1',cfg)
    first=read(original/'NUMERICAL_FAILURE.json');second=read(retry/'NUMERICAL_FAILURE.json')
    if not first['same_settings_retry_allowed'] or second['same_settings_retry_allowed']:raise RuntimeError('not two finite numerical failures')
    if read(original/'input/freeze.json')['design']!=read(retry/'input/freeze.json')['design']:raise RuntimeError('retry settings changed')
    p=read(original/'input/freeze.json')['parent_id']
    d=dict(at=now(),parent_id=p,complete=True,missing=True,passed=False,selected_case=None,
        reason='R10 same-settings numerical retry failed; no further retry or altered settings',failure_hashes=[sha(original/'failure.txt'),sha(retry/'failure.txt')])
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):dest.parent.mkdir(exist_ok=True);write(dest,d)
    return d

def measured_case_path(root,case,cfg):
    if case in cfg.get('inherited_public_result_paths',{}):return REPO/cfg['inherited_public_result_paths'][case]
    if case in cfg.get('inherited_case_paths',{}):return Path(cfg['inherited_case_paths'][case])
    return case_dir(root,case,cfg)

def analyze6a(root,primary=False):
    cfg=read(root/'authorization.json');ms={}
    for n in INITIAL+(['P1dense','P2dense'] if not primary else []):
        path=root/'decisions'/('S6R10_'+n+'_FINAL.json')
        if path.exists():
            d=read(path)
            if not d.get('skipped') and not d.get('missing'):ms[n]=measurement(measured_case_path(root,d['selected_case'],cfg))
    b=baseline()
    if primary:
        if set(INITIAL)-set(ms):raise RuntimeError('initial measurements incomplete')
        noise=abs(ta.highest(ms['N0'])-ta.highest(b));out=dict(at=now(),noise_dB=noise,conditional_dense_required=noise>.05,measurements=ms)
        write(root/'decisions/6A_PRIMARY.json',out);return out
    out=ta.stage6a(b,ms);out['measurements']=ms
    if not out['complete']:raise RuntimeError('6A analysis incomplete: '+str(out))
    if out['conditional_dense_required']:
        bd=baseline(True);out['conditional_dense_vs_B1dense']={n:dict(measurement=ms[n],differences={k:ms[n][k]-bd[k] if ms[n].get(k) is not None and bd.get(k) is not None else None for k in ta.RESPONSES}) for n in ('P1dense','P2dense')}
    return out

def status(root):
    cfg=read(root/'authorization.json');g=list((root/'ledger').glob('geometry_*.json'));a=list((root/'ledger').glob('Analyze_*.json'))
    st=dict(at=now(),phase='R12_stage6_R4',R10_geometries=16+len(g),R10_geometry_cap=27,R4_new_geometries=len(g),R4_new_geometry_cap=8,geometry_total=189+len(g),geometry_cap=200,
        R10_actual_Analyze=174+len(a),R4_actual_Analyze=len(a),actual_Analyze_total=1807+len(a),P10_aggregate_Analyze=13,completed_parents=[read(p) for p in sorted((root/'decisions').glob('*_FINAL.json'))],
        stage7_authorized=False,stop=read(root/'STOP.json') if (root/'STOP.json').exists() else None)
    for dest in (root/'CURRENT_STATUS.json',HERE/'CURRENT_STATUS.json'):
        tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,dest)
    lines=['# R10 阶段6状态','',f"阶段6几何 {16+len(g)}/27（R4新增{len(g)}/8）；累计 {189+len(g)}/200（本轮最多197）。",f"阶段6实际 Analyze 请求 {174+len(a)}（R4新增{len(a)}）；累计 {1807+len(a)}。",'14核、一组、串行；不发hook；阶段7未授权。','',('已停止，见 CURRENT_STATUS.json。' if st['stop'] else '每点终态后独立审核和实看图，再显式接续。')]
    (HERE/'CURRENT_STATUS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return st

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['publication','ack','finish','status','skip','primary','analysis','missing']);ap.add_argument('case',nargs='?');ap.add_argument('--reason');a=ap.parse_args()
    print(json.dumps(status(ROOT) if a.command=='status' else skip(ROOT,a.case,a.reason) if a.command=='skip' else analyze6a(ROOT,a.command=='primary') if a.command in ('primary','analysis') else globals()[a.command](ROOT,a.case),ensure_ascii=False))
