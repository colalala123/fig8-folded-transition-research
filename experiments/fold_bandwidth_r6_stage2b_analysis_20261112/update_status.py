"""2b状态快照，文件/进程只读检查；唯一可更新文件为CURRENT_STATUS.{json,md}。"""
import argparse,datetime,json,os,sys,hashlib
from pathlib import Path
import psutil
REPO=Path(__file__).resolve().parents[2]
PUBLIC=REPO/"experiments/fold_bandwidth_r6_stage2b_20261112"
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def same_worker(identity):
    try:return abs(psutil.Process(identity["pid"]).create_time()-identity["create_time"])<.01
    except (psutil.NoSuchProcess,psutil.AccessDenied):return False
def snapshot(root):
    cfg=read(root/"authorization.json")
    if cfg["batch"]!="2b":raise ValueError("仅2b快照")
    geos=list((root/"ledger").glob("geometry_*.json"));calls=list((root/"ledger").glob("Analyze_*.json"))
    started={read(p)["parent_id"] for p in geos};closed=[read(p) for p in (root/"decisions").glob("*_FINAL.json")]
    if any(d.get("complete") is not True for d in closed):raise ValueError("无效结项")
    active=[];issues=[];first=0;first_ack=0;complete_calls=0
    for case,path in cfg["case_paths"].items():
        w=root/path
        if not w.exists():continue
        done=(w/"done.json").exists();failed=(w/"failure.txt").exists()
        if cfg["case_specs"][case]["attempt_ordinal"]==1:
            first+=done
            ack_path=w/"review/visual_ack.json"
            if done and ack_path.exists():
                ack=read(ack_path)
                if ack.get("actually_viewed") is True and ack["plot_sha256"]==hashlib.sha256((w/"review/S11_S21.png").read_bytes()).hexdigest() and ack["extraction_sha256"]==hashlib.sha256((w/"review/extraction_R2.json").read_bytes()).hexdigest():first_ack+=1
                else:issues.append(dict(case=case,reason="visual_ACK_mismatch"))
        for p in (w/"evidence").glob("*_role_check.json"):
            stage=p.name.removesuffix("_role_check.json")
            if read(p).get("passed") and (w/"evidence"/(stage+"_result.json")).exists():complete_calls+=1
        if failed:issues.append(dict(case=case,reason="failure_marker"))
        if not done and not failed and (w/"worker_started.json").exists():
            identity=read(w/"worker_started.json")
            if same_worker(identity):
                active.append(dict(case=case,worker_identity_verified=True,
                    adaptive14_observed=(w/"evidence/actual_start_observed.json").exists()))
            else:issues.append(dict(case=case,reason="worker_identity_missing_without_terminal"))
    if len(active)>1:issues.append(dict(reason="unexpected_multiple_active_workers"))
    return dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),batch="2b",
        phase="stopped" if (root/"STOP.json").exists() else "paused" if (root/"PAUSE.json").exists() else "running" if active else "review_or_next_release",
        parents_total=22,parents_closed=len(closed),selected_calibrated=sum(d["length_calibrated"] for d in closed),
        closed_unresolved=sum(not d["length_calibrated"] for d in closed),parents_started=len(started),parents_not_started=22-len(started),
        first_prospective_completed=first,first_prospective_visual_ACK=first_ack,active=active,issues=issues,
        geometry_used=len(geos),geometry_limit=66,total_geometry=cfg["prior_geometry_total"]+len(geos),total_geometry_limit=187,
        Analyze_requested=len(calls),Analyze_validated_completed=complete_calls,
        total_Analyze_requested=cfg["prior_Analyze_total"]+len(calls),
        cumulative_checkpoint_count=cfg["prior_Analyze_total"]+complete_calls,
        cumulative_count_note="前批累计为实际请求数，不反向将原技术中断请求认作已闭合核验；本批已验证完成数单列。",
        model_sha256=cfg["model_sha256"],predictions_sha256=cfg["predictions_sha256"],
        requested_cores=14,tasks=1,serial=True,no_hook=True,
        final_sweep_policy="合法扫频角色/单组/核数<=14且完整自适应历史不变",
        first_prospective_never_replaced=True,model_accuracy_verified=False,
        old_batches_paused_and_untouched=True)
def render(q):
    return "\n".join(["# 阶段2b当前快照","",
       f"记录时间（UTC）：{q['at']}。状态：{q['phase']}。此文件可更新；原始输入、预测和结果不覆盖。",
       f"22个设计已结项{q['parents_closed']}个，其中{q['selected_calibrated']}个调准、{q['closed_unresolved']}个限额内未调准；另有{q['parents_not_started']}个尚未启动。",
       f"首次前瞻已完成{q['first_prospective_completed']}个、实际看图ACK {q['first_prospective_visual_ACK']}个。",
       f"本批几何{q['geometry_used']}/66；累计几何{q['total_geometry']}/187。实际Analyze请求累计{q['total_Analyze_requested']}；本批已闭合核验{q['Analyze_validated_completed']}。",
       "","当前真实身份核验通过的worker："+("、".join(x["case"] for x in q["active"]) or "无"),
       "问题标记："+(json.dumps(q["issues"],ensure_ascii=False) if q["issues"] else "无"),
       "","14核/1任务串行；最终扫频按用户确认的阶段规则核验。不发hook。",
       "模型只是已冻结候选，2a精度假设没有通过；本批用于跨家族验证，不宣称已完成可靠逆设计。",""])+"\n"
def main():
    p=argparse.ArgumentParser();p.add_argument("root",type=Path);a=p.parse_args();q=snapshot(a.root)
    for base in (a.root,PUBLIC):
        for name,content in (("CURRENT_STATUS.json",json.dumps(q,ensure_ascii=False,indent=2)+"\n"),("CURRENT_STATUS.md",render(q))):
            tmp=base/(name+".tmp")
            with tmp.open("x",encoding="utf-8") as f:f.write(content)
            os.replace(tmp,base/name)
    print(json.dumps(q,ensure_ascii=False))
if __name__=="__main__":main()
