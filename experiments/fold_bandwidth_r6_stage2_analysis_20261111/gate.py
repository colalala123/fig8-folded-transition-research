"""2a只读汇总和阶梯门槛；不连接HFSS、不派发、不冻结模型。"""
import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAGE2 = REPO / "experiments/fold_bandwidth_r6_stage2_20261111"
ARCHIVE = REPO / "experiments/fold_bandwidth_r2_20261110/replay_r2/EXTRACTED_80.json"

def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def calibrated(q):
    s = q["shape"]
    c, b = s.get("central_valley_GHz"), s.get("peak_difference_dB")
    return bool(s.get("shape_valid") and isinstance(c, (int, float)) and
                isinstance(b, (int, float)) and abs(c - 6.72) <= .03 + 1e-12 and b <= .5 + 1e-12)

def point(q, source, parent=None, nominal_a=None, numerical=True, topology="folded"):
    g = q["geometry_mm"]
    a = 0. if topology == "straight" else g["Ls3"] - g["Ws"]
    gap = 0. if topology == "straight" else g["Ls2"] - 2*g["Ws"]
    return dict(case=q["case"], source=source, parent_id=parent, topology=topology,
                nominal_a_mm=nominal_a, actual_a_mm=a, actual_g_mm=gap,
                geometry_mm=g, length_calibrated=calibrated(q),
                numerical_pass=bool(numerical),
                fit_unique_under_R2=q["circuit"]["extraction_nonunique"] is False,
                circuit=q["circuit"]["parameters"],
                central_valley_GHz=q["shape"].get("central_valley_GHz"),
                peak_difference_dB=q["shape"].get("peak_difference_dB"),
                bandwidths=q["bandwidths"])

def staircase(rows, axis):
    other = "actual_g_mm" if axis == "actual_a_mm" else "actual_a_mm"
    fixed = .55 if axis == "actual_a_mm" else 1.8
    relevant, off_stair, groups = [], [], {}
    prefix = "S2_E1_" if axis == "actual_a_mm" else "S2_E2_"
    for r in rows:
        in_scope = r["source"] == "archive_reference" or (r.get("parent_id") or "").startswith(prefix)
        if not in_scope or r["topology"] != "folded":
            continue
        if abs(r[other]-fixed) > 1e-8:
            off_stair.append(r["case"])
            continue
        relevant.append(r)
        if r["length_calibrated"] and r["numerical_pass"]:
            groups.setdefault(round(r[axis], 6), []).append(r)
    return dict(axis=axis, fixed_axis=other, fixed_value_mm=fixed,
                distinct_calibrated_count=len(groups),
                distinct_fit_eligible_count=sum(any(r["fit_unique_under_R2"] for r in group) for group in groups.values()),
                calibrated_values_mm=sorted(groups),
                members={str(k):[r["case"] for r in v] for k,v in sorted(groups.items())},
                excluded_off_stair_cases=off_stair,
                considered_cases=[r["case"] for r in relevant],
                minimum_required=5, count_gate_passed=len(groups) >= 5)

def summarize(rows, expected_parents, closed_parents, stop_exists=False):
    stairs = dict(E1=staircase(rows, "actual_a_mm"), E2=staircase(rows, "actual_g_mm"))
    missing = sorted(set(expected_parents)-set(closed_parents))
    return dict(all_15_parents_closed=not missing and len(expected_parents)==15,
                missing_parents=missing, current_batch_stopped=stop_exists, stairs=stairs,
                count_conditions_met=(not missing and len(expected_parents)==15 and not stop_exists and
                                      all(s["count_gate_passed"] for s in stairs.values())),
                model_coefficients_frozen=False, prospective_2b_predictions_pushed=False,
                may_launch_2b=False,
                note="此脚本只检查计数，不授予接续；还必须完成κ/长度修正冻结、2b预测推送及原计划的其他进入条件。")

def assemble(root):
    cfg = read(root/"authorization.json")
    if cfg["batch"] != "2a" or len(cfg["parent_order"]) != 15:
        raise ValueError("不是已登记的2a/15设计")
    rows, inputs, closed = [], {}, []
    inputs["archive_R2/EXTRACTED_80.json"] = sha(ARCHIVE)
    for q in read(ARCHIVE):
        if q["case"] in ("N14_A14", "N14_A18"):
            rows.append(point(q, "archive_reference"))
    if len(rows) != 2:
        raise ValueError("缺少两项原始归档阶梯参考")
    for parent in cfg["parent_order"]:
        dpath = root/"decisions"/(parent+"_FINAL.json")
        if not dpath.exists():
            continue
        d = read(dpath)
        if d.get("complete") is not True:
            continue
        case = d["selected_case"]
        w = (root/cfg["case_paths"][case]).resolve()
        w.relative_to(root.resolve())
        review_path = w/"review/REVIEW_STAGE2.json"
        ack_path = w/"review/visual_ack.json"
        if d["review_sha256"] != sha(review_path) or d["visual_ack_sha256"] != sha(ack_path):
            raise ValueError("结项证据哈希不符: "+case)
        review, ack, q = read(review_path), read(ack_path), read(w/"review/extraction_R2.json")
        if not ack.get("actually_viewed") or ack["plot_sha256"] != sha(w/"review/S11_S21.png"):
            raise ValueError("缺少真实看图证据: "+case)
        if ack["extraction_sha256"] != sha(w/"review/extraction_R2.json"):
            raise ValueError("提取哈希不符: "+case)
        if calibrated(q) != review["tuning_status"]["length_calibrated"]:
            raise ValueError("独立调准判断不符: "+case)
        f = read(w/"input/freeze.json")
        rows.append(point(q,"stage2a_selected",parent,f["nominal_a_mm"],review["numerical_pass"],f["design"]["topology"]))
        closed.append(parent)
        for label,p in dict(decision=dpath,review=review_path,extraction=w/"review/extraction_R2.json",ack=ack_path,freeze=w/"input/freeze.json").items():
            inputs[case+"/"+label] = sha(p)
    return dict(summary=summarize(rows,cfg["parent_order"],closed,(root/"STOP.json").exists()),
                rows=rows, source_sha256=inputs, new_Analyze_requests=0, hook_messages=0)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    report=assemble(a.root.resolve())
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x",encoding="utf-8") as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report["summary"],ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
