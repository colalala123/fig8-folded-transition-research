"""R7只授权3R；每一输入必须先发布，旧STOP不可清除。"""
from common_stage2 import *
from solve_block import solve_stage
import subprocess,hashlib
from prepare_r7 import histories,propose_history,selection
import geometry

def verify_release(root,case):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('停止/暂停')
    cfg=read(root/'authorization.json')
    if not cfg['human_authorized'] or cfg['execution_revision']!='R7_3R' or cfg['limits']!=LIMITS or cfg['batch']!='3':raise RuntimeError('R7授权不符')
    if (cfg['prior_geometry_total'],cfg['prior_Analyze_total'],cfg['stage3_prior_geometry'],cfg['R7_new_geometry_cap'])!=(106,961,6,35):raise RuntimeError('预算不符')
    if (cfg['cores'],cfg['tasks'],cfg['serial'],cfg['no_hook'])!=(14,1,True,True):raise RuntimeError('资源设置不符')
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('冻结改变 '+rel)
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('历史证据变化 '+p)
    if not read(HERE/'offline/SENSITIVITY.json')['passed']:raise RuntimeError('R7-1未过')
    w=case_dir(root,case,cfg);f=read(w/'input/freeze.json');p=f['parent_id'];i=f['attempt_ordinal'];s=cfg['designs'][p]
    if any((w/n).exists() for n in ('worker_started.json','done.json','failure.txt')):raise RuntimeError('禁止重复派发')
    if f['resume'] or f['inherited_Analyze'] or f['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('输入授权变化')
    if cfg['case_specs'][case]!=dict(parent_id=p,attempt_ordinal=i) or not 1<=i<=s['max_Analyze']:raise RuntimeError('未授权槽')
    for prev in cfg['parent_order'][:cfg['parent_order'].index(p)]:
        if not read(root/'decisions'/(prev+'_FINAL.json'))['complete']:raise RuntimeError('前项未闭合')
    if cfg['parent_order'].index(p)>=3:
        if sum(read(root/'decisions'/(t+'_FINAL.json'))['tuned'] for t in cfg['parent_order'][:3])<2:raise RuntimeError('前三项少于2可用点，R7停止')
    pred=f['design']
    if s['kind']=='EQ':
        hh=histories(root,p,cfg);sug=propose_history(hh,s['nominal_a_mm'],s['topology'])
        if not sug['needs_solve'] or sug!=pred['tuning'] or sug['geometry_mm']!=pred['geometry_mm']:raise RuntimeError('非冻结R7调参结果')
        if pred['geometry_mm']['Wm']!=s['geometry_mm']['Wm']:raise RuntimeError('Wm变化')
    else:
        sel=selection(root,s['parent'],cfg)
        if sel is None:raise RuntimeError('对照父点不可用')
        selected,g,npz=sel
        if g!=pred['geometry_mm'] or pred['binding']!=dict(selected_case=selected,native_source=str(npz),native_sha256=sha(npz)):raise RuntimeError('对照绑定变化')
    if pred['topology']!=s['topology'] or geometry.slot_boxes(pred['geometry_mm'],pred['topology'])!=f['expected_boxes']:raise RuntimeError('拓扑/槽盒变化')
    pub=root/'publications'/(case+'.json');proof=read(pub)
    files={**cfg['code_hashes'],**cfg['frozen_hashes'],(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix():sha(w/'input/freeze.json')}
    if not proof['remote_verified'] or proof['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('未推送')
    for rel,h in files.items():
        if hashlib.sha256(subprocess.check_output(['git','show',proof['commit']+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('推送提交未绑定 '+rel)
    if sha(HERE/'pre_solve'/(case+'.json'))!=sha(w/'input/freeze.json'):raise RuntimeError('公开输入不一致')
    return cfg,f
