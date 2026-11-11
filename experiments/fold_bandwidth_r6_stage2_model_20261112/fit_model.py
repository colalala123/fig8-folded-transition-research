"""R6/2a离线拟合；无求解/网络/原始数据写入。输出必须是新文件。"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import least_squares, brentq
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/"experiments/fold_bandwidth_r2_20261110"))
import chain
sys.path.insert(0,str(REPO/"experiments/fold_bandwidth_r6_stage2_analysis_20261111"))
from gate_v2 import assemble

KINDS=("ka","krho","ka_exp")
REFERENCE_WIDTHS=dict(Wm=1.810636,Ws=.394178)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dimensions(row):
    return chain.dimensions(row["geometry_mm"],row.get("topology","folded"))

def eligible(row):
    return (row.get("topology")=="folded" and row.get("length_calibrated") is True
            and row.get("numerical_pass") is True and row.get("fit_unique_under_R2") is True)

def staircase_members(rows):
    groups=dict(E1=[],E2=[],E3=[])
    for i,r in enumerate(rows):
        d=dimensions(r);a,g=d["a_mm"],d["g_mm"]
        parent=r.get("parent_id") or ""
        archive=r.get("source")=="archive_reference"
        if (parent.startswith("S2_E1_") or archive) and abs(g-.55)<1e-8:
            groups["E1"].append(i)
        if (parent.startswith("S2_E2_") or archive) and abs(a-1.8)<1e-8:
            groups["E2"].append(i)
        if parent.startswith("S2_E3_"):
            groups["E3"].append(i)
    if any(not g for g in groups.values()):
        raise ValueError("缺少可用的整组留出；不能补造样本")
    return groups

def shape_value(kind,row,k,g0=None):
    if kind not in KINDS:raise ValueError("未知κ候选")
    if not math.isfinite(k) or k<0:raise ValueError("k必须非负")
    d=dimensions(row)
    if d["a_mm"]==0:
        return 1.
    if kind=="ka":x=d["a_mm"]
    elif kind=="krho":x=d["rho"]
    elif kind=="ka_exp":
        if g0 is None or not math.isfinite(g0) or g0<=0:raise ValueError("衰减长度须为正")
        x=d["a_mm"]*math.exp(-d["g_mm"]/g0)
    else:raise ValueError("未知κ候选")
    if not math.isfinite(k) or k<0:raise ValueError("k必须非负")
    return 1-k*x

def fitted_zs(model,row):
    q=model["A_N14"]*shape_value(model["kind"],row,model["k"],model.get("g0_mm"))
    if not math.isfinite(q) or q<=0:raise ValueError("模型产生非正槽阻抗")
    return q

def fit_kappa(rows,kind):
    if kind not in KINDS or len(rows)<3:raise ValueError("候选或样本不足")
    y=np.array([r["circuit"]["zs_eff"] for r in rows])
    if not np.all(np.isfinite(y)&(y>0)):raise ValueError("无效槽阻抗标签")
    xmax=max(dimensions(r)["rho"] if kind=="krho" else dimensions(r)["a_mm"] for r in rows)
    kmax=.999/max(xmax,1.0 if kind=="krho" else 3.0)
    def unpack(v):
        return dict(kind=kind,A_N14=float(v[0]),k=float(v[1]),
                    **({"g0_mm":float(np.exp(v[2]))} if kind=="ka_exp" else {}))
    def residual(v):
        m=unpack(v)
        return (np.array([fitted_zs(m,r) for r in rows])-y)/y
    starts=[.05,.2,1.,5.,50.,500.] if kind=="ka_exp" else [None]
    fits=[]
    for g0 in starts:
        x0=[float(np.max(y)*1.08),min(.05,kmax*.5)]
        lo=[.1,0.];hi=[10.,kmax]
        if g0 is not None:x0.append(np.log(g0));lo.append(np.log(.02));hi.append(np.log(1000.))
        s=least_squares(residual,x0,bounds=(lo,hi),xtol=1e-12,gtol=1e-12,ftol=1e-12,max_nfev=10000)
        if s.success and np.isfinite(s.fun).all():fits.append(s)
    if not fits:raise ValueError("候选优化未收敛")
    best=min(fits,key=lambda s:float(s.fun@s.fun))
    return {**unpack(best.x),"training_case_ids":[r["case"] for r in rows],
            "relative_RMSE":float(np.sqrt(np.mean(best.fun**2))),
            "relative_MAE":float(np.mean(abs(best.fun))),"relative_max":float(np.max(abs(best.fun))),
            "active_bounds":best.active_mask.astype(int).tolist(),
            "jacobian_rank":int(np.linalg.matrix_rank(best.jac)),"parameter_count":len(best.x),
            "A_is_unvalidated_straight_extrapolation":True}

def error_summary(values):
    v=np.asarray(values,float)
    if not len(v) or not np.isfinite(v).all():raise ValueError("误差数据不完整")
    return dict(n=len(v),MAE=float(np.mean(abs(v))),RMSE=float(np.sqrt(np.mean(v*v))),
                max_abs=float(np.max(abs(v))))

def kappa_cv(rows,kind):
    groups=staircase_members(rows);folds=[]
    for name,ids in groups.items():
        held=set(ids);training=[r for i,r in enumerate(rows) if i not in held]
        m=fit_kappa(training,kind)
        errs=[fitted_zs(m,rows[i])/rows[i]["circuit"]["zs_eff"]-1 for i in ids]
        folds.append(dict(held_group=name,training_case_ids=[r["case"] for r in training],
            held_case_ids=[rows[i]["case"] for i in ids],fit=m,errors_relative=errs,**error_summary(errs)))
    score=float(np.sqrt(np.mean([f["RMSE"]**2 for f in folds])))
    maximum=max(f["max_abs"] for f in folds)
    return dict(kind=kind,folds=folds,group_balanced_RMSE_relative=score,
                max_relative_error=maximum,within_1percent_every_point=maximum<=.01)

def length_features(row):
    d=dimensions(row)
    return np.array([1.,d["a_mm"],0. if d["g_mm"] is None else d["g_mm"]-.55])

def measured_delta(row):
    g=row["geometry_mm"]
    return chain.wave_length(g["Ws"],row["circuit"]["fs_GHz"],False)-dimensions(row)["L_centerline_mm"]

def base_delta(row):
    g=row["geometry_mm"];return chain.corrections(g["Wm"],g["Ws"],dimensions(row)["a_mm"])[1]

def fit_length(rows):
    x=np.array([length_features(r) for r in rows])
    if np.linalg.matrix_rank(x)<3:raise ValueError("单家族长度项不满秩")
    y=np.array([measured_delta(r)-base_delta(r) for r in rows])
    beta=np.linalg.lstsq(x,y,rcond=None)[0]
    return dict(delta_intercept_mm=float(beta[0]),delta_a_coefficient=float(beta[1]),
        g_minus_0p55_coefficient=float(beta[2]),training_case_ids=[r["case"] for r in rows],
        prior_Wm_coefficient=-.4017,prior_Ws_coefficient=-1.2118,
        residual_mm=error_summary(x@beta-y),width_coefficients_refitted=False)

def predicted_delta(model,row):
    beta=np.array([model["delta_intercept_mm"],model["delta_a_coefficient"],model["g_minus_0p55_coefficient"]])
    return float(base_delta(row)+length_features(row)@beta)

def predicted_fs(model,row):
    g=row["geometry_mm"];length=dimensions(row)["L_centerline_mm"]+predicted_delta(model,row)
    return float(brentq(lambda f:chain.wave_length(g["Ws"],f,False)-length,4,10))

def length_cv(rows):
    folds=[]
    for name,ids in staircase_members(rows).items():
        held=set(ids);train=[r for i,r in enumerate(rows) if i not in held];m=fit_length(train)
        errors=[1000*(predicted_fs(m,rows[i])-rows[i]["circuit"]["fs_GHz"]) for i in ids]
        folds.append(dict(held_group=name,training_case_ids=[r["case"] for r in train],
            held_case_ids=[rows[i]["case"] for i in ids],fit=m,errors_MHz=errors,**error_summary(errors)))
    maximum=max(f["max_abs"] for f in folds)
    return dict(folds=folds,group_balanced_RMSE_MHz=float(np.sqrt(np.mean([f["RMSE"]**2 for f in folds]))),
                max_abs_MHz=maximum,within_15MHz_every_point=maximum<=15.)

def straight_prior_zs(wm,ws):
    p=chain.nominal(wm,ws);n2=chain.ratios(p["Zm_ohm"],p["Zs_ohm"],0)[1]
    return n2*n2*p["Zs_ohm"]/50

def forward(g,topology,model):
    row=dict(geometry_mm=g,topology=topology)
    d=dimensions(row);n=chain.nominal(g["Wm"],g["Ws"]);a=d["a_mm"]
    n1=chain.ratios(n["Zm_ohm"],n["Zs_ohm"],a)[0]
    ref=model["reference_widths_mm"]
    ratio=straight_prior_zs(g["Wm"],g["Ws"])/straight_prior_zs(ref["Wm"],ref["Ws"])
    zs=fitted_zs(model["kappa"],row)*ratio;zm=n1*n1*n["Zm_ohm"]/50
    dm=chain.corrections(g["Wm"],g["Ws"],a)[0]
    fm=float(brentq(lambda f:chain.wave_length(g["Wm"],f)-g["Lm"]-dm,4,10))
    fs=predicted_fs(model["slot_length"],row)
    return dict(**n,N1=n1,N2=float(np.sqrt(zs*50/n["Zs_ohm"])),zm_eff=zm,zs_eff=zs,
                P_eff=zm*zs,R_eff=zm/zs,fm_GHz=fm,fs_GHz=fs,
                A_is_unvalidated_straight_extrapolation=True,
                cross_family_transfer_validated=False,lossless_equivalent_circuit_only=True,
                geometry_mm=dict(g),topology=topology)

def build(snapshot):
    if not snapshot["summary"]["count_conditions_met"]:
        raise ValueError("2a未结项或阶梯数量门槛未满足，不能冻结")
    rows=[r for r in snapshot["rows"] if eligible(r)]
    cv=[kappa_cv(rows,k) for k in KINDS]
    selected=min(cv,key=lambda v:(v["group_balanced_RMSE_relative"],KINDS.index(v["kind"])))
    model=dict(schema="R6-stage2a-model-v1",reference_widths_mm=REFERENCE_WIDTHS,
        kappa=fit_kappa(rows,selected["kind"]),slot_length=fit_length(rows),
        candidate_CV=cv,length_CV=length_cv(rows),selected_by="minimum group-balanced relative RMSE; E1/E2/E3 whole-group holdout",
        H1_measured_straight_ratio_validated=False,
        all_candidates_exceed_1percent=not any(r["within_1percent_every_point"] for r in cv),
        eligible_case_ids=[r["case"] for r in rows],excluded_case_ids=[r["case"] for r in snapshot["rows"] if not eligible(r)],
        old_N1_and_microstrip_length_coefficients_unchanged=True,
        evidence="单家族回顾性拟合；待冻结后的2b跨家族前瞻检验；不构成达标保证",
        fit_source_sha256=snapshot["source_sha256"],new_Analyze_requests=0,hook_messages=0)
    # Excluded straight/failed points are diagnostics only, never fitted.
    model["excluded_diagnostics"]=[]
    for r in snapshot["rows"]:
        if eligible(r):continue
        try:p=forward(r["geometry_mm"],r["topology"],model)
        except ValueError as e:model["excluded_diagnostics"].append(dict(case=r["case"],error=str(e)));continue
        model["excluded_diagnostics"].append(dict(case=r["case"],length_calibrated=r["length_calibrated"],
            predicted_zs=p["zs_eff"],extracted_zs=r["circuit"]["zs_eff"],
            relative_zs_error=p["zs_eff"]/r["circuit"]["zs_eff"]-1,
            fs_error_MHz=1000*(p["fs_GHz"]-r["circuit"]["fs_GHz"]),not_used_for_fitting=True))
    return model

def main():
    p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();x=assemble(a.root);m=build(x)
    a.out.mkdir(parents=True,exist_ok=False)
    for name,value in (("SNAPSHOT.json",x),("MODEL.json",m)):
        (a.out/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    files=[Path(__file__),Path(__file__).with_name("METHODS.md")]
    manifest={p.name:sha(p) for p in a.out.iterdir() if p.is_file()}
    manifest["source"]={p.relative_to(REPO).as_posix():sha(p) for p in files}
    (a.out/"MANIFEST.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(dict(selected=m["kappa"]["kind"],eligible=len(m["eligible_case_ids"]),
        model_sha256=sha(a.out/"MODEL.json"),all_candidates_exceed_1percent=m["all_candidates_exceed_1percent"],
        length_max_MHz=m["length_CV"]["max_abs_MHz"]),ensure_ascii=False))
if __name__=="__main__":main()
