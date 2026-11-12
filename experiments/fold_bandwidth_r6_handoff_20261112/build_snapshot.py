"""只读收集暂停后的交接快照；仅写本交接目录的新文件，不启动HFSS或解除暂停。"""
import argparse,collections,datetime,hashlib,json,subprocess
from pathlib import Path
import psutil
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PUBLIC=REPO/"experiments/fold_bandwidth_r6_stage2b_20261112"
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,q):
    with p.open("x",encoding="utf-8") as f:json.dump(q,f,ensure_ascii=False,indent=2,allow_nan=False)
def same_process(q):
    try:return abs(psutil.Process(q["pid"]).create_time()-q["create_time"])<.01
    except psutil.NoSuchProcess:return False
def records(root,prefix):return [read(p) for p in sorted((root/"ledger").glob(prefix+"*.json"))]
def build(root):
    cfg=read(root/"authorization.json");pause=read(root/"PAUSE.json")
    assert pause["require_explicit_human_resume"] and not pause["allow_new_Analyze"]
    assert sha(root/"PAUSE.json")==sha(PUBLIC/"PAUSE.json")
    status=read(root/"CURRENT_STATUS.json")
    assert status["phase"]=="paused" and not status["active"] and not status["issues"]
    audit=read(HERE/"PAUSED_PREFIX_AUDIT.json")
    assert audit["passed"] and audit["partial"]
    s1=root.parent/"fig8_fold_bandwidth_r6_20261111_cold1"
    s2=root.parent/"fig8_r6_2a_20261111"
    c1,c2=read(s1/"authorization.json"),read(s2/"authorization.json")
    g1,a1=records(s1,"geometry_"),records(s1,"Analyze_")
    gu=collections.Counter(x["batch"] for x in g1)
    au=collections.Counter(x["batch"] for x in a1)
    gu["1a"]+=c1["prior_geometry_total"];au["1a"]+=c1["prior_Analyze_total"]
    assert c2["prior_geometry_total"]==sum(gu.values())
    assert c2["prior_Analyze_total"]==sum(au.values())
    gu["2a"]=len(records(s2,"geometry_"));au["2a"]=len(records(s2,"Analyze_"))
    assert cfg["prior_geometry_total"]==sum(gu.values())
    assert cfg["prior_Analyze_total"]==sum(au.values())
    geos,calls=records(root,"geometry_"),records(root,"Analyze_")
    gu["2b"],au["2b"]=len(geos),len(calls)
    assert sum(gu.values())==status["total_geometry"]==audit["total_geometry_count"]
    assert sum(au.values())==status["total_Analyze_requested"]==audit["total_actual_Analyze_count"]
    closed=[read(root/"decisions"/(p+"_FINAL.json")) for p in cfg["parent_order"]
            if (root/"decisions"/(p+"_FINAL.json")).exists()]
    remaining=cfg["parent_order"][len(closed):]
    next_case=remaining[0]+"__T1"
    counts=collections.Counter(x["parent_id"] for x in geos)
    rows=[]
    for d in closed:
        case=d["selected_case"];w=root/cfg["case_paths"][case]
        r=read(w/"review/REVIEW_STAGE2.json");f=read(w/"input/freeze.json")
        gg=f["design"]["geometry_mm"]
        actual_a=0 if f["design"]["topology"]=="straight_control" else gg["Ls3"]-gg["Ws"]
        rows.append(dict(parent_id=d["parent_id"],selected_case=case,attempts=counts[d["parent_id"]],
          length_calibrated=d["length_calibrated"],usable_for_law=d["usable_for_law"],
          design_pass=r["design_pass"],numerical_pass=r["numerical_pass"],
          actual_a_mm=actual_a,nominal_a_mm=f["nominal_a_mm"],metrics=r["metrics"],
          mesh_cells=r["mesh_cells"],delta_s=r["delta_s"],reason=d["reason"]))
    future=3*len(remaining)+cfg["limits"]["3"]+cfg["limits"]["4"]+cfg["limits"]["5"]
    budget=dict(unit="R5/R6：一次几何完整分段自适应加最终扫频；actual Analyze API另记，不能混减。",
       limits=cfg["limits"],geometry_used_by_batch=dict(gu),actual_Analyze_by_batch=dict(au),
       geometry_total_used=sum(gu.values()),geometry_total_cap=187,
       nominal_unused_total_cap=187-sum(gu.values()),remaining_registered_geometry_upper_bound=future,
       actual_Analyze_total=sum(au.values()),current_batch_actual_Analyze_validated=audit["actual_Analyze_count"],
       batch2b_cap_unused=66-gu["2b"],batch2b_remaining_parents=len(remaining),
       batch2b_remaining_registered_geometry_upper_bound=3*len(remaining),
       closed_unused_slots_not_transferable=(45-gu["2a"])+(3*len(closed)-gu["2b"]),
       per_geometry_actual_Analyze_implementation_limit=14,
       historical_request_count_includes_failed_requests=True,
       note="剩余额度不是恢复授权；已结项未用槽不得转给其他设计/批次。后续条件对照与进入门槛可能进一步减少实际次数。")
    current=pause["after_case"];w=root/cfg["case_paths"][current]
    last=read(w/"review/REVIEW_STAGE2.json")
    process=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
       current_worker_identity_still_alive=same_process(read(w/"worker_started.json")),
       current_AEDT_identity_still_alive=same_process(read(w/"owner.json")),
       native_cleanup=read(w/"cleanup.json")["released"],
       current_done_sha256=sha(w/"done.json"),
       total_hf3d_processes=sum((p.info["name"] or "").lower()=="hf3d.exe" for p in psutil.process_iter(["name"])),
       total_AEDT_processes=sum((p.info["name"] or "").lower()=="ansysedt.exe" for p in psutil.process_iter(["name"])))
    assert not process["current_worker_identity_still_alive"]
    assert not process["current_AEDT_identity_still_alive"] and process["native_cleanup"]
    nw=root/cfg["case_paths"][next_case]
    assert not any((nw/n).exists() for n in ("worker_started.json","done.json","failure.txt","launch_claim.json"))
    nxt=read(nw/"input/freeze.json")
    snapshot=dict(at=process["at"],phase="user_paused",plan_commit=cfg["plan_commit"],
       branch="codex/fold-bandwidth-r4-execution",handoff_parent_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),
       current_case_completed=current,current_case_review=last,
       geometry_used=budget["geometry_total_used"],actual_Analyze_used=budget["actual_Analyze_total"],
       batch2b_parents_closed=len(closed),batch2b_registered_parents=22,
       batch2b_selected_length_calibrated=sum(d["length_calibrated"] for d in closed),
       batch2b_selected_unresolved=sum(not d["length_calibrated"] for d in closed),
       completed_designs=rows,remaining_parent_order=remaining,next_case_after_explicit_resume=next_case,
       next_case_relative_runtime_path=cfg["case_paths"][next_case],
       next_case_frozen_geometry=nxt["design"]["geometry_mm"],next_case_freeze_sha256=sha(nw/"input/freeze.json"),
       next_checkpoint_completed_Analyze=560,budget=budget,process_check=process,
       public_pause_sha256=sha(PUBLIC/"PAUSE.json"),model_sha256=cfg["model_sha256"],prediction_sha256=cfg["predictions_sha256"],
       original_batches_untouched=True,full_batch2b_complete=False,no_hook=True,
       resume_requires_explicit_human_instruction=True,model_switch_alone_does_not_resume=True,
       stage3_runtime_ready=False,stage3_note="仅R3离线登记和功率口径预查完成，尚未实现/释放阶段3运行器。")
    write(HERE/"HANDOFF.json",snapshot)
    write(HERE/"BUDGET.json",budget)
    write(HERE/"PROCESS_CHECK.json",process)
    write(HERE/"CURRENT_STATUS_AT_PAUSE.json",status)
    write(HERE/"PAUSE_AT_HANDOFF.json",pause)
    sources={p.relative_to(REPO).as_posix():sha(p) for p in
       [PUBLIC/"PAUSE.json",PUBLIC/"STOP_AFTER_CURRENT.json",PUBLIC/"CURRENT_STATUS.json",
        HERE/"PAUSED_PREFIX_AUDIT.json",HERE/"prospective_snapshot/PROSPECTIVE_ERRORS.json"]}
    write(HERE/"SOURCES.json",sources)
    print(json.dumps(dict(geometry=sum(gu.values()),Analyze=sum(au.values()),closed=len(closed),
        calibrated=snapshot["batch2b_selected_length_calibrated"],remaining=len(remaining),next_case=next_case,budget=budget,process=process),ensure_ascii=False))
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("runtime_root",type=Path)
    build(ap.parse_args().runtime_root.resolve())
