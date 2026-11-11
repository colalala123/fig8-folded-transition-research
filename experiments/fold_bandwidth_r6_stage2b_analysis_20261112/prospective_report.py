"""2b首次前瞻误差；纯离线，不改模型/预测/输入，不把调参结果替换首次结果。"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
REGISTRY=REPO/"experiments/fold_bandwidth_r6_stage2_model_20261112/prospective_22/PREDICTIONS_22.json"
MODEL=REPO/"experiments/fold_bandwidth_r6_stage2_model_20261112/fit_complete/MODEL.json"
PUBLIC=REPO/"experiments/fold_bandwidth_r6_stage2b_20261112"
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def error(pred,actual,scale=1.):
    return (pred-actual)*scale if finite(pred) and finite(actual) else None
def stats(values):
    values=[v for v in values if finite(v)]
    if not values:return dict(n=0,mean=None,mae=None,rmse=None,max_abs=None)
    a=np.array(values)
    return dict(n=len(a),mean=float(a.mean()),mae=float(np.abs(a).mean()),rmse=float(np.sqrt(np.mean(a*a))),max_abs=float(np.max(np.abs(a))))
def compare(design,q):
    if q.get("data_role")!="prospective_test":raise ValueError("禁止用调参结果替换前瞻检验")
    if q["geometry_mm"]!=design["geometry_mm"] or q["topology"]!=design["topology"]:
        raise ValueError("首次前瞻几何/拓扑改变")
    pred=design["prediction"];p=pred["parameters"];a=q["circuit"]["parameters"]
    unique=q["circuit"]["extraction_nonunique"] is False
    parameters=dict(a, P_eff=a["zm_eff"]*a["zs_eff"],R_eff=a["zm_eff"]/a["zs_eff"])
    raw={k:error(p[k],parameters[k]) for k in ("zm_eff","zs_eff","fm_GHz","fs_GHz","P_eff","R_eff")}
    errors={k+"_relative_pct":100*raw[k]/parameters[k] if unique and finite(raw[k]) and parameters[k]!=0 else None
            for k in ("zm_eff","zs_eff","P_eff","R_eff")}
    errors.update({k+"_MHz":raw[k]*1000 if unique and finite(raw[k]) else None for k in ("fm_GHz","fs_GHz")})
    bw={}
    for key in ("BW15","BW20","BW_joint"):
        bp=pred["lossless_circuit_bandwidths"][key];ba=q["bandwidths"][key]
        x,y=bp["BW_GHz"],ba["BW_GHz"]
        # 无效主通带不能用外包络跨度或0替代。
        valid=bp.get("fit_eligible") is True and ba.get("fit_eligible") is True
        bw[key]=dict(prediction_GHz=x,HFSS_GHz=y,prediction_valid=bp.get("fit_eligible"),
             HFSS_valid=ba.get("fit_eligible"),prediction_exclusion=bp.get("exclusion_reason"),
             HFSS_exclusion=ba.get("exclusion_reason"),
             lossless_circuit_minus_HFSS_MHz=error(x,y,1000) if valid else None,
             caveat="无耗等效电路与有耗HFSS的比较，不是独立的损耗预测")
        errors[key+"_MHz"]=bw[key]["lossless_circuit_minus_HFSS_MHz"]
    ps=pred["lossless_circuit_shape"];actual=q["shape"]
    errors["central_valley_MHz"]=error(ps.get("central_valley_GHz"),actual.get("central_valley_GHz"),1000)
    return dict(parent_id=design["id"],family=design["family"],topology=design["topology"],
        data_role="prospective_test",attempt_ordinal=1,geometry_mm=design["geometry_mm"],
        first_attempt_role_immutable=True,fit_unique_under_R2=unique,predicted_parameters=p,
        extracted_parameters=parameters,raw_parameter_errors_including_nonunique=raw,
        quantitative_parameter_errors_require_uniqueness=True,errors=errors,bandwidth_comparison=bw,
        HFSS_BW_S21_GHz=q["bandwidths"]["BW_S21"]["BW_GHz"],HFSS_BW_S21_prediction_error=None,
        HFSS_BW_S21_prediction_absent=True,predicted_shape=ps,HFSS_shape=actual,
        label="首次前瞻检验；不以是否调准或设计通过筛除；多解参数不计入定量参数误差")
def build(public=PUBLIC,allow_partial=False):
    reg=read(REGISTRY)
    if reg["model_sha256"]!=sha(MODEL):raise ValueError("冻结模型变化")
    result=[];missing=[];selected=[];sources={REGISTRY.relative_to(REPO).as_posix():sha(REGISTRY),MODEL.relative_to(REPO).as_posix():sha(MODEL)}
    for design in reg["designs"]:
        case=design["id"]+"__T1";out=public/"results"/case
        if not out.exists():missing.append(case);continue
        qp=out/"review/extraction_R2.json";ip=out/"INPUT.json";sp=out/"SUMMARY.json";mp=out/"MANIFEST.json"
        for rel,h in read(mp).items():
            if sha(out/rel)!=h:raise ValueError("公开文件哈希不符："+case+"/"+rel)
        inp=read(ip);summary=read(sp)
        if inp["design"]!=design or inp["attempt_ordinal"]!=1:raise ValueError("首次冻结改变")
        if not summary["review"]["numerical_pass"]:raise ValueError("前瞻数值失败，需单独停止处理")
        row=compare(design,read(qp));row["case"]=case;row["curve_sha256"]=summary["review"]["native_sha256"]
        row["initial_length_calibrated"]=summary["review"]["tuning_status"]["length_calibrated"]
        result.append(row)
        for f in (qp,ip,sp,mp):sources[f.relative_to(REPO).as_posix()]=sha(f)
        dp=public/"decisions"/(design["id"]+"_FINAL.json")
        if dp.exists():
            dec=read(dp);sr=read(public/"results"/dec["selected_case"]/"review/REVIEW_STAGE2.json")
            selected.append(dict(parent_id=design["id"],selected_case=dec["selected_case"],
                 length_calibrated=dec["length_calibrated"],usable_for_law=dec["usable_for_law"],
                 decision_reason=dec["reason"],design_pass=sr["design_pass"],
                 subsequent_tuned_not_independent=sr["attempt_ordinal"]>1))
            sources[dp.relative_to(REPO).as_posix()]=sha(dp)
    if not allow_partial and (missing or len(selected)!=22):raise ValueError("2b未全部结项，不能写完整批次报告")
    subsets={"all":result,**{family:[r for r in result if r["family"]==family] for family in ("N04","N08")},
             **{kind:[r for r in result if r["topology"]==kind] for kind in ("folded","straight_control")}}
    summaries={key:{metric:stats([r["errors"][metric] for r in rows]) for metric in result[0]["errors"]} for key,rows in subsets.items()} if result else {}
    return dict(batch="2b",partial=bool(missing or len(selected)!=22),completed_first=len(result),expected_first=22,
       missing_first=missing,closed_parents=len(selected),selected_length_calibrated=sum(r["length_calibrated"] for r in selected),
       first_prediction_frozen_model_sha256=reg["model_sha256"],first_prediction_registry_sha256=sha(REGISTRY),
       error_sign="prediction_minus_actual",summary=summaries,first_attempts=result,selected_results=selected,
       source_sha256=sources,model_refit=False,new_Analyze=0,hook_messages=0,
       caveats=["首次前瞻不因设计负例、未调准或模型误差大而删除","调参选定结果单列，不进入首次前瞻误差",
                "等效电路含损耗拟合的解释有局限；这里只比较冻结理论参数/无耗电路与实际曲线",
                "未预测有耗HFSS的S21带宽，不将无耗电路S21冒充该预测",
                "直槽尺度为2a弯折数据外推，直槽未调准时不能宣称物理归一化已验证",
                "所有结果仍是名义插值，不是直接频点、全模功率或制造公差认证"])
def report(q):
    lines=["# 阶段2b：首次跨家族前瞻检验","",
       f"已收集 {q['completed_first']}/22 项首次结果，结项 {q['closed_parents']}/22 项。以下误差只用首次求解，不用调参结果替换。",
       "部分结果快照，尚不能作为整批结论。" if q["partial"] else "本批已结项；保留所有负例，不修改已冻结预测。",
       "","误差符号为预测减实测。带宽为无耗电路与含损耗HFSS的差异；无效主带记为缺失，不用外包络跨度填充。",
       "","|首次案例|zs误差 %|fs误差 MHz|BW15差 MHz|中央谷差 MHz|长度调准|设计名义通过|","|---|---:|---:|---:|---:|---|---|"]
    def fmt(x):return "不适用" if x is None else f"{x:.3f}"
    for r in q["first_attempts"]:
        e=r["errors"];lines.append("|"+r["case"]+"|"+ "|".join(fmt(e[k]) for k in ("zs_eff_relative_pct","fs_GHz_MHz","BW15_MHz","central_valley_MHz"))+f"|{r['initial_length_calibrated']}|{r['HFSS_shape']['passed']}|")
    lines+=["","## 分家族误差汇总","","|范围|指标|有效样本|MAE|RMSE|最大绝对误差|","|---|---|---:|---:|---:|---:|"]
    for group,metrics in q["summary"].items():
        for k in ("zs_eff_relative_pct","fs_GHz_MHz","BW15_MHz","central_valley_MHz"):
            s=metrics[k];lines.append(f"|{group}|{k}|{s['n']}|{fmt(s['mae'])}|{fmt(s['rmse'])}|{fmt(s['max_abs'])}|")
    lines+=["","## 证据限制"]+["- "+c for c in q["caveats"]]
    return "\n".join(lines)+"\n"
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--allow-partial",action="store_true");a=p.parse_args()
    q=build(allow_partial=a.allow_partial);a.out.mkdir(parents=True,exist_ok=False)
    (a.out/"PROSPECTIVE_ERRORS.json").write_text(json.dumps(q,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    (a.out/"REPORT.md").write_text(report(q),encoding="utf-8")
    (a.out/"MANIFEST.json").write_text(json.dumps({f.name:sha(f) for f in a.out.iterdir() if f.is_file()},indent=2),encoding="utf-8")
    print(json.dumps({k:q[k] for k in ("completed_first","closed_parents","partial")}))
if __name__=="__main__":main()
