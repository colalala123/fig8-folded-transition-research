"""生成E2阶段性报告。只读原始证据，输出目录必须新建；不派发求解。"""
import argparse,json,hashlib
from pathlib import Path
from gate import assemble
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def val(v):
    return "空" if v is None else f"{v:.6f}"

def generate(root,out):
    x=assemble(root)
    out.mkdir(parents=True,exist_ok=False)
    (out/"SNAPSHOT.json").write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[r for r in x["rows"] if r["case"]=="N14_A18" or (r.get("parent_id") or "").startswith("S2_E2_")]
    rows.sort(key=lambda r:r["actual_g_mm"])
    usable=[r for r in rows if r["length_calibrated"] and r["numerical_pass"] and r["fit_unique_under_R2"] and abs(r["actual_a_mm"]-1.8)<1e-8]
    lines=["# E2间隔阶梯阶段性结果","",
      "五个新增间隔设计已按每项最多三次的规程完成，其中四项长度调准，g=2.00 mm项三次后仍未调准。加上g=0.55的归档参考，严格a=1.8 mm的阶梯有五个可用位置，达到这一条阶梯的数量条件；当前仍需完成四个交叉设计和模型冻结，不能据此直接开始2b。","",
      "全部已完成尝试均通过数值检查。未调准是设计/调准规程结果，不是HFSS崩溃，也不能证明物理上不可达。","",
      "|算例|来源|实际a (mm)|g (mm)|中央谷(GHz)|内峰差(dB)|BW15(GHz)|BW20(GHz)|长度调准|",
      "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        lines.append("|"+"|".join([r["case"],"原归档" if r["source"]=="archive_reference" else "本轮",
          val(r["actual_a_mm"]),val(r["actual_g_mm"]),val(r["central_valley_GHz"]),val(r["peak_difference_dB"]),
          val(r["bandwidths"]["BW15"]["BW_GHz"]),val(r["bandwidths"]["BW20"]["BW_GHz"]),"是" if r["length_calibrated"] else "否"])+"|")
    if len(usable)>=2:
        lo,hi=usable[0],usable[-1]
        bw_change=(hi["bandwidths"]["BW15"]["BW_GHz"]-lo["bandwidths"]["BW15"]["BW_GHz"])*1000
        z_change=100*(hi["circuit"]["zs_eff"]/lo["circuit"]["zs_eff"]-1)
        lines+=["","## 当前观察与限制","",
          f"- 在a=1.8、线宽固定的这组已调准点上，g从{lo['actual_g_mm']:.2f}增至{hi['actual_g_mm']:.2f} mm，BW15变化{bw_change:.3f} MHz，提取的归一化槽阻抗变化{z_change:.3f}%。",
          "- 当前结果不支持把“g增大必然削弱弯折效应”作为已验证规律；需等交叉点和跨家族前瞻检验，不能强迫数据符合H7。",
          "- g=2.00的末次尝试因净距约束把a缩到1.756 mm，且三谷形状仍不合格；它不能计入a=1.8的固定折臂阶梯，也不能用S21带宽填补BW15/BW20空值。",
          "- g=1.20点中心6.69 GHz在边界、低频内峰距−20 dB仅约0.056 dB；名义长度调准不意味着设计/制造裕量。",
          "- 归档点允许作为阶梯已有参考，但没有冒充本轮新测；本轮N14基线与该归档BW15差约3.777 MHz已在阶段1报告。",
          "- 尚未完成无耗对照，不能把这些变化直接解释成辐射损耗变化。",
          "- 此报告没有冻结κ系数或2b预测，未增加任何求解、阈值或设计。"]
    lines+=["","图中实心圆为本轮，空心方块为原归档；仅绘制严格a=1.8且已调准、R2未标多解的点。"]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for r in usable:
        old=r["source"]=="archive_reference"
        style=dict(marker="s" if old else "o",facecolors="none" if old else "C0",edgecolors="C0")
        axes[0].scatter(r["actual_g_mm"],r["bandwidths"]["BW15"]["BW_GHz"],**style)
        axes[1].scatter(r["actual_g_mm"],r["circuit"]["zs_eff"],**style)
    for ax,label in zip(axes,["BW15 (GHz)","Extracted normalized slot impedance"]):
        ax.set(xlabel="Gap g (mm)",ylabel=label);ax.grid(alpha=.3)
    fig.suptitle("N14 fixed widths, actual a=1.8 mm; calibrated points only")
    fig.tight_layout();fig.savefig(out/"E2_OBSERVATIONS.png",dpi=150);plt.close(fig)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    (out/"MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(x["summary"]["stairs"]["E2"],ensure_ascii=False,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();generate(a.root.resolve(),a.out)
