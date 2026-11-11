"""R6 公共函数；导入不连接 AEDT。"""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
R4=REPO/'experiments/fold_bandwidth_r4_20261110'
sys.path.insert(0,str(R4))
from headless_worker_r5 import read,write,sha,now,serial_lock,native_boxes,saved_setting,is_wave_port,DESIGN,SETUP
from staged_mesh_r5 import history,next_stage,check_transition,NumericalStop
LIMITS={'1a':5,'1b':9,'2a':45,'2b':66,'3':42,'4':8,'5':12}
BASES=('S1_BASE_N04','S1_BASE_N14','S1_BASE_N08')
STEPS=tuple(f'S1_WS_{i:02d}' for i in range(9))
