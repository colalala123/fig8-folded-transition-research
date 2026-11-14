"""R9 审核：独立复算 R8 阶段 4 全部 18 个几何，并把可用点并入代价分析。离线，只读，不启动 HFSS，不发消息。"""
import json, pathlib, sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r7_20261113'))
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r8_20261113'))
from review_checks import load, usable
from review_3r import metrics
S4 = EXP / 'fold_bandwidth_r8_stage4_20261114'
S15, REF = 0.125, -20.3


def cases():
    out = []
    for c in sorted((S4 / 'results').iterdir()):
        p = c / 'native/full_modes.csv'
        if not p.exists():
            continue
        d = json.load(open(c / 'INPUT.json', encoding='utf-8'))['design']
        g = d['geometry_mm']
        s = json.load(open(c / 'SUMMARY.json', encoding='utf-8'))
        rec, m = s['record'], (s.get('review') or {}).get('metrics') or {}
        r = dict(case=c.name, design=d['design'], family=d['family'], a=d['nominal_a_mm'], g=d['g_mm'], **g,
                 mesh=rec['mesh_cells'], delta_s=rec['delta_s'], numerical_pass=rec['numerical_pass'], Analyze=rec['new_Analyze_requested'])
        r['tip'] = g['Ls1'] - 2 * g['Ls3']
        r['clear'] = (r['tip'] - max(g['Wm'], 1.82)) / 2
        r.update(metrics(*load(p)))
        r['usable'] = bool(r['three_valley'] and usable(r))
        if r['three_valley'] and m.get('inner_peak_low_dB') is not None:
            r['diff'] = dict(lo=r['peak_lo_dB'] - m['inner_peak_low_dB'], hi=r['peak_hi_dB'] - m['inner_peak_high_dB'],
                             valley=r['valley_GHz'] - m['central_valley_GHz'],
                             BW15=(r['BW15'] - m['BW15_GHz']) if r['BW15'] and m.get('BW15_GHz') else None,
                             BW20=(r['BW20'] - m['BW20_GHz']) if r['BW20'] and m.get('BW20_GHz') else None)
        out.append(r)
    return out


if __name__ == '__main__':
    rs = cases()
    json.dump(rs, open(HERE / 'out/S4_RECOMPUTED.json', 'w'), indent=1)
    dv = [r['diff'] for r in rs if 'diff' in r]
    print('n', len(rs), 'cross n', len(dv), {k: max((abs(x[k]) for x in dv if x[k] is not None), default=None) for k in dv[0]})
    print('mesh', min(r['mesh'] for r in rs), max(r['mesh'] for r in rs), 'maxdS', max(r['delta_s'] for r in rs),
          'Analyze', sum(r['Analyze'] for r in rs), max(r['Analyze'] for r in rs))
    for r in rs:
        print(f"{r['case']:13s} a={r['a']} g={r['g']} Wm={r['Wm']} Ws={r['Ws']} clr={r['clear']:.3f} use={r['usable']!s:5} v={r.get('valley_GHz')} "
              f"D={r.get('D_dB', np.nan):+.3f} L={r.get('peak_mean_dB', np.nan):.3f} BW15*={r.get('BW15_star') or np.nan:.4f} "
              f"BW20={r.get('BW20') or np.nan:.4f} S21min={r.get('S21_min_in_BW15_dB', np.nan):.3f}")
