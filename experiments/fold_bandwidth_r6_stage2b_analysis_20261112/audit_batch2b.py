"""阶段2b结项只读交叉审计：逐尝试、账本、原生历史、角色、图ACK与公开哈希。"""
import argparse,json
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"experiments/fold_bandwidth_r6_stage2_model_20261112"))
import fit_model as m
sys.path.insert(0,str(m.REPO/"experiments/fold_bandwidth_r6_20261111"))
from roles_r6 import evaluate
sys.path.insert(0,str(m.REPO/"experiments/fold_bandwidth_r4_20261110"))
from staged_mesh_r5 import history
from extract_run import extract
import geometry

def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def require(ok,message):
    if not ok:raise ValueError(message)

def audit(root,public):
    cfg=read(root/"authorization.json")
    require(cfg["batch"]=="2b","批次不是2b")
    require(not(root/"STOP.json").exists() and not(root/"PAUSE.json").exists(),"批次有停止/暂停")
    require(len(cfg["parent_order"])==22,"2b设计数错误")
    for parent in cfg["parent_order"]:
        decision=read(root/"decisions"/(parent+"_FINAL.json"))
        require(decision.get("complete") is True,"2b存在未结项设计")
    sys.path.insert(0,str(public))
    from runtime_stage2 import verify_prediction_publication
    verify_prediction_publication(root,cfg)
    for rel,h in cfg["code_hashes"].items():require(m.sha(m.REPO/rel)==h,"冻结代码改变："+rel)
    geometries=[read(p) for p in sorted((root/"ledger").glob("geometry_*.json"))]
    calls=[read(p) for p in sorted((root/"ledger").glob("Analyze_*.json"))]
    require(len(geometries)<=66 and cfg["prior_geometry_total"]+len(geometries)<=187,"预算超限")
    counts=Counter(r["parent_id"] for r in geometries)
    require(len(counts)==22 and max(counts.values())<=3,"设计数或单项上限不符")
    rows=[];roles=Counter()
    for g in geometries:
        case=g["case"];w=(root/cfg["case_paths"][case]).resolve();w.relative_to(root.resolve())
        require((w/"done.json").exists() and not(w/"failure.txt").exists(),"非成功终态："+case)
        record,done,f,q,ack=[read(w/p) for p in ("RUN_RECORD.json","done.json","input/freeze.json","review/extraction_R2.json","review/visual_ack.json")]
        require(record["solve_completed"] and record["numerical_pass"],"未通过原数值检查")
        require(record["cleanup"]["released"],"桌面释放未确认")
        require(done["native_sha256"]==m.sha(w/"native/full_modes.npz")==q["input_sha256"],"原生文件哈希不符")
        require(ack["actually_viewed"] and ack["plot_sha256"]==m.sha(w/"review/S11_S21.png")
                and ack["extraction_sha256"]==m.sha(w/"review/extraction_R2.json"),"实际看图ACK不符")
        require(f["authorization_sha256"]==m.sha(root/"authorization.json"),"授权哈希不符")
        if f["attempt_ordinal"]==1:
            require(f["design"]==cfg["designs"][f["parent_id"]],"首次几何/预测改变")
            require(q["data_role"]=="prospective_test" and f["design"]["first_attempt_role_immutable"],"首次前瞻身份改变")
        else:require(q["data_role"]=="tuned_data","调参身份错误")
        require(geometry.compare_boxes(f["expected_boxes"],read(w/"evidence/native_slot_boxes.json"))["passed"],"槽盒不符")
        hist=history((w/"native/convergence.txt").read_text(encoding="utf-8-sig"))
        pre=history((w/"native/pre_final_sweep.txt").read_text(encoding="utf-8-sig"))
        require(hist==pre,"最终扫频改动自适应历史")
        require(100000<=hist[-1][1]<=112000 and hist[-1][2]<=.005,"网格/ΔS超限")
        case_calls=sorted([r for r in calls if r["case"]==case],key=lambda r:r["index"])
        n=len(case_calls)
        require(n==record["Analyze_requested"] and 2<=n<=14,"实际请求计数不符")
        require([r["index"] for r in case_calls]==list(range(n)),"账本序号缺口")
        require([r["stage"] for r in case_calls]==[f"adaptive_{i:02d}" for i in range(n-1)]+["final_sweep"],"阶段顺序不符")
        for c in case_calls:
            stage=c["stage"]
            obs=[json.loads(line) for line in (w/"evidence"/(stage+"_solver.jsonl")).read_text(encoding="utf-8").splitlines()]
            fresh=evaluate(obs,stage)
            require(fresh["passed"] and fresh==read(w/"evidence"/(stage+"_role_check.json")),"角色复核不符")
            roles.update(o["role"] for o in obs)
        with np.load(w/"native/full_modes.npz",allow_pickle=False) as z:
            require(z["S"].shape==(1500,4,4) and z["Zo"].shape==(1500,4) and z["Gamma"].shape==(1500,4),"全模数据维度错误")
            require(all(np.isfinite(z[k]).all() for k in z.files),"原生数据非有限")
            again=extract(z["f_GHz"],z["S"][:,[0,2],0],read(w/"native/metadata.json"))
        require(again["shape"]==q["shape"] and again["bandwidths"]==q["bandwidths"],"带宽/形状独立重算不一致")
        par1=q["circuit"]["parameters"];par2=again["circuit"]["parameters"]
        diff=max(abs(par1[k]-par2[k]) for k in par1)
        require(diff<1e-8 and again["circuit"]["extraction_nonunique"]==q["circuit"]["extraction_nonunique"],"提取重算不一致")
        pub=public/"results"/case
        manifest=read(pub/"MANIFEST.json")
        for rel,h in manifest.items():require(m.sha(pub/rel)==h,"公开结果文件改变："+case+"/"+rel)
        require(m.sha(pub/"native/full_modes.npz")==m.sha(w/"native/full_modes.npz"),"公开/本机原生数据不一致")
        require(m.sha(pub/"review/extraction_R2.json")==m.sha(w/"review/extraction_R2.json"),"公开/本机提取不一致")
        started=read(w/"worker_started.json")["at"]
        finished=record["finished_at"]
        elapsed=(datetime.fromisoformat(finished)-datetime.fromisoformat(started)).total_seconds()
        require(elapsed>=0,"时间戳顺序不符")
        rows.append(dict(case=case,parent_id=g["parent_id"],started_at=started,finished_at=finished,wall_seconds=elapsed,mesh_cells=hist[-1][1],passes=hist[-1][0],
            delta_s=hist[-1][2],Analyze=n,design_pass=q["shape"]["passed"],numerical_pass=True,
            extracted_parameters_max_abs_recompute_difference=diff,mesh_history_unchanged=True,
            curve_sha256=m.sha(w/"native/full_modes.npz"),public_manifest_sha256=m.sha(pub/"MANIFEST.json")))
    require(sum(r["Analyze"] for r in rows)==len(calls),"账本总额不一致")
    return dict(passed=True,batch="2b",parents=22,geometry_count=len(geometries),
        total_geometry_count=cfg["prior_geometry_total"]+len(geometries),batch_geometry_limit=66,total_geometry_limit=187,
        actual_Analyze_count=len(calls),total_actual_Analyze_count=cfg["prior_Analyze_total"]+len(calls),
        all_numerical_pass=True,technical_failures=0,rows=rows,observed_role_record_counts=dict(roles),
        full_modal_power_certified=False,direct_frequency_certified=False,manufacturing_tolerance_certified=False,
        prospective_first_count=22,new_Analyze_requests=0,hook_messages=0,
        note="只读重算所有已完成尝试；役别核验不要求端口准备进程14核，最终扫频只核验合法扫频角色/单组/≤14核和历史不变。")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("root",type=Path);ap.add_argument("--public",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args();q=audit(a.root,a.public)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x",encoding="utf-8") as fp:json.dump(q,fp,indent=2,ensure_ascii=False,allow_nan=False)
    print(json.dumps({k:v for k,v in q.items() if k not in ("rows",)},ensure_ascii=False))
if __name__=="__main__":main()
