"""Materialize offline R1 evidence, exclusive output directories only."""
import argparse
from pathlib import Path
import numpy as np
import chain
from common import HERE, OLD, REPO, read, write, csvwrite, sha
from geometry import slot_boxes, compare_boxes
from test_r1 import synthetic_stage1
from analyze_stage1 import analyze


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for r in read(REPO/'model/DATASET.json')['rows']:
        old=chain.forward(r['geometry'],length_form='parameter_sum')
        new=chain.forward(r['geometry'],length_form='centerline')
        rows.append(dict(case=r['case'],fs_parameter_sum_GHz=old['fs_GHz'],fs_centerline_GHz=new['fs_GHz'],
                         absolute_difference_GHz=abs(new['fs_GHz']-old['fs_GHz'])))
    csvwrite(out/'LENGTH_EQUIVALENCE_80.csv',rows)
    write(out/'LENGTH_EQUIVALENCE_CHECK.json',dict(cases=80,tolerance_GHz=1e-9,
          max_abs_difference_GHz=max(r['absolute_difference_GHz'] for r in rows),
          passed=all(r['absolute_difference_GHz']<1e-9 for r in rows)))
    g=dict(Wm=1.91362018,Ws=.345967019,Lm=6.58449979,Ls1=12.6199947,
           Ls2=1.2419340379884205,Ls3=1.74596701899421)
    native=[dict(name=b['name'],parameters_mm={k:float(v.removesuffix('mm')) for k,v in b['parameters'].items()})
            for b in read(OLD/'audit_results/GEOMETRY_EVIDENCE.json')['blocks']]
    expected=slot_boxes(g)
    q=compare_boxes(expected,native)
    q.update(geometry_mm=g,expected=expected,native=native,
             evidence_file='experiments/fold_bandwidth_phase0_20261110/audit_results/GEOMETRY_EVIDENCE.json',
             evidence_sha256=sha(OLD/'audit_results/GEOMETRY_EVIDENCE.json'),
             max_abs_coordinate_difference_mm=max(abs(e['parameters_mm'][k]-n['parameters_mm'][k])
                 for e,n in zip(expected,native) for k in e['parameters_mm']),
             generated_new_HFSS_project=False)
    write(out/'INV01_BOX_COMPARISON.json',q)
    d=synthetic_stage1();write(out/'STAGE1_SYNTHETIC_INPUT.json',d)
    q=analyze(d);q['evidence']='SYNTHETIC ALGORITHM TEST; NOT HFSS';write(out/'STAGE1_SYNTHETIC_OUTPUT.json',q)
    # Store construction, results and propagation flags as reviewable evidence.
    from extract_run import power_metrics
    f=np.linspace(2,12,20);S=np.zeros((len(f),4,4),complex)
    S[:,:,0]=np.sqrt([.01,.04,.8,.05]);p=np.ones((len(f),4),bool)
    q=power_metrics(f,S[:,[0,2],0],S,p,'power_waves')
    write(out/'MODAL_POWER_SYNTHETIC.json',dict(label='SYNTHETIC NOT HFSS',
          construction='All S entries zero except first input column; squared magnitudes [0.01,0.04,0.80,0.05], real positive; all modes propagating.',
          expected_fundamental_unaccounted=.19,expected_all_mode_remaining=.10,output=q))
    print('offline evidence saved',out.name)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)
