"""R10 exactly-once physical geometry and actual API accounting."""
from common_stage2 import *

def charge(root,case,label,record,freeze):
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')):raise RuntimeError('stopped/paused')
    cfg=read(root/'authorization.json');logical=freeze['logical_case'];p=freeze['parent_id'];ledger=root/'ledger'
    if (cfg['execution_revision'],cfg['batch_geometry_limit'],cfg['total_geometry_limit'],cfg['prior_geometry_total'])!=('R10_STAGE6_R2',19,200,181):raise RuntimeError('R10 budget mismatch')
    if cfg['case_specs'].get(case)!=dict(parent_id=p,attempt_ordinal=freeze['attempt_ordinal'],numerical_retry=freeze['numerical_retry']) or logical!=p+f"__T{freeze['attempt_ordinal']}":raise RuntimeError('unauthorized physical/technical slot')
    cap=20 if freeze['design'].get('dense_confirmation') else 14
    used=[read(z) for z in ledger.glob('Analyze_*.json') if read(z)['logical_case']==logical]
    i=record['Analyze_requested']
    if len(used)>=cap:raise NumericalStop('R10 per-physical-geometry Analyze cap, including numerical retry')
    if any(read(z)['stage']=='final_sweep' for z in ledger.glob(f'Analyze_{case}_*.json')):raise RuntimeError('duplicate final sweep')
    if label!='final_sweep' and label!=f'adaptive_{i:02d}':raise RuntimeError('unexpected adaptive stage')
    if i==0:
        if label!='adaptive_00':raise RuntimeError('fresh independent solve required')
        path=ledger/f'geometry_{logical}.json'
        if freeze['numerical_retry']:
            if not path.exists():raise RuntimeError('no original charged geometry')
        else:
            if len(list(ledger.glob('geometry_*.json')))>=19:raise RuntimeError('geometry cap')
            write(path,dict(at=now(),case=case,logical_case=logical,parent_id=p,batch='6',attempt_ordinal=freeze['attempt_ordinal']))
    write(ledger/f'Analyze_{case}_{i:02d}.json',dict(at=now(),case=case,logical_case=logical,parent_id=p,batch='6',index=i,stage=label,cores=14,tasks=1,dense_confirmation=cap==20))
    record['Analyze_requested']+=1
