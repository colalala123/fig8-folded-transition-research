"""2b沿用原长度修正规程，只把尝试前预测更新为冻结的2a模型。"""
import importlib.util
from pathlib import Path
import sys,json,hashlib
REPO=Path(__file__).resolve().parents[2]
OLD=REPO/"experiments/fold_bandwidth_r6_stage2_20261111/tuning.py"
spec=importlib.util.spec_from_file_location("stage2a_length_rule_readonly",OLD)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
classify=base.classify
presubmit=base.presubmit
FM_TARGET,FS_TARGET=base.FM_TARGET,base.FS_TARGET
MODELDIR=REPO/"experiments/fold_bandwidth_r6_stage2_model_20261112"
MODEL=MODELDIR/"fit_complete/MODEL.json"

def new_prediction(g,topology):
    sys.path.insert(0,str(MODELDIR))
    from freeze_2b import predict
    return predict(g,topology,json.loads(MODEL.read_text(encoding="utf-8-sig")))

def propose(q,nominal_a,topology="folded"):
    suggestion=base.propose(q,nominal_a,topology)
    if suggestion["needs_solve"]:
        suggestion["prediction"]=new_prediction(suggestion["geometry_mm"],topology)
        suggestion["prediction_basis"]="2a冻结模型；本项为调参数据，不改首次前瞻身份"
    return suggestion
