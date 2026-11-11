"""只生成22项离线前瞻冻结。此脚本不允许启动/连接HFSS。"""
import argparse,copy,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import fit_model as m
from presubmit import presubmit
from lib import assess,TARGET
import geometry
REGISTRY=m.REPO/"experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json"

def predict(geo,topology,model):
    p=m.forward(geo,topology,model)
    f=np.arange(1,1501)/100
    s11,s21=m.chain.circuit(f,*(p[k] for k in ("zm_eff","zs_eff","fm_GHz","fs_GHz")))
    shape=assess(f,np.column_stack([s11,s21]),TARGET)
    bands=m.chain.bands(f,s11,s21,shape=shape)
    return dict(parameters=p,lossless_circuit_bandwidths=bands,lossless_circuit_shape=shape,
        equal_frequency_inner_peak_dB=m.chain.ripple_db(p["P_eff"]) if p["P_eff"]>1 else None,
        BW_S21_HFSS_prediction_GHz=None,
        caveat="单家族模型向新宽度外推；理想电路S21不是含损耗HFSS预测；直槽尺度未经调准对照验证。")

def prepare_rows(registry,model):
    rows=[copy.deepcopy(r) for r in registry["designs"] if r["batch"]=="2b"]
    if len(rows)!=22 or {r["family"] for r in rows}!={"N04","N08"}:
        raise ValueError("必须是原22项跨家族登记")
    for r in rows:
        if not presubmit(r["geometry_mm"],r["screen"]["a_mm"],topology=r["topology"])["can_submit"]:
            raise ValueError("原登记几何不通过筛选："+r["id"])
        r["prior_R1_prediction"]=copy.deepcopy(r["prediction"])
        r["prediction"]=predict(r["geometry_mm"],r["topology"],model)
        r["prior_R1_data_role"]=r["data_role"]
        r["data_role"]="prospective_test"
        r["control_type"]="straight_control" if r["topology"]=="straight_control" else "folded"
        r["first_attempt_role"]="prospective_test";r["first_attempt_role_immutable"]=True
        r["subsequent_attempt_role"]="tuned_data"
        r["initial_prediction_stage"]="post_2a_model_frozen_before_2b"
        r["validity"]="unvalidated_cross_family_prospective_prediction"
        r["release_status"]="prediction_only_not_native_release"
        r["solver_authorized"]=False
        r["future_prospective_freeze_required"]=False
        r["blocking_reasons"]=["push_before_first_Analyze","batch2b_budget_and_native_CAD_resource_preflight"]
        r["source_geometry_unchanged"]=True
        r["expected_boxes"]=geometry.slot_boxes(r["geometry_mm"],r["topology"])
    source={r["id"]:r for r in registry["designs"] if r["batch"]=="2b"}
    for r in rows:
        if r["geometry_mm"]!=source[r["id"]]["geometry_mm"] or r["topology"]!=source[r["id"]]["topology"]:
            raise AssertionError("前瞻冻结改变了原几何/拓扑")
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument("model_dir",type=Path);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
    model=read(a.model_dir/"MODEL.json");snapshot=read(a.model_dir/"SNAPSHOT.json")
    if not snapshot["summary"]["count_conditions_met"]:raise ValueError("2a数量/结项门槛未过")
    rows=prepare_rows(read(REGISTRY),model)
    out=dict(at=datetime.now(timezone.utc).isoformat(),batch="2b",prospective_count=22,
        model_sha256=m.sha(a.model_dir/"MODEL.json"),stage2a_snapshot_sha256=m.sha(a.model_dir/"SNAPSHOT.json"),
        original_R1_registry_sha256=m.sha(REGISTRY),designs=rows,
        geometry_changes=0,new_Analyze_requests=0,hook_messages=0,solver_started=False,
        caveats=["E0未调准，A为弯折数据外推尺度；不是测得的直槽标定",
                 "单家族拟合误差及所有未满足标准均保留，首次前瞻身份永久不改",
                 "旧冻结未覆盖；必须先提交推送，再做独立本机启动核查"])
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/"PREDICTIONS_22.json").write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    src=[Path(__file__),Path(__file__).with_name("fit_model.py"),Path(__file__).with_name("METHODS.md"),
        m.REPO/"experiments/fold_bandwidth_r6_stage2_analysis_20261111/gate_v2.py",
        m.REPO/"experiments/fold_bandwidth_r2_20261110/chain.py",
        m.REPO/"experiments/fold_bandwidth_r2_20261110/presubmit.py",
        m.REPO/"experiments/fold_bandwidth_r2_20261110/geometry.py",
        m.REPO/"experiments/fold_bandwidth_phase0_20261110/chain.py",
        m.REPO/"analysis/line_models.py",m.REPO/"analysis/lib.py",REGISTRY,a.model_dir/"MODEL.json",a.model_dir/"SNAPSHOT.json"]
    manifest=dict(output_sha256=m.sha(a.out/"PREDICTIONS_22.json"),
        source_sha256={p.resolve().relative_to(m.REPO).as_posix():m.sha(p) for p in src})
    (a.out/"MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(dict(count=len(rows),output_sha256=manifest["output_sha256"],geometry_changes=0),ensure_ascii=False))
if __name__=="__main__":main()
