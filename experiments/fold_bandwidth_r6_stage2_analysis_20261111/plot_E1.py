"""从只读快照重画E1图；输出目录必须是新目录。"""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def render(snapshot,out):
    x=json.loads(snapshot.read_text(encoding="utf-8-sig"))
    rows=[r for r in x["rows"] if r["topology"]=="folded" and
          (r["source"]=="archive_reference" or (r.get("parent_id") or "").startswith("S2_E1_")) and
          r["length_calibrated"] and r["numerical_pass"] and r["fit_unique_under_R2"]]
    out.mkdir(parents=True,exist_ok=False)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for r in sorted(rows,key=lambda r:r["actual_a_mm"]):
        old=r["source"]=="archive_reference"
        style=dict(marker="s" if old else "o",facecolors="none" if old else "C0",edgecolors="C0")
        axes[0].scatter(r["actual_a_mm"],r["bandwidths"]["BW15"]["BW_GHz"],**style)
        axes[1].scatter(r["actual_a_mm"],r["circuit"]["zs_eff"],**style)
    for ax,label in zip(axes,["BW15 (GHz)","Extracted normalized slot impedance"]):
        ax.set(xlabel="Actual folded arm a (mm)",ylabel=label);ax.grid(alpha=.3)
    fig.suptitle("N14 fixed widths, g=0.55 mm; calibrated points only")
    fig.tight_layout();fig.savefig(out/"E1_OBSERVATIONS.png",dpi=150);plt.close(fig)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("snapshot",type=Path);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();render(a.snapshot,a.out)
