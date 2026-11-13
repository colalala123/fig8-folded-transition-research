"""R8 exclusive geometry/API double ledger. No old unused-slot transfers."""
from common_stage2 import *
def charge(root,case,label,record,freeze):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stopped/paused')
    cfg=read(root/'authorization.json');p=freeze['parent_id'];i=record['Analyze_requested']
    if cfg['batch']!='4' or cfg['execution_revision']!='R8_STAGE4' or cfg['batch_geometry_limit']!=24 or cfg['total_geometry_limit']!=187:raise RuntimeError('budget auth')
    if case not in cfg['case_paths'] or p not in cfg['parent_order'] or not 1<=freeze['attempt_ordinal']<=3:raise RuntimeError('unauthorized geometry')
    ledger=root/'ledger';geom=[read(z) for z in ledger.glob('geometry_*.json')]
    if not isinstance(i,int) or isinstance(i,bool) or not 0<=i<14:raise RuntimeError('14 API cap')
    if any(read(z)['stage']=='final_sweep' for z in ledger.glob(f'Analyze_{case}_*.json')):raise RuntimeError('final sweep already requested')
    if label!='final_sweep' and label!=f'adaptive_{i:02d}':raise RuntimeError('unexpected adaptive phase')
    if i==0:
        if label!='adaptive_00':raise RuntimeError('fresh geometry must start at16passes')
        if len(geom)>=24 or 133+len(geom)>=157 or 133+len(geom)>=187:raise RuntimeError('geometry budget exhausted')
        if sum(z['parent_id']==p for z in geom)>=3:raise RuntimeError('parent3geometry cap')
        write(ledger/f'geometry_{case}.json',dict(at=now(),case=case,parent_id=p,batch='4',attempt_ordinal=freeze['attempt_ordinal'],role=freeze['design']['data_role']))
    elif not (ledger/f'geometry_{case}.json').exists():raise RuntimeError('missing prior ledger; no implicit cache retry')
    write(ledger/f'Analyze_{case}_{i:02d}.json',dict(at=now(),case=case,parent_id=p,batch='4',index=i,stage=label,cores=14,tasks=1))
    record['Analyze_requested']+=1
