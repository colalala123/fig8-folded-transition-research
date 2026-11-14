"""R9 exactly-once per geometry/API accounting, including one dense confirmation."""
from common_stage2 import *
def charge(root,case,label,record,freeze):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stopped/paused')
    cfg=read(root/'authorization.json');p=freeze['parent_id'];i=record['Analyze_requested'];dense=freeze['design'].get('dense_confirmation',False)
    if cfg['batch']!='5' or cfg['execution_revision']!='R9_STAGE5' or cfg['batch_geometry_limit']!=26 or cfg['total_geometry_limit']!=187:raise RuntimeError('budget auth')
    if cfg['case_specs'].get(case)!=dict(parent_id=p,attempt_ordinal=freeze['attempt_ordinal']):raise RuntimeError('unauthorized slot')
    cap=20 if dense else 14
    if not isinstance(i,int) or isinstance(i,bool) or not 0<=i<cap:raise RuntimeError('API cap')
    ledger=root/'ledger';geom=[read(z) for z in ledger.glob('geometry_*.json')]
    if any(read(z)['stage']=='final_sweep' for z in ledger.glob(f'Analyze_{case}_*.json')):raise RuntimeError('final sweep already requested')
    if label!='final_sweep' and label!=f'adaptive_{i:02d}':raise RuntimeError('unexpected phase')
    if i==0:
        if label!='adaptive_00':raise RuntimeError('must start fresh')
        subcap=16 if p in cfg['parent_order'][:6] else 10
        subset=cfg['parent_order'][:6] if subcap==16 else cfg['parent_order'][6:]
        if len(geom)>=26 or 151+len(geom)>=177 or sum(z['parent_id'] in subset for z in geom)>=subcap:raise RuntimeError('geometry budget')
        pc=1 if dense else 2 if p.endswith(('D1c','D3c')) else 3
        if sum(z['parent_id']==p for z in geom)>=pc:raise RuntimeError('parent cap')
        write(ledger/f'geometry_{case}.json',dict(at=now(),case=case,parent_id=p,batch='5',attempt_ordinal=freeze['attempt_ordinal'],role=freeze['design']['data_role']))
    elif not (ledger/f'geometry_{case}.json').exists():raise RuntimeError('missing ledger')
    write(ledger/f'Analyze_{case}_{i:02d}.json',dict(at=now(),case=case,parent_id=p,batch='5',index=i,stage=label,cores=14,tasks=1,dense_confirmation=dense))
    record['Analyze_requested']+=1
