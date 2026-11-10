"""Apply the R5 comparison gate to native full-mode exports; never start HFSS."""
import argparse
from pathlib import Path
import sys
import numpy as np
from headless_worker_r5 import REPO,HERE,read,write,sha,now,BASES
from review_headless import review

def compare_complex(f,native,archive_f,archive,lo,hi):
    if f.shape!=archive_f.shape or not np.allclose(f,archive_f,atol=1e-9,rtol=0):
        raise ValueError('Archive and native grids do not agree')
    if not (np.isfinite(native).all() and np.isfinite(archive).all() and lo<hi):
        raise ValueError('Nonfinite response or invalid archive main band')
    inside=(archive_f>=lo)&(archive_f<=hi)
    if not inside.any():raise ValueError('No sample in archive -15 dB passband')
    return np.max(abs(native[inside]-archive[inside]),axis=0).tolist()

def review_r5(root,case):
    if case not in BASES:raise ValueError('R5 baseline only')
    w=root/'runs'/case
    freeze=read(w/'input/freeze.json')
    cfg=read(root/'authorization_r5.json')
    if sha(root/'authorization_r5.json')!=freeze['authorization_sha256']:raise ValueError('Wrong authorization')
    for rel,h in {**cfg['code_hashes'],**freeze['source_hashes']}.items():
        if sha(REPO/rel)!=h:raise ValueError('Frozen file changed: '+rel)
    if sha(w/'native/full_modes.npz')!=read(w/'done.json')['native_sha256']:raise ValueError('Native data digest mismatch')
    review(w,w/'review')
    from extract_run import extract
    from analyze_stage1 import metrics_from_extraction
    source=freeze['design']['source_case']
    olddir=REPO/'data/raw'/source
    st=read(olddir/'state.json')
    if st['geometry']!=freeze['design']['geometry_mm']:raise ValueError('Not identical archive geometry')
    treatment=st['reference_treatment']
    if treatment['treatment']!='native_fundamental' or not treatment['no_conversion']:
        raise ValueError('Not comparable native archive reference')
    a=np.genfromtxt(olddir/'sparams.csv',delimiter=',',names=True,encoding='utf-8')
    f0=a['Freq_GHz'];z0=np.stack([a['S11_real']+1j*a['S11_imag'],a['S21_real']+1j*a['S21_imag']],axis=1)
    q0=extract(f0,z0,dict(case=source,geometry=st['geometry']))
    q=read(w/'review/extraction_R2.json')
    criteria=read(HERE/'STAGE1_CRITERIA_R5.json')
    band=q0['bandwidths']['BW15']
    lo,hi=band['main_component_GHz']
    with np.load(w/'native/full_modes.npz',allow_pickle=False) as data:
        ds11,ds21=compare_complex(data['f_GHz'],data['S'][:,[0,2],0],f0,z0,lo,hi)
    a,b=metrics_from_extraction(q0),metrics_from_extraction(q)
    record=read(w/'RUN_RECORD.json')
    dims={}
    for k in ('central_valley_GHz','BW15_GHz','BW20_GHz','inner_peak_low_dB','inner_peak_high_dB'):
        delta=None if a[k] is None or b[k] is None else b[k]-a[k]
        limit=criteria.get(k)
        dims[k]=dict(archive=a[k],redo=b[k],delta=delta,limit=limit,
                     passed=None if limit is None else delta is not None and abs(delta)<=limit+1e-12)
    mesh_ok=record['numerical_pass'] is True and criteria['mesh_cells'][0]<=record['mesh_cells']<=criteria['mesh_cells'][1] and record['delta_s']<=criteria['max_delta_s']
    pass_gate=bool(mesh_ok and read(w/'evidence/slot_comparison.json')['passed']
        and ds11<=criteria['max_complex_dS11'] and ds21<=criteria['max_complex_dS21']
        and all(v['passed'] is not False for v in dims.values()))
    prior=None
    if case==BASES[0]:
        cold=HERE/'headless_results'/case
        prior=dict(status=read(cold/'REVIEW.json'),metrics=metrics_from_extraction(read(cold/'extraction_R2.json')),
                   data_role='diagnostic only; excluded from training and stage1 noise')
    result=dict(at=now(),case=case,source=source,baseline_pass=pass_gate,numerical_pass=mesh_ok,design_pass=q['shape']['passed'],
        solve_completed=record['solve_completed'],Analyze_requests=record['Analyze_requested'],
        archive_mesh_cells=st['actual_elements'],archive_delta_s=st['convergence']['final_delta_s'],
        redo_mesh_cells=record['mesh_cells'],redo_delta_s=record['delta_s'],archive_BW15_band_GHz=[lo,hi],
        max_abs_dS11=ds11,max_abs_dS21=ds21,metrics=dims,prior_R4=prior,
        native_sha256=sha(w/'native/full_modes.npz'),criteria_sha256=sha(HERE/'STAGE1_CRITERIA_R5.json'))
    write(w/'review/REVIEW_R5.json',result)
    if not pass_gate:
        write(root/'STOP_R5.json',dict(at=now(),case=case,reason='R5 baseline comparison failed',review=result))
    print('R5 baseline',case,'pass',pass_gate,'mesh',record['mesh_cells'],'complex differences',ds11,ds21)
    return pass_gate

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('case',choices=BASES)
    a=p.parse_args();sys.exit(0 if review_r5(a.runtime,a.case) else 2)
