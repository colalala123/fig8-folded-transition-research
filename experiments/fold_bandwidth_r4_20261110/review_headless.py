"""Offline R2 review of completed native exports; no solver calls or dispatch."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np
from headless_worker import REPO,read,write,sha,now

def review(w,out):
    if not (w/'done.json').exists():raise RuntimeError('Successful native export marker required')
    out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
    from extract_run import extract
    from analyze_stage1 import metrics_from_extraction
    m=read(w/'native/metadata.json');d=np.load(w/'native/full_modes.npz',allow_pickle=False)
    f,S=d['f_GHz'],d['S']
    # Explicitly do NOT invent propagating flags or a power-normalization claim.
    q=extract(f,S[:,[0,2],0],m)
    q['full_modal_export_available']=True
    q['full_modal_power_certified']=False
    q['modal_power_note']='All16S+4Zo+4Gamma preserved; normalization and propagation classification still need review.'
    q['input_sha256']=sha(w/'native/full_modes.npz')
    write(out/'extraction_R2.json',q)
    freeze=read(w/'input/freeze.json');source=freeze['design']['source_case']
    rows=read(REPO/'model/DATASET.json')['rows'];i=next(i for i,r in enumerate(rows) if r['case']==source)
    a=np.load(REPO/'model/dataset.npz',allow_pickle=False)
    old=extract(a['f'],a['Z'][i],rows[i]);oldmetrics=metrics_from_extraction(old);newmetrics=metrics_from_extraction(q)
    c=read(REPO/'experiments/fold_bandwidth_r1_20261110/STAGE1_CRITERIA.json')
    comparisons={}
    for k,limit in c['baseline_max_abs_difference'].items():
        x,y=oldmetrics[k],newmetrics[k]
        delta=None if x is None or y is None else y-x
        comparisons[k]=dict(archive=x,new=y,delta=delta,limit=limit,passed=delta is not None and abs(delta)<=limit+1e-12)
    record=read(w/'RUN_RECORD.json')
    status=dict(at=now(),case=m['case'],source_case=source,solve_completed=record['solve_completed'],
        numerical_pass=record['numerical_pass'],design_pass=q['shape'].get('passed'),
        archive_baseline_comparison_pass=all(x['passed'] for x in comparisons.values()),comparisons=comparisons,
        mesh_cells=record.get('mesh_cells'),delta_s=record.get('delta_s'),full_mode_power_certified=False,
        new_Analyze_requests=record['Analyze_requested'],result_level='nominal interpolated, not direct-frequency/manufacturing certification',
        scratch_isolation_pass=not (w/'evidence/scratch_isolation_discrepancy.json').exists())
    write(out/'REVIEW.json',status)
    for name in ['done.json','RUN_RECORD.json','owner.json','cleanup.json','supervised_start.json']:
        shutil.copyfile(w/name,out/name)
    shutil.copyfile(w/'native/full_modes.npz',out/'full_modes.npz')
    shutil.copyfile(w/'native/convergence.txt',out/'convergence.txt')
    shutil.copyfile(w/'native/mesh.txt',out/'mesh.txt')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,5))
    for arr,label in [(S[:,0,0],'S11'),(S[:,2,0],'S21')]:ax.plot(f,20*np.log10(np.maximum(abs(arr),1e-15)),label=label)
    ax.axhline(-20,color='gray',ls='--',lw=.8);ax.axhline(-2,color='gray',ls=':',lw=.8)
    ax.axvspan(3.92,9.52,color='green',alpha=.07);ax.set(xlim=(.01,15),ylim=(-60,3),xlabel='Frequency (GHz)',ylabel='Magnitude (dB)',title=m['case']+' | cold-start R4 baseline')
    ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(out/'S11_S21.png',dpi=150);plt.close(fig)
    print(json.dumps(status,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();review(a.run,a.out)
