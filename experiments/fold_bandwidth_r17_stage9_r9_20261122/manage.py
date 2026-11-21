"""Explicit R10 offline review/publication/finite decisions. No solver API."""
import argparse,hashlib,json,os,subprocess
import numpy as np
from prepare_r10 import *
import stage8

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
    from validation_gate import validation_files
    from publication_check import verify_blobs
    files.update(validation_files(root,case,cfg));files.update(appendix_files(root,cfg['case_specs'][case]['parent_id'].removeprefix(PREFIX),cfg))
    verify_blobs(commit,files)
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
    return dict(edges20=q.get('R17_edges20') or q.get('R16_edges20') or stage8.edge_from_run(w),center_GHz=float(y[0]),low_peak_dB=float(y[2]-y[1]/2),high_peak_dB=float(y[2]+y[1]/2),
        BW20_GHz=b.get('BW_GHz'),S21_min_dB=mn,numerical_review_passed=True,actual_view_ack=True,shape_valid=True,
        BW15_GHz=q['bandwidths']['BW15'].get('BW_GHz'),BW15_star_GHz=(q['bandwidths']['BW15']['BW_GHz']-.125*(y[2]+20.3)) if q['bandwidths']['BW15'].get('BW_GHz') is not None else None)



def status(root):
    cfg=read(root/'authorization.json');dg=list((root/'ledger').glob('geometry_*.json'));da=list((root/'ledger').glob('Analyze_*.json'))
    st=dict(at=now(),phase='R17_stage9_R9',new_geometries=len(dg),new_geometry_cap=15,geometry_total=206+len(dg),geometry_cap=221,new_Analyze=len(da),actual_Analyze_total=1984+len(da),completed_parents=[read(p) for p in sorted((root/'decisions').glob('*_FINAL.json'))],stop=read(root/'STOP.json') if (root/'STOP.json').exists() else None,no_further_stage_authorized=True)
    for dest in [root/'CURRENT_STATUS.json',HERE/'CURRENT_STATUS.json']:
        tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,dest)
    (HERE/'CURRENT_STATUS.md').write_text(f"# R17 阶段9\n\n新增{len(dg)}/15几何，累计{st['geometry_total']}/221；新增{len(da)}/216 Analyze，累计{st['actual_Analyze_total']}。终态父项{len(st['completed_parents'])}/9（含条件跳过）。\n",encoding='utf-8')
    return st
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['ack','publication','finish','status','missing','skip']);ap.add_argument('case',nargs='?');a=ap.parse_args()
    if a.command in ('missing','finish','skip'):
        from prepare_r10 import decision
        result=decision(ROOT,a.case,a.command)
    else:result=status(ROOT) if a.command=='status' else globals()[a.command](ROOT,a.case)
    print(json.dumps(result,ensure_ascii=False))
