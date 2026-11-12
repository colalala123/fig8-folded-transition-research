"""只读引用已结项旧目录；白名单与哈希来自修正版授权，不把旧路径当派发目标。"""
from common_stage2 import *
def prior_dir(root,case,cfg):
    if case in cfg['case_paths']:
        p=case_dir(root,case,cfg)
        if (p/'review/extraction_R2.json').exists():return p
    entry=cfg['prior_cases'][case]
    p=Path(entry['path']).resolve()
    if sha(p/'input/freeze.json')!=entry['input_sha256']:raise RuntimeError('旧输入改变')
    return p
def decision_path(root,parent,cfg):
    p=root/'decisions'/(parent+'_FINAL.json')
    if p.exists():return p
    entry=cfg['prior_decisions'][parent]
    p=Path(entry['path'])
    if sha(p)!=entry['sha256']:raise RuntimeError('旧结项改变')
    return p
