"""读取已冻结2a模型，生成新报告目录；不改模型/预测，不连接HFSS。"""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import fit_model as m

def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def val(x,n=5):return "空" if x is None else f"{x:.{n}f}"
def bw(r,key):return r["bandwidths"][key]["BW_GHz"]

def h2_h3(snapshot,model):
    rows=[r for r in snapshot["rows"] if m.eligible(r)]
    reference=next(r for r in rows if r["case"]=="N14_A18")
    zm0,zs0=[reference["circuit"][k] for k in ("zm_eff","zs_eff")]
    base_circ=m.chain.closed_band(zm0*zs0,zm0,6.72,-15)["BW_GHz"]
    shape0=m.shape_value(model["kappa"]["kind"],reference,model["kappa"]["k"],model["kappa"].get("g0_mm"))
    entries=[]
    for r in rows:
        if r["case"]==reference["case"]:continue
        if bw(r,"BW15") is None:raise ValueError("合格点缺BW15，不以零补")
        factor=m.shape_value(model["kappa"]["kind"],r,model["kappa"]["k"],model["kappa"].get("g0_mm"))/shape0
        pred=1000*(m.chain.closed_band(zm0*zs0*factor,zm0,6.72,-15)["BW_GHz"]-base_circ)
        actual=1000*(bw(r,"BW15")-bw(reference,"BW15"))
        s21=None if bw(r,"BW_S21") is None else 1000*(bw(r,"BW_S21")-bw(reference,"BW_S21"))
        extracted=m.chain.closed_band(r["circuit"]["zm_eff"]*r["circuit"]["zs_eff"],r["circuit"]["zm_eff"],6.72,-15)["BW_GHz"]
        entries.append(dict(case=r["case"],a_mm=m.dimensions(r)["a_mm"],g_mm=m.dimensions(r)["g_mm"],
            delta_BW15_HFSS_MHz=actual,delta_BW15_kappa_only_MHz=pred,H2_residual_MHz=pred-actual,
            H2_within_30MHz=abs(pred-actual)<=30.,
            delta_BW15_extracted_circuit_MHz=1000*(extracted-base_circ),
            delta_BW_S21_MHz=s21,H3_raw_condition=None if s21 is None else abs(s21)<.2*abs(actual),
            H3_ratio=None if s21 is None or abs(actual)<1e-12 else abs(s21/actual),
            noise_sensitive_small_delta=abs(actual)<10))
    return dict(reference_case=reference["case"],fixed_f0_GHz=6.72,
        H2_model_fit_is_retrospective=True,H2_independent_validation_pending_2b=True,
        H2_zm_held_to_reference=True,rows=entries,
        H2_error_MHz=m.error_summary([r["H2_residual_MHz"] for r in entries]),
        H2_every_point_within_30MHz=all(r["H2_within_30MHz"] for r in entries),
        H3_every_nonreference_point_satisfies_raw_condition=all(r["H3_raw_condition"] for r in entries),
        note="固定f0的闭式电路及只变zs的分解，不等同含损耗HFSS的绝对带宽预测；小差值的H3比例受数值噪声影响。")

