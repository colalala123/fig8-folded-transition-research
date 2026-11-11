"""2b离线准备；必须先有完整2a审计和22项预测冻结。不连接AEDT。"""
import argparse,copy,subprocess,shutil
from common_stage2 import *
import geometry
from presubmit import presubmit
from tuning import propose,MODELDIR,MODEL
REGISTRY=MODELDIR/"prospective_22/PREDICTIONS_22.json"
MANIFEST=MODELDIR/"prospective_22/MANIFEST.json"
SNAPSHOT=MODELDIR/"fit_complete/SNAPSHOT.json"
AUDIT=MODELDIR/"validation/INDEPENDENT_AUDIT.json"
ORIGINAL=REPO/"experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json"
BOXES=REPO/"experiments/fold_bandwidth_r1_20261110/freeze_r1/SLOT_BOXES.json"

def initial_designs():
    p=read(REGISTRY);manifest=read(MANIFEST)
    if p["batch"]!="2b" or p["prospective_count"]!=22 or p["model_sha256"]!=sha(MODEL):
        raise RuntimeError("2b预测与模型不符")
    if manifest["output_sha256"]!=sha(REGISTRY):raise RuntimeError("预测冻结哈希不符")
    for rel,h in manifest["source_sha256"].items():
        if sha(REPO/rel)!=h:raise RuntimeError("模型/预测来源变化："+rel)
    rows=p["designs"]
    if len(rows)!=22 or {r["family"] for r in rows}!={"N04","N08"}:raise RuntimeError("不是22项指定家族")
    originals={r["id"]:r for r in read(ORIGINAL)["designs"] if r["batch"]=="2b"}
    boxes={r["id"]:r for r in read(BOXES)}
    if set(originals)!={r["id"] for r in rows}:raise RuntimeError("22项设计身份不符")
    for r in rows:
        old=originals[r["id"]]
        if r["geometry_mm"]!=old["geometry_mm"] or r["topology"]!=old["topology"]:raise RuntimeError("初始几何偏离R1")
        if r["expected_boxes"]!=boxes[r["id"]]["boxes"]:raise RuntimeError("初始槽盒偏离R1")
        if r["data_role"]!="prospective_test" or r["first_attempt_role_immutable"] is not True:
            raise RuntimeError("首次前瞻身份不符")
        if not presubmit(r["geometry_mm"],r["screen"]["a_mm"],topology=r["topology"])["can_submit"]:
            raise RuntimeError("初始几何筛选未过")
    return rows

