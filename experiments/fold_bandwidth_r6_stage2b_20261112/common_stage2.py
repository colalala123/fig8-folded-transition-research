"""阶段2共用的纯路径和记录函数；导入不连接AEDT。"""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
R6=REPO/'experiments/fold_bandwidth_r6_20261111'
R4=REPO/'experiments/fold_bandwidth_r4_20261110'
R2=REPO/'experiments/fold_bandwidth_r2_20261110'
for p in (R4,R6,R2):sys.path.insert(0,str(p))
from common_r6 import read,write,sha,now,serial_lock,native_boxes,saved_setting,is_wave_port,DESIGN,SETUP
from staged_mesh_r5 import history,next_stage,check_transition,NumericalStop
LIMITS={'1a':5,'1b':9,'2a':45,'2b':66,'3':42,'4':8,'5':12}

def case_dir(root,case,cfg):
    if case not in cfg['case_paths']:raise ValueError('未登记的案例')
    p=(root/cfg['case_paths'][case]).resolve()
    p.relative_to(root.resolve())
    return p
