"""阶段3授权/冻结/顺序门槛。导入不连接AEDT。"""
from common_stage2 import *
from solve_block import solve_stage
import subprocess,hashlib
import geometry
from tuning import propose
from history_links import prior_dir,decision_path
def verify_release(root,case):
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists():raise RuntimeError('停止/暂停有效')
    cfg=read(root/'authorization.json')
    if cfg.get('human_authorized') is not True or cfg['batch']!='3' or cfg['limits']!=LIMITS or cfg['batch_geometry_limit']!=42-cfg['stage3_prior_geometry']:
        raise RuntimeError('阶段3授权不符')
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('冻结改变 '+rel)
    for path,h in cfg['historical_hashes'].items():
        if sha(path)!=h:raise RuntimeError('历史证据改变')
    audit0=read(cfg['prior_stage3_audit'])
    if cfg['prior_geometry_total']!=audit0['cumulative_geometries'] or cfg['prior_Analyze_total']!=audit0['cumulative_Analyze']:
        raise RuntimeError('历史实际预算不符')
    if cfg['stage3_prior_geometry']!=audit0['stage3_geometries']:raise RuntimeError('阶段3成本覆盖不符')
    audit=read(cfg['prior_batch_audit'])
    if not audit['passed'] or audit['parents']!=22 or not audit['all_numerical_pass']:raise RuntimeError('2b审计未过')
    proof=read(root/'prediction_publication.json')
    if not proof['remote_verified'] or proof['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('未推送冻结')
    for rel,h in cfg['frozen_hashes'].items():
        if proof['files_sha256'].get(rel)!=h:raise RuntimeError('发布未绑定冻结')
        if hashlib.sha256(subprocess.check_output(['git','show',proof['commit']+':'+rel],cwd=REPO)).hexdigest()!=h:
            raise RuntimeError('已推送提交不含冻结')
    w=case_dir(root,case,cfg);f=read(w/'input/freeze.json')
    if any((w/n).exists() for n in ('worker_started.json','done.json','failure.txt')):raise RuntimeError('已有尝试，不重复')
    if f['resume'] or f['inherited_Analyze']!=0 or f['authorization_sha256']!=sha(root/'authorization.json'):
        raise RuntimeError('输入授权或冷启动不符')
    parent=f['parent_id'];i=f['attempt_ordinal'];pred=f['design'];initial=cfg['designs'][parent]
    if cfg['case_specs'][case]!=dict(parent_id=parent,attempt_ordinal=i):raise RuntimeError('尝试映射不符')
    if not 1<=i<=initial['max_Analyze']:raise RuntimeError('父项预算不符')
    for prev in cfg['parent_order'][:cfg['parent_order'].index(parent)]:
        if not read(decision_path(root,prev,cfg))['complete']:raise RuntimeError('前项未闭合')
    for rel,h in f['source_hashes'].items():
        if sha(REPO/rel)!=h:raise RuntimeError('源哈希变化')
    if initial['kind']=='EQ':
        if i==1:
            if pred!=initial:raise RuntimeError('R3初值改变')
        else:
            base_case=cfg.get('calibration_overrides',{}).get(case,parent+f'__T{i-1}')
            old=prior_dir(root,base_case,cfg)
            qp=old/'review/extraction_R2.json';ack=read(old/'review/visual_ack.json')
            if not ack['actually_viewed'] or ack['plot_sha256']!=sha(old/'review/S11_S21.png') or ack['extraction_sha256']!=sha(qp):
                raise RuntimeError('前次实际看图未核验')
            sug=propose(read(qp),initial['nominal_a_mm'],initial['topology'])
            if not sug['needs_solve'] or sug!=pred.get('tuning') or sug['geometry_mm']!=pred['geometry_mm']:
                raise RuntimeError('不符合冻结有限调参')
            if f['previous_extraction_sha256']!=sha(qp):raise RuntimeError('调参绑定变化')
            allowed={'geometry_mm','prediction','tuning','data_role','screen'}
            if {k:v for k,v in pred.items() if k not in allowed}!={k:v for k,v in initial.items() if k not in allowed}:raise RuntimeError('调参改变了其他冻结字段')
    else:
        if i!=1:raise RuntimeError('对照仅一次')
        binding=read(w/'input/parent_binding.json')
        source=Path(binding['source_input'])
        if sha(source)!=binding['source_input_sha256']:raise RuntimeError('对照父几何来源变化')
        old=read(source)
        geo=old.get('design',{}).get('geometry_mm') or old['geometry_mm']
        if geo!=pred['geometry_mm']:raise RuntimeError('对照父几何不一致')
        if initial['kind']=='BOUNDARY' and (pred['geometry_mm']!=initial['geometry_mm'] or binding['source_input_sha256']!=initial['source_final_input_sha256']):raise RuntimeError('边界父项冻结绑定不符')
        if initial['kind']=='LOSSLESS':
            d=read(decision_path(root,initial['parent'],cfg))
            if not d['tuned'] or d['selected_case']!=binding['selected_case']:raise RuntimeError('无耗对照父项未调准')
        if {k:v for k,v in pred.items() if k not in ('geometry_mm','prediction','screen','expected_boxes')}!={k:v for k,v in initial.items() if k not in ('geometry_mm','prediction','screen','expected_boxes')}:
            raise RuntimeError('对照除绑定最终几何外的配置改变')
    if pred['geometry_mm']['Wm']!=initial['geometry_mm']['Wm'] or pred['topology']!=initial['topology']:raise RuntimeError('Wm或拓扑变化')
    if geometry.slot_boxes(pred['geometry_mm'],pred['topology'])!=f['expected_boxes']:raise RuntimeError('槽盒不符')
    return cfg,f