def generate(model_dir,out):
    model=read(model_dir/"MODEL.json");snap=read(model_dir/"SNAPSHOT.json")
    checks=h2_h3(snap,model)
    out.mkdir(parents=True,exist_ok=False)
    (out/"H2_H3.json").write_text(json.dumps(checks,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    rows=snap["rows"];selected=[r for r in rows if r["source"]=="stage2a_selected"]
    calibrated=sum(r["length_calibrated"] for r in selected)
    lines=["# 阶段2a：N14固定线宽弯折阶梯及交叉点结项","",
        f"15个设计已按每项最多三次的规程结项，其中{calibrated}项长度调准；未调准项保留完整记录，不再加点。E1/E2数量门槛见下；κ与槽长修正已写入独立模型冻结，尚未完成跨家族前瞻检验。",
        "本报告中的“调准”仅指中央谷和平衡，不等于−20 dB设计达标。没有做无耗对照或直接频点认证，不能据此宣称辐射机理已证实。","",
        "## 阶梯数量与样本","",
        "|阶梯|严格控制变量|合格位置数|至少5点|","|---|---|---:|---|"]
    for k,s in snap["summary"]["stairs"].items():
        lines.append(f"|{k}|{s['fixed_axis']}={s['fixed_value_mm']}|{s['distinct_calibrated_count']}|{'通过' if s['count_gate_passed'] else '未通过'}|")
    lines += ["","|选定案例|实际a|实际g|中心GHz|峰差dB|BW15 GHz|BW20 GHz|长度调准|",
        "|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in selected:
        lines.append("|"+"|".join([r["case"],val(r["actual_a_mm"],3),val(r["actual_g_mm"],3),
            val(r["central_valley_GHz"],2),val(r["peak_difference_dB"]),val(bw(r,"BW15")),val(bw(r,"BW20")),
            "是" if r["length_calibrated"] else "否"])+"|")
    lines+=["","归档N14_A14和N14_A18仅作为已允许的两个参考，不冒充本轮新测。最长折臂/最远间隔的尝试若被净距筛选缩短a，表里使用实际a，不把它放回名义阶梯。","",
        "## κ：三种预定候选，整组留出","",
        "|候选|组等权相对RMSE|最大逐点误差|逐点1%|","|---|---:|---:|---|"]
    for c in model["candidate_CV"]:
        lines.append(f"|{c['kind']}|{100*c['group_balanced_RMSE_relative']:.3f}%|{100*c['max_relative_error']:.3f}%|{'通过' if c['within_1percent_every_point'] else '未通过'}|")
    k=model["kappa"];length=model["slot_length"];lc=model["length_CV"]
    lines+=["",f"冻结候选：{k['kind']}，A_N14={k['A_N14']:.9f}，k={k['k']:.9f}"+
        (f"，g0={k['g0_mm']:.9f} mm。" if "g0_mm" in k else "。"),
        "**A只是从调准弯折点外推的直槽尺度。E0未调准，未参与拟合，也没有被当成已验证直槽分母。故H1实测直槽归一化证据仍缺，不能写成已经证实的普适定律。**",
        "整组留出按E1/E2/E3划分；共享的归档基准在对应折中移出训练。所有误差是单家族回顾性误差，不是2b前瞻结果。",
        "三个候选均超出逐点1%限制，不通过增加模型项掩盖。冻结的是预定候选中误差最小者，精度不足如实保留。" if model["all_candidates_exceed_1percent"] else
        "至少一个候选在本次整组留出上达到逐点1%；这仍不能替代跨家族检验。",
        "", "## 槽中心线长度修正","",
        "在原A.2中心线式上添加：",
        f"`δLs_extra = {length['delta_intercept_mm']:.9f} + ({length['delta_a_coefficient']:.9f})·a + ({length['g_minus_0p55_coefficient']:.9f})·(g−0.55)` mm。",
        "Wm/Ws系数保留原先验，因为N14单一宽度无法识别它们。微带长度修正和N1也没有重拟合。",
        f"整组留出fs误差：组等权RMSE {lc['group_balanced_RMSE_MHz']:.3f} MHz，最大{lc['max_abs_MHz']:.3f} MHz；15 MHz逐点要求{'通过' if lc['within_15MHz_every_point'] else '未通过'}。","",
        "## 带宽解释与限制","",
        f"- H2只变zs的闭式差值预测，相对a=1.8归档基准：MAE {checks['H2_error_MHz']['MAE']:.3f} MHz，最大{checks['H2_error_MHz']['max_abs']:.3f} MHz；逐点30 MHz要求{'满足' if checks['H2_every_point_within_30MHz'] else '不全满足'}。",
        f"- H3的逐点原始不等式{'全部满足' if checks['H3_every_nonreference_point_satisfies_raw_condition'] else '并非全范围成立'}；具体差值与小差值噪声警告在H2_H3.json，不能用平均效应掩盖反例。",
        "- E2的g增大使BW15下降，不能硬解释成H7预期的互耦效应减弱；现阶段只报告观测，不推断辐射损耗。",
        "- 等纹波带宽代价、无耗损耗分解尚属后续阶段，本批没有这些证据。",
        "", "## 接续边界","",
        "2b仍需：拉取并检查新修订、22项预测及模型哈希冻结、提交推送早于首个Analyze、独立新批预算/进程/CAD核查。报告及模型文件本身不是启动记录。",
        "首次2b结果永久标为前瞻检验，后续长度调整另标调参所得；不会回写本模型来美化首次误差。",
        "",f"模型SHA256：`{m.sha(model_dir/'MODEL.json')}`。",
        "未新增几何、未改阈值、未发送hook。"]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    fig,ax=plt.subplots(1,2,figsize=(11,4.5))
    for c in model["candidate_CV"]:
        a=[];e=[]
        for f in c["folds"]:
            for case,err in zip(f["held_case_ids"],f["errors_relative"]):
                r=next(r for r in rows if r["case"]==case);a.append(r["actual_a_mm"]);e.append(err*100)
        ax[0].scatter(a,e,label=c["kind"],s=25)
    ax[0].axhline(1,color="gray",ls="--");ax[0].axhline(-1,color="gray",ls="--")
    ax[0].set(xlabel="Actual fold arm a (mm)",ylabel="Held-group slot-impedance error (%)")
    ax[0].legend();ax[0].grid(alpha=.25)
    xs=[r["delta_BW15_HFSS_MHz"] for r in checks["rows"]]
    ys=[r["delta_BW15_kappa_only_MHz"] for r in checks["rows"]]
    ax[1].scatter(xs,ys);lo=min(xs+ys)-30;hi=max(xs+ys)+30
    ax[1].plot([lo,hi],[lo,hi],color="gray");ax[1].plot([lo,hi],[lo+30,hi+30],color="gray",ls="--");ax[1].plot([lo,hi],[lo-30,hi-30],color="gray",ls="--")
    ax[1].set(xlabel="HFSS delta BW15 (MHz)",ylabel="Kappa-only circuit delta BW15 (MHz)")
    ax[1].grid(alpha=.25)
    fig.suptitle("N14 retrospective fit: not cross-family certification")
    fig.tight_layout();fig.savefig(out/"MODEL_DIAGNOSTICS.png",dpi=150);plt.close(fig)
    manifest={p.name:m.sha(p) for p in out.iterdir() if p.is_file()}
    (out/"MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(dict(calibrated=calibrated,H2=checks["H2_error_MHz"],H3=checks["H3_every_nonreference_point_satisfies_raw_condition"]),ensure_ascii=False))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("model_dir",type=Path);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();generate(a.model_dir,a.out)
