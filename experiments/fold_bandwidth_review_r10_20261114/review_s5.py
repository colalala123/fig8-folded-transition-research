"""R10 审核：独立复算 R9 阶段 5 全部几何（含 B1 密网格）。离线，只读，不启动 HFSS，不发消息。
阶段 5 数据在 codex 分支；用环境变量 S5_EXP 指向含 fold_bandwidth_r9_stage5_20261114 的 experiments 目录。"""
import json, os, pathlib, sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r7_20261113'))
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r8_20261113'))
from review_checks import load, usable
from review_3r import metrics
S5 = pathlib.Path(os.environ.get('S5_EXP', EXP)) / 'fold_bandwidth_r9_stage5_20261114'


def bw_at(f, s11, lvl, v):
    """包含中央谷 v 的连续 S11<=lvl 区间宽度（GHz）。"""
    i = int(np.argmin(abs(f - v)))
    if s11[i] > lvl:
        return None
    lo = i
    while lo > 0 and s11[lo - 1] <= lvl:
        lo -= 1
    hi = i
    while hi < len(f) - 1 and s11[hi + 1] <= lvl:
        hi += 1
    def x(a, b):
        return f[a] + (lvl - s11[a]) * (f[b] - f[a]) / (s11[b] - s11[a])
    return (x(hi, hi + 1) if hi < len(f) - 1 else f[hi]) - (x(lo, lo - 1) if lo > 0 else f[lo])


def cases():
    out = []
    for c in sorted((S5 / 'results').iterdir()):
        p = c / 'native/full_modes.csv'
        if not p.exists():
            continue
        d = json.load(open(c / 'INPUT.json', encoding='utf-8'))['design']
        g = d['geometry_mm']
        s = json.load(open(c / 'SUMMARY.json', encoding='utf-8'))
        rec, m = s['record'], (s.get('review') or {}).get('metrics') or {}
        r = dict(case=c.name, design=d.get('design'), a=d.get('nominal_a_mm'), g=d.get('g_mm'), **g,
                 mesh=rec['mesh_cells'], delta_s=rec['delta_s'], numerical_pass=rec['numerical_pass'], Analyze=rec['new_Analyze_requested'])
        r['clear'] = (g['Ls1'] - 2 * g['Ls3'] - max(g['Wm'], 1.82)) / 2
        r.update(metrics(*load(p)))
        r['usable'] = bool(r['three_valley'] and usable(r))
        f, s11 = load(p)[:2]
        if r['three_valley']:
            r['BW205'] = bw_at(np.asarray(f), np.asarray(s11), -20.5, r['valley_GHz'])
        if r['three_valley'] and m.get('inner_peak_low_dB') is not None:
            r['diff'] = dict(lo=r['peak_lo_dB'] - m['inner_peak_low_dB'], hi=r['peak_hi_dB'] - m['inner_peak_high_dB'],
                             valley=r['valley_GHz'] - m['central_valley_GHz'],
                             BW15=(r['BW15'] - m['BW15_GHz']) if r['BW15'] and m.get('BW15_GHz') else None,
                             BW20=(r['BW20'] - m['BW20_GHz']) if r['BW20'] and m.get('BW20_GHz') else None)
        out.append(r)
    return out


if __name__ == '__main__':
    rs = cases()
    json.dump(rs, open(HERE / 'out/S5_RECOMPUTED.json', 'w'), indent=1, default=float)
    dv = [r['diff'] for r in rs if 'diff' in r]
    print('n', len(rs), 'cross n', len(dv), {k: max((abs(x[k]) for x in dv if x[k] is not None), default=None) for k in dv[0]} if dv else None)
    print('mesh', min(r['mesh'] for r in rs), max(r['mesh'] for r in rs), 'maxdS', max(r['delta_s'] for r in rs),
          'Analyze', sum(r['Analyze'] for r in rs), max(r['Analyze'] for r in rs))
    for r in rs:
        print(f"{r['case']:18s} a={r['a']} g={r['g']} Wm={r['Wm']} Ws={r['Ws']:.4f} Lm={r['Lm']:.4f} Ls1={r['Ls1']:.3f} clr={r['clear']:.3f} use={r['usable']!s:5} v={r.get('valley_GHz')} "
              f"lo={r.get('peak_lo_dB', np.nan):.3f} hi={r.get('peak_hi_dB', np.nan):.3f} D={r.get('D_dB', np.nan):+.3f} L={r.get('peak_mean_dB', np.nan):.3f} BW15*={r.get('BW15_star') or np.nan:.4f} "
              f"BW20={r.get('BW20') or np.nan:.4f} S21min={r.get('S21_min_in_BW15_dB', np.nan):.3f}")
