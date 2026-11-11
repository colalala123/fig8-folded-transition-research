"""阶段2长度调准的纯离线实现。无求解授权、无派发；不改P/R。"""
from pathlib import Path
import math
import sys
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r2_20261110'))
import chain
from presubmit import presubmit

FM_TARGET=6.622
FS_TARGET=6.588

def classify(q):
    s=q['shape']
    centre=s.get('central_valley_GHz');balance=s.get('peak_difference_dB')
    tuned=bool(s.get('shape_valid') and isinstance(centre,(int,float)) and math.isfinite(centre) and
        abs(centre-6.72)<=.03+1e-12 and isinstance(balance,(int,float)) and math.isfinite(balance) and balance<=.5+1e-12)
    unique=q['circuit'].get('extraction_nonunique') is False
    return dict(length_calibrated=tuned,equivalent_fit_unique_under_R2=unique,
        usable_for_law=tuned and unique,design_pass=s.get('passed'),
        note='阶段2调准指中央谷和内峰平衡，不要求固定宽度设计达到−20dB；等效电路多起点检查也单独记录。')

def propose(q,nominal_a,topology='folded'):
    status=classify(q);g=dict(q['geometry_mm'])
    if status['length_calibrated']:
        return dict(status=status,needs_solve=False,reason='already_length_calibrated')
    if not status['equivalent_fit_unique_under_R2']:
        return dict(status=status,needs_solve=False,reason='nonunique_circuit_no_unjustified_length_update')
    p=q['circuit']['parameters'];fm,fs=float(p['fm_GHz']),float(p['fs_GHz'])
    if not all(math.isfinite(x) and x>0 for x in (fm,fs)):raise ValueError('无效提取频率')
    dm=chain.wave_length(g['Wm'],fm)*(fm/FM_TARGET-1)
    ds=chain.wave_length(g['Ws'],fs,False)*(fs/FS_TARGET-1)
    candidate={**g,'Lm':round(g['Lm']+dm,3),'Ls1':round(g['Ls1']+ds,3)}
    if min(candidate['Lm'],candidate['Ls1'])<.01:
        return dict(status=status,needs_solve=False,reason='updated_length_below_minimum')
    screen=presubmit(candidate,nominal_a,tuning_changed=True,topology=topology)
    if not screen['can_submit']:
        return dict(status=status,needs_solve=False,reason='updated_geometry_failed_presubmit',screen=screen)
    new=screen['geometry_mm']
    if any(new[k]!=g[k] for k in ('Wm','Ws','Ls2')):raise AssertionError('固定宽度或间隔被改变')
    if new==g:
        return dict(status=status,needs_solve=False,reason='no_change_after_0p001mm_rounding',screen=screen)
    return dict(status=status,needs_solve=True,reason='R4_length_correction_then_R2_screen',
        previous_geometry_mm=g,geometry_mm=new,screen=screen,deltaLm_unrounded_mm=dm,
        deltaLs1_unrounded_mm=ds,targets_GHz=dict(fm=FM_TARGET,fs=FS_TARGET),
        actual_a_mm=screen['actual_a_mm'],prediction=chain.forward(new,topology),
        data_role='tuned_data',solver_started=False)
