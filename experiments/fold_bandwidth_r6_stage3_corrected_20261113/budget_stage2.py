"""独占持久化双账本；实际请求计数不冒充几何次数。"""
from common_stage2 import *

def charge(root,case,label,record,freeze):
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists():
        raise RuntimeError('本批停止或用户暂停，不提交新的Analyze')
    cfg=read(root/'authorization.json')
    if cfg['batch']!='3' or cfg['limits']!=LIMITS or sum(cfg['limits'].values())!=187:
        raise RuntimeError('预算授权不符')
    if case not in cfg['case_paths']:raise RuntimeError('未授权的尝试槽')
    parent=freeze['parent_id']
    if parent not in cfg['parent_order'] or not 1<=freeze['attempt_ordinal']<=cfg['designs'][parent]['max_Analyze']:
        raise RuntimeError('设计或尝试序号不符')
    ledger=root/'ledger'
    geom=[read(p) for p in ledger.glob('geometry_*.json')]
    i=record['Analyze_requested']
    # 所有可预先判定的拒绝必须先于任何记账写入。
    if not isinstance(i,int) or isinstance(i,bool) or not 0<=i<14:
        raise RuntimeError('单几何14次实际请求上限')
    if any(read(p)['stage']=='final_sweep' for p in ledger.glob(f'Analyze_{case}_*.json')):
        raise RuntimeError('最终扫频已请求，不自动重复')
    if label!='final_sweep' and label not in {f'adaptive_{j:02d}' for j in range(13)}:
        raise RuntimeError('未授权的求解阶段')
    if i==0 and label!='adaptive_00':raise RuntimeError('冷启动必须从16轮开始')
    if label.startswith('adaptive_') and label!=f'adaptive_{i:02d}':
        raise RuntimeError('自适应阶段与请求序号不符')
    if i==0:
        if cfg['prior_geometry_total']+len(geom)>=187:raise RuntimeError('总几何预算耗尽')
        if cfg['stage3_prior_geometry']+len(geom)>=42:raise RuntimeError('阶段3几何预算耗尽')
        if cfg['prior_parent_geometry'].get(parent,0)+sum(x['parent_id']==parent for x in geom)>=cfg['designs'][parent]['max_Analyze']:raise RuntimeError('该设计三次几何预算耗尽')
        write(ledger/f'geometry_{case}.json',dict(at=now(),case=case,parent_id=parent,batch='3',
            attempt_ordinal=freeze['attempt_ordinal'],role=freeze['design']['data_role']))
    elif not (ledger/f'geometry_{case}.json').exists():
        raise RuntimeError('找不到本几何已计费记录；缓存恢复需另行审核')
    write(ledger/f'Analyze_{case}_{i:02d}.json',dict(at=now(),case=case,parent_id=parent,batch='3',
        index=i,stage=label,cores=14,tasks=1))
    record['Analyze_requested']+=1
