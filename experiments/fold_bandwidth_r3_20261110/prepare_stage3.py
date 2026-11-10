"""R3-1 offline replacement registry. Old freezes are read only."""
import argparse
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import brentq

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
R2=REPO/'experiments/fold_bandwidth_r2_20261110'
sys.path.insert(0,str(R2))
import chain
from common import read,write,csvwrite,sha
from geometry import slot_boxes
from presubmit import presubmit


def build():
    p=brentq(lambda v:chain.ripple_db(v)+20.3,1.01,3)
    ref=read(REPO/'experiments/fold_bandwidth_review_r3_20261110/out/REVIEW_CHECKS.json')
    records=[];comparisons=[];superseded=[]
    for family,wm in [('N04',1.936496),('N14',1.810636)]:
        expected={r['a_mm']:r for r in ref['stage3_retarget']['families'][family]['new_target']}
        for j,a in enumerate([0.,.6,1.4,2.2,2.9]):
            def residual(ws):
                n=chain.nominal(wm,ws);n1,n2=chain.ratios(n['Zm_ohm'],n['Zs_ohm'],a)
                return n['P']*n1*n1*n2*n2-p
            ws=round(brentq(residual,.1,1),3)
            topology='straight_control' if a==0 else 'folded'
            if a==0:g=chain.straight(wm,ws)
            else:
                g=chain.base.lengths(wm,ws,a,.55)
                g['Lm']=round(g['Lm'],3);g['Ls1']=round(g['Ls1'],3)
            gate=presubmit(g,a,False,topology)
            if not gate['can_submit']:raise ValueError('Initial R3 screen failed')
            n=chain.nominal(wm,ws);n1,n2=chain.ratios(n['Zm_ohm'],n['Zs_ohm'],a)
            prior=chain.closed_band(p,n['Zm_ohm']/50*n1*n1,6.72,-20)
            original=f'S3_EQ_{family}_{j:02d}';new=f'S3R3_EQ_{family}_{j:02d}'
            values=dict(Ws=ws,Lm=g['Lm'],Ls1=g['Ls1'],prior_lossless_BW20_GHz=prior['BW_GHz'])
            comparisons.append(dict(id=new,family=family,a_mm=a,values=values,
                     expected={k:expected[a][k] for k in values},
                     max_difference=max(abs(v-expected[a][k]) for k,v in values.items()),
                     passed=all(np.isclose(v,expected[a][k],rtol=1e-9,atol=1e-12) for k,v in values.items())))
            for lossless in (False,True):
                suffix='_LOSSLESS' if lossless else ''
                rec=dict(id=new+suffix,supersedes=original+suffix,revision='R3',family=family,
                         geometry_mm=g.copy(),topology=topology,nominal_a_mm=a,actual_a_mm=a,
                         g_mm=None if a==0 else .55,material_role='PEC_tandelta0' if lossless else 'archived_lossy',
                         parent=new if lossless else None,conditional_on_parent_final_geometry=lossless,
                         target_inner_peak_mean_dB=-20.3,hard_inner_peak_max_dB=-20.,mean_inner_peak_min_dB=-20.6,
                         max_Analyze=1 if lossless else 3,screen=gate,
                         prior_equal_frequency_lossless_BW20_GHz=prior['BW_GHz'],
                         prior_model='R1 rounded law, fm=fs=6.72, target P before Ws quantization; not HFSS prediction',
                         quantized_geometry_predicted_ripple_dB=chain.ripple_db(n['P']*n1*n1*n2*n2),
                         boxes=slot_boxes(g,topology),
                         directory=('uniform_control/' if a==0 else 'runs/')+new+suffix+'/attempt_001',
                         solver_started=False)
                records.append(rec);superseded.append(dict(old_id=original+suffix,status='superseded_by_R3',new_id=rec['id'],old_record_preserved=True))
    return records,comparisons,superseded


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    rows,comparison,superseded=build()
    write(out/'REGISTRY_R3.json',dict(revision='R3',designs=rows,equal_ripple_count=10,lossless_count=10,
          unchanged_boundary_control_ids=['S3_BOUNDARY_N14_STRAIGHT','S3_BOUNDARY_N14_A18'],batch3_Analyze_limit=42,
          new_Analyze_requests=0))
    write(out/'SUPERSESSION.json',superseded)
    write(out/'TABLE_COMPARISON.json',dict(all_passed=all(r['passed'] for r in comparison),rows=comparison))
    csvwrite(out/'designs_r3.csv',[dict(id=r['id'],family=r['family'],topology=r['topology'],a_mm=r['actual_a_mm'],**r['geometry_mm'],
            prior_BW20_GHz=r['prior_equal_frequency_lossless_BW20_GHz'],parent=r['parent'],max_Analyze=r['max_Analyze']) for r in rows])
    write(out/'SLOT_BOXES_R3.json',[dict(id=r['id'],geometry_mm=r['geometry_mm'],topology=r['topology'],boxes=r['boxes']) for r in rows])
    write(out/'HASHES.json',dict(artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()},
          source_hashes={p.relative_to(REPO).as_posix():sha(p) for p in [Path(__file__),R2/'presubmit.py',R2/'chain.py',R2/'geometry.py',REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R3.md']}))
    print('R3 registry: 10 equal ripple + 10 conditional lossless; comparison passed:',all(r['passed'] for r in comparison))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)
