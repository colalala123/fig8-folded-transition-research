"""R7离线接续管理。launch只由专用控制器执行；ACK必须实际看图后写。"""
import argparse,subprocess
from prepare_r7 import *

def publication(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/fold-bandwidth-r4-execution'],cwd=REPO,text=True).split()[0]
    if commit!=remote:raise RuntimeError('HEAD未推送远程')
    rel=(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix()
    import hashlib
    if hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=REPO)).hexdigest()!=sha(w/'input/freeze.json'):raise RuntimeError('公开候选不一致')
    d=root/'publications';d.mkdir(exist_ok=True)
    write(d/(case+'.json'),dict(at=now(),commit=commit,remote_verified=True,authorization_sha256=sha(root/'authorization.json'),freeze_sha256=sha(w/'input/freeze.json')))
    print('PUBLICATION_VERIFIED',case,commit)

def ack(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if not read(w/'review/REVIEW_STAGE3.json')['numerical_pass']:raise RuntimeError('数值失败')
    write(w/'review/visual_ack.json',dict(at=now(),actually_viewed=True,viewer='tools.view_image; model inspected actual S11/S21 plot',
         plot_sha256=sha(w/'review/S11_S21.png'),extraction_sha256=sha(w/'review/extraction_R2.json')))

def finish(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id'];s=cfg['designs'][p]
    r=read(w/'review/REVIEW_STAGE3.json');a=read(w/'review/visual_ack.json')
    if not r['numerical_pass'] or not a['actually_viewed'] or a['plot_sha256']!=sha(w/'review/S11_S21.png') or a['extraction_sha256']!=sha(w/'review/extraction_R2.json'):raise RuntimeError('审核缺失')
    h=histories(root,p,cfg) if s['kind']=='EQ' else []
    if h:
        best=min(h,key=lambda z:error(state(z['q'])));usable=classify(best['q'])['tuned']
        sug=propose_history(h,s['nominal_a_mm'],s['topology'])
        if not usable and f['attempt_ordinal']<s['max_Analyze'] and sug['needs_solve']:
            return dict(complete=False,next_ordinal=f['attempt_ordinal']+1)
        selected=best['case'];status='可用' if usable else '净距受限' if not sug['needs_solve'] else '未调准'
    else:selected=case;usable=None;status='对照完成'
    d=dict(at=now(),parent_id=p,complete=True,tuned=usable,selected_case=selected,kind=s['kind'],reason=status,stage4_enabled=False)
    write(root/'decisions'/(p+'_FINAL.json'),d)
    (HERE/'decisions').mkdir(exist_ok=True);write(HERE/'decisions'/(p+'_FINAL.json'),d)
    if p==cfg['parent_order'][2] and sum(read(root/'decisions'/(x+'_FINAL.json'))['tuned'] for x in cfg['parent_order'][:3])<2:
        write(root/'STOP.json',dict(at=now(),reason='R7前三设计可用少于2',stage4_started=False))
    return d

def status(root):
    cfg=read(root/'authorization.json');gg=list((root/'ledger').glob('geometry_*.json'));aa=list((root/'ledger').glob('Analyze_*.json'))
    st=dict(at=now(),R7_geometries=len(gg),stage3_geometries=6+len(gg),geometry_total=106+len(gg),geometry_cap=187,
        R7_actual_Analyze=len(aa),actual_Analyze_total=961+len(aa),stage3_cap=42,R7_cap=35,
        completed_parents=[read(p) for p in sorted((root/'decisions').glob('*_FINAL.json'))],
        stage4_started=False,stage5_started=False,stop=read(root/'STOP.json') if (root/'STOP.json').exists() else None)
    # Mutable status is expressly not a frozen input, use atomic replacement.
    import os
    for dest in (root/'CURRENT_STATUS.json',HERE/'CURRENT_STATUS.json'):
        tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,dest)
    print(json.dumps(st,ensure_ascii=False))
    return st

def skip_control(root,p):
    cfg=read(root/'authorization.json');s=cfg['designs'][p]
    if s['kind']=='EQ' or selection(root,s['parent'],cfg) is not None:raise RuntimeError('不可跳过')
    d=dict(at=now(),parent_id=p,complete=True,tuned=None,kind=s['kind'],skipped=True,reason='该a没有可用父点，不替换其他a')
    write(root/'decisions'/(p+'_FINAL.json'),d);(HERE/'decisions').mkdir(exist_ok=True);write(HERE/'decisions'/(p+'_FINAL.json'),d)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['publication','ack','finish','status','skip']);p.add_argument('case',nargs='?');a=p.parse_args()
    if a.command=='publication':publication(ROOT,a.case)
    elif a.command=='ack':ack(ROOT,a.case)
    elif a.command=='finish':print(finish(ROOT,a.case))
    elif a.command=='skip':skip_control(ROOT,a.case)
    else:status(ROOT)