def prepare(previous,dest):
    if dest.exists():raise RuntimeError("新2b目录已存在，不覆盖")
    if (previous/"STOP.json").exists() or (previous/"PAUSE.json").exists():raise RuntimeError("前批停止或暂停")
    audit,snapshot=read(AUDIT),read(SNAPSHOT)
    if not audit["passed"] or audit["parents"]!=15 or not snapshot["summary"]["count_conditions_met"]:
        raise RuntimeError("2a审计/结项/阶梯数量未过")
    previous_cfg=read(previous/"authorization.json")
    if previous_cfg["batch"]!="2a":raise RuntimeError("前批身份不符")
    geos=list((previous/"ledger").glob("geometry_*.json"));calls=list((previous/"ledger").glob("Analyze_*.json"))
    if audit["geometry_count"]!=len(geos) or audit["actual_Analyze_count"]!=len(calls):raise RuntimeError("2a账本与审计不一致")
    for parent in previous_cfg["parent_order"]:
        d=read(previous/"decisions"/(parent+"_FINAL.json"))
        if d.get("complete") is not True:raise RuntimeError("2a有未结项设计")
    for row in audit["rows"]:
        w=case_dir(previous,row["case"],previous_cfg)
        if not read(w/"cleanup.json")["released"] or not(w/"done.json").exists():raise RuntimeError("前批未释放/未完成")
        if sha(w/"native/full_modes.npz")!=row["curve_sha256"]:raise RuntimeError("前批曲线改变")
    consent=read(previous/"sweep_role_confirmation.json")
    if consent.get("policy")!="stage_specific" or not consent.get("human_reply_received"):raise RuntimeError("扫频规则未经确认")
    import psutil
    if any((p.info["name"] or "").lower()=="hf3d.exe" for p in psutil.process_iter(["name"])):
        raise RuntimeError("其他求解仍在，不能准备2b释放")
    if shutil.disk_usage(dest.parent).free<35*1024**3:raise RuntimeError("空间少于35GiB")
    rows=initial_designs()
    cfg=dict(at=now(),human_authorized=True,batch="2b",plan_path="docs/PLAN_20261110_FOLD_BANDWIDTH_R6.md",
        plan_commit=subprocess.check_output(["git","rev-parse","origin/claude/fold-bandwidth-plan"],cwd=REPO,text=True).strip(),
        user_authorization="用户明确同意R6，满足R1/R4进入条件后接续后续批；首次2b前瞻标签永久保留。",
        limits=LIMITS,total_geometry_limit=187,prior_geometry_total=audit["total_geometry_count"],
        prior_Analyze_total=audit["total_actual_Analyze_count"],cores=14,tasks=1,serial=True,no_hook=True,
        aedt_install=previous_cfg["aedt_install"],prior_batch_audit=str(AUDIT),prior_batch_snapshot=str(SNAPSHOT),
        model_path=MODEL.relative_to(REPO).as_posix(),model_sha256=sha(MODEL),
        predictions_path=REGISTRY.relative_to(REPO).as_posix(),predictions_sha256=sha(REGISTRY),
        parent_order=[r["id"] for r in rows],designs={r["id"]:r for r in rows},case_paths={},case_specs={},
        plan_hashes={},historical_hashes={},code_hashes={},batch_geometry_limit=66,
        per_parent_geometry_limit=3,per_geometry_Analyze_limit=14,
        technical_recovery_policy="R6 2.3；本入口仅冷启动，故障保留停止；缓存恢复必须版本化独立审核，不能自动重派。")
    for r in rows:
        prefix="uniform_control" if r["topology"]=="straight_control" else "runs"
        for i in range(1,4):
            case=r["id"]+f"__T{i}"
            cfg["case_paths"][case]=f"{prefix}/{r['id']}/attempt_{i:03d}"
            cfg["case_specs"][case]=dict(parent_id=r["id"],attempt_ordinal=i)
    for p in sorted((REPO/"docs").glob("PLAN_20261110_FOLD_BANDWIDTH*.md")):
        cfg["plan_hashes"][p.relative_to(REPO).as_posix()]=sha(p)
    historical=[previous/"authorization.json",previous/"sweep_role_confirmation.json",AUDIT,SNAPSHOT,MODEL,REGISTRY,MANIFEST,
                *geos,*calls,*sorted((previous/"decisions").glob("*_FINAL.json"))]
    cfg["historical_hashes"]={str(p):sha(p) for p in historical}
    cfg["code_hashes"]=dict(previous_cfg["code_hashes"])
    for folder in (HERE,MODELDIR):
        for p in sorted(folder.glob("*.py")):cfg["code_hashes"][p.relative_to(REPO).as_posix()]=sha(p)
    dest.mkdir()
    for name in ("ledger","decisions","model_freeze"):(dest/name).mkdir()
    write(dest/"authorization.json",cfg)
    shutil.copyfile(previous/"sweep_role_confirmation.json",dest/"sweep_role_confirmation.json")
    for parent in cfg["parent_order"]:prepare_attempt(dest,parent,1)
    write(dest/"PREPARED.json",dict(at=now(),authorization_sha256=sha(dest/"authorization.json"),initial_count=22,
        solver_started=False,new_Analyze=0,requires_publication_proof=True))

