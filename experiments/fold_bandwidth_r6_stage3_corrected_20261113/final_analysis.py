"""阶段3最终离线指标与硬门槛；不得用未调准/未完成对照填数量。"""
import argparse
import numpy as np
from common_stage2 import *
from history_links import prior_dir,decision_path
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r3_20261110'))
from stage3_metrics import evaluate
def analyze(root):
    cfg=read(root/'authorization.json')
    if (root/'STOP.json').exists():raise RuntimeError('批次有停止记录，先诊断')
    finals=[];pairs={'N04':0,'N14':0};missing=[]
    for parent in cfg['parent_order']:
        row=cfg['designs'][parent]
        if row['kind']!='EQ':continue
        d=read(decision_path(root,parent,cfg));w=prior_dir(root,d['selected_case'],cfg)
        q=read(w/'review/extraction_R2.json')
        finals.append(dict(design_id=parent,family=row['family'],extraction=q,decision=d))
    metrics=[]
    for r in finals:
        m=evaluate(r['extraction'],r['family'],finals)
        ll=r['design_id']+'_LOSSLESS';path=root/'decisions'/(ll+'_FINAL.json')
        has=path.exists() and not read(path).get('skipped',False)
        if m['tuned'] and has:
            dc=read(path);w=prior_dir(root,dc['selected_case'],cfg)
            rr=read(w/'review/REVIEW_STAGE3.json')
            if rr['numerical_pass'] and read(w/'review/visual_ack.json')['actually_viewed']:pairs[r['family']]+=1
            else:has=False
        if m['tuned'] and not has:missing.append(ll)
        metrics.append(dict(design_id=r['design_id'],**m,has_lossless=has))
    gate=all(n>=4 for n in pairs.values()) and not missing
    out=HERE/'final';out.mkdir(exist_ok=False)
    write(out/'METRICS.json',metrics)
    write(out/'GATE_TO_STAGE4.json',dict(passed=gate,pairs=pairs,missing=missing,new_Analyze=0,
        power_s_probe_is_not_power_certificate=True,physical_radiation_claim_pending=True))
    return dict(passed=gate,pairs=pairs,missing=missing)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();print(analyze(a.root))
