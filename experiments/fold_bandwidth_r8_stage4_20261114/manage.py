"""Explicit offline review/real image ACK/next-candidate management; no solver."""
import argparse,subprocess,os
from prepare_r8 import *
def publication(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/fold-bandwidth-r4-execution'],cwd=REPO,text=True).split()[0]
    if commit!=remote:raise RuntimeError('HEAD not pushed')
    import hashlib
    rel=(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix()
    if hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=REPO)).hexdigest()!=sha(w/'input/freeze.json'):raise RuntimeError('published candidate mismatch')
    (root/'publications').mkdir(exist_ok=True)
    write(root/'publications'/(case+'.json'),dict(at=now(),commit=commit,remote_verified=True,authorization_sha256=sha(root/'authorization.json'),freeze_sha256=sha(w/'input/freeze.json')))
    print('PUBLICATION_VERIFIED',case,commit)
def ack(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if not read(w/'review/REVIEW_STAGE3.json')['numerical_pass']:raise RuntimeError('numerical failure')
    write(w/'review/visual_ack.json',dict(at=now(),actually_viewed=True,viewer='tools.view_image; model inspected actual S11/S21',plot_sha256=sha(w/'review/S11_S21.png'),extraction_sha256=sha(w/'review/extraction_R2.json')))
def finish(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id']
    r=read(w/'review/REVIEW_STAGE3.json');a=read(w/'review/visual_ack.json')
    if not r['numerical_pass'] or not a['actually_viewed'] or a['plot_sha256']!=sha(w/'review/S11_S21.png'):raise RuntimeError('missing review')
    hh=histories(root,p,cfg);best=min(hh,key=lambda z:error(state(z['q'])));usable=classify(best['q'])['tuned']
    sg=propose_history(hh,cfg['designs'][p]['nominal_a_mm'],'folded')
    if not usable and f['attempt_ordinal']<3 and sg['needs_solve']:return dict(complete=False,next_ordinal=f['attempt_ordinal']+1)
    d=dict(at=now(),parent_id=p,complete=True,tuned=usable,selected_case=best['case'],attempts=len(hh),
      kind='EQ',reason='R7 usable' if usable else 'clearance/finite tuning not solved; not physical impossibility',stage5_enabled=False)
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):
        dest.parent.mkdir(exist_ok=True);write(dest,d)
    if p==cfg['parent_order'][3] and sum(read(root/'decisions'/(t+'_FINAL.json'))['tuned'] for t in cfg['parent_order'][:4])<2:
        write(root/'STOP.json',dict(at=now(),reason='R8 D1-D4 usable <2',stage5_started=False))
    return d
def status(root):
    cfg=read(root/'authorization.json');g=list((root/'ledger').glob('geometry_*.json'));a=list((root/'ledger').glob('Analyze_*.json'))
    st=dict(at=now(),phase='stage4',R8_geometries=len(g),R8_cap=24,geometry_total=133+len(g),geometry_cap=187,stage4_cumulative_cap=157,
        R8_actual_Analyze=len(a),actual_Analyze_total=1226+len(a),completed_parents=[read(p) for p in sorted((root/'decisions').glob('*_FINAL.json'))],
        stage5_started=False,stop=read(root/'STOP.json') if (root/'STOP.json').exists() else None)
    for dest in (root/'CURRENT_STATUS.json',HERE/'CURRENT_STATUS.json'):
        tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,dest)
    print(json.dumps(st,ensure_ascii=False));return st
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['publication','ack','finish','status']);ap.add_argument('case',nargs='?');a=ap.parse_args()
    if a.command=='status':status(ROOT)
    else:print(globals()[a.command](ROOT,a.case))