def tuned_design(prior,suggestion,parent,curve_sha,path,nominal_a):
    pred=copy.deepcopy(prior)
    pred.update(geometry_mm=suggestion["geometry_mm"],prediction=suggestion["prediction"],data_role="tuned_data",
        parent=parent,initial_prediction_stage="2a_frozen_model_after_actual_length_update",
        tuning=suggestion,prior_curve_sha256=curve_sha,initial_screen=copy.deepcopy(prior["screen"]),
        screen=suggestion["screen"]["screen_after"],nominal_a_mm=nominal_a,actual_a_mm=suggestion["actual_a_mm"],
        future_run_directory=path,source_geometry_unchanged=False,
        expected_boxes=geometry.slot_boxes(suggestion["geometry_mm"],prior["topology"]),
        first_attempt_record_never_overwritten=True)
    return pred

def prepare_attempt(root,parent,ordinal):
    cfg=read(root/"authorization.json")
    if (root/"STOP.json").exists() or (root/"PAUSE.json").exists():raise RuntimeError("2b停止或暂停")
    if cfg["batch"]!="2b" or parent not in cfg["designs"] or not 1<=ordinal<=3:raise RuntimeError("未授权的尝试")
    case=parent+f"__T{ordinal}";w=case_dir(root,case,cfg)
    if w.exists():raise RuntimeError("尝试目录已存在，不覆盖")
    prior=cfg["designs"][parent];nominal_a=prior["screen"]["a_mm"]
    pred=copy.deepcopy(prior);previous_hash=None
    if ordinal>1:
        old=case_dir(root,parent+f"__T{ordinal-1}",cfg);r=read(old/"review/REVIEW_STAGE2.json");ack=read(old/"review/visual_ack.json")
        if r["numerical_pass"] is not True or not ack.get("actually_viewed") or ack["plot_sha256"]!=sha(old/"review/S11_S21.png"):
            raise RuntimeError("前次未数值通过/实际看图")
        qp=old/"review/extraction_R2.json"
        if ack["extraction_sha256"]!=sha(qp):raise RuntimeError("ACK提取哈希不符")
        suggestion=propose(read(qp),nominal_a,prior["topology"])
        if not suggestion["needs_solve"]:raise RuntimeError("无合法下一次调整")
        pred=tuned_design(prior,suggestion,parent,read(old/"done.json")["native_sha256"],cfg["case_paths"][case],nominal_a)
        previous_hash=sha(qp)
    source_hashes={**read(MANIFEST)["source_sha256"],REGISTRY.relative_to(REPO).as_posix():sha(REGISTRY),
        MANIFEST.relative_to(REPO).as_posix():sha(MANIFEST),BOXES.relative_to(REPO).as_posix():sha(BOXES),
        "hfss/INV01_A14.aedt":sha(REPO/"hfss/INV01_A14.aedt")}
    for name in ("input","evidence","native"):(w/name).mkdir(parents=True)
    freeze=dict(at=now(),parent_id=parent,attempt_ordinal=ordinal,design=pred,nominal_a_mm=nominal_a,
        expected_boxes=geometry.slot_boxes(pred["geometry_mm"],pred["topology"]),source_hashes=source_hashes,
        authorization_sha256=sha(root/"authorization.json"),resume=False,inherited_Analyze=0,
        previous_extraction_sha256=previous_hash,prediction_level="单家族模型向新家族的冻结预测，尚未验证；第一次结果永久保留前瞻身份",
        solver_started=False)
    write(w/"input/freeze.json",freeze);write(root/"model_freeze"/(case+".json"),freeze)
    return w

if __name__=="__main__":
    p=argparse.ArgumentParser();s=p.add_subparsers(dest="command",required=True)
    q=s.add_parser("prepare");q.add_argument("previous",type=Path);q.add_argument("dest",type=Path)
    q=s.add_parser("attempt");q.add_argument("root",type=Path);q.add_argument("parent");q.add_argument("ordinal",type=int)
    a=p.parse_args()
    if a.command=="prepare":prepare(a.previous.resolve(),a.dest.resolve())
    else:prepare_attempt(a.root.resolve(),a.parent,a.ordinal)
