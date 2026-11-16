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


def finish(root,case):
    import stage7
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id']
    if (root/'STOP.json').exists():raise RuntimeError('strict STOP')
    m=measurement(w);q=read(w/'review/extraction_R2.json');req=read(HERE/'freeze/R15_R7.json')['margin']['P_req_dB']
    check=stage7.nominal_check(q,req,m.get('S21_min_dB'));passing=check['tuned'] if p=='S7R15_W4R' else None
    if p=='S7R15_W4R' and not passing and f['attempt_ordinal']<4:
        sg=suggestion(root,p,cfg)
        if sg['needs_solve']:return dict(complete=False,next_ordinal=f['attempt_ordinal']+1,measurement=m,nominal_check=check)
    selected=case
    if p=='S7R15_W4R' and not passing:
        hs=[r for r in histories(root,p,cfg) if r['case'].startswith('S7R15_') and state(r['q']) is not None]
        if hs:selected=min(hs,key=lambda r:stage7.nominal_check(r['q'],req)['error_e'])['case']
        m=measurement(case_dir(root,selected,cfg))
    d=dict(at=now(),parent_id=p,complete=True,passed=passing,selected_case=selected,measurement=m,
        nominal_check=check if selected==case else stage7.nominal_check(read(case_dir(root,selected,cfg)/'review/extraction_R2.json'),req,m.get('S21_min_dB')),
        numerical_valid=True,independent_next_step_allowed=True,note='Control completion is not a robustness pass; C1W is labeled only after dense result or declared missing.')
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):write(dest,d)
    return d

def missing(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);r=read(w/'RUN_RECORD.json');p=cfg['case_specs'][case]['parent_id']
    if (root/'STOP.json').exists() or r['numerical_pass'] is not False or not (w/'NUMERICAL_MISSING.json').exists():raise RuntimeError('not independent numerical missing')
    selected=None;measurement_value=None
    if p=='S7R15_W4R':
        import stage7
        req=read(HERE/'freeze/R15_R7.json')['margin']['P_req_dB'];hs=[r for r in histories(root,p,cfg) if r['case'].startswith('S7R15_') and state(r['q']) is not None]
        selected=min(hs,key=lambda r:stage7.nominal_check(r['q'],req)['error_e'])['case'] if hs else 'S7R15_W4R__T1'
        if hs:measurement_value=measurement(case_dir(root,selected,cfg))
    d=dict(at=now(),parent_id=p,complete=True,passed=False,missing=True,selected_case=selected,measurement=measurement_value,reason='R15 numerical missing; no retry, next independent step allowed. If no valid nominal solve, controls use frozen T1 geometry without claiming nominal metrics.')
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):write(dest,d)
    return d

def status(root):
    cfg=read(root/'authorization.json');g=list((root/'ledger').glob('geometry_*.json'));a=list((root/'ledger').glob('Analyze_*.json'))
    st=dict(at=now(),phase='R15_stage7_R7',new_geometries=len(g),new_geometry_cap=6,geometry_total=196+len(g),geometry_cap=202,new_Analyze=len(a),actual_Analyze_total=1880+len(a),completed_parents=[read(p) for p in sorted((root/'decisions').glob('*_FINAL.json'))],stop=read(root/'STOP.json') if (root/'STOP.json').exists() else None,stage8_authorized=False)
    for dest in (root/'CURRENT_STATUS.json',HERE/'CURRENT_STATUS.json'):
        tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,dest)
    (HERE/'CURRENT_STATUS.md').write_text(f"# R15 阶段7状态\n\n新增{len(g)}/6几何，累计{196+len(g)}/202。新增{len(a)} Analyze，累计{1880+len(a)}。\n14核1组串行；各步数值缺失独立处理，完整性问题严格停止。\n",encoding='utf-8')
    return st
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['publication','ack','finish','status','missing']);ap.add_argument('case',nargs='?');a=ap.parse_args()
    print(json.dumps(status(ROOT) if a.command=='status' else globals()[a.command](ROOT,a.case),ensure_ascii=False))
