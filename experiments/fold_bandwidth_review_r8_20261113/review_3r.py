"""R8 审核：独立复核 R7 3R。离线，只读已提交数据，不启动 HFSS，不发消息。"""
import json, pathlib, sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'experiments/fold_bandwidth_review_r7_20261113'))
from review_checks import load, shape, band, collect, usable
R7 = ROOT / 'experiments/fold_bandwidth_r7_3r_20261113'
S15, SREF, REF = 0.125, 0.19, -20.3
EXISTING = {'N04': {1.0: 'S2_E1_N04_a1.0__T1', 1.8: 'S1_BASE_N04'}, 'N14': {1.8: 'S1_WS_01', 2.2: 'S2_E1_N14_a2.2__T2'}}


def metrics(f, s11, s21):
    r = dict(three_valley=False)
    sh = shape(f, s11)
    if not sh:
        return r
    v, lo, hi = sh
    r.update(three_valley=True, valley_GHz=float(f[v]), valley_dB=float(s11[v]), peak_lo_dB=float(s11[lo]),
             peak_hi_dB=float(s11[hi]), peak_lo_GHz=float(f[lo]), peak_hi_GHz=float(f[hi]))
    r['D_dB'] = r['peak_hi_dB'] - r['peak_lo_dB']
    r['peak_mean_dB'] = (r['peak_lo_dB'] + r['peak_hi_dB']) / 2
    r['peak_max_dB'] = max(r['peak_lo_dB'], r['peak_hi_dB'])
    r['peak_gap_dB'] = abs(r['D_dB'])
    for n, t in (('BW15', -15.), ('BW20', -20.), ('BWref', r['peak_mean_dB'] + .3)):
        b = band(f, s11, t, lo, hi)
        r[n] = b[1] - b[0] if b else None
        r[n + '_edges'] = b
    b = r['BW15_edges']
    if b:
        m = (f >= b[0]) & (f <= b[1])
        r['S21_min_in_BW15_dB'] = float(s21[m].min())
    d = r['peak_mean_dB'] - REF
    r['BW15_star'] = r['BW15'] - S15 * d if r['BW15'] else None
    r['BWref_star'] = r['BWref'] - SREF * d if r['BWref'] else None
    r['BW15_star_range'] = sorted([r['BW15'] - s * d for s in (S15 - .015, S15 + .015)]) if r['BW15'] else None
    r['f_step_GHz'] = float(np.median(np.diff(f)))
    return r


def new_cases():
    out = []
    for c in sorted((R7 / 'results').iterdir()):
        p = c / 'native/full_modes.csv'
        if not p.exists():
            continue
        inp = json.load(open(c / 'INPUT.json', encoding='utf-8'))
        d = inp.get('design') or inp
        g = d['geometry_mm']
        summ = json.load(open(c / 'SUMMARY.json', encoding='utf-8'))
        rec = summ['record']
        r = dict(case=c.name, family=d.get('family'), kind=d.get('kind'), nominal_a=d.get('nominal_a_mm'),
                 material=d.get('material_role'), **g, mesh=rec.get('mesh_cells'), delta_s=rec.get('delta_s'),
                 numerical_pass=rec.get('numerical_pass'), Analyze=rec.get('new_Analyze_requested'))
        r['tip_distance_mm'] = g['Ls1'] - 2 * g['Ls3'] if g['Ls3'] else None
        r.update(metrics(*load(p)))
        r['usable'] = bool(r['three_valley'] and usable(r))
        m = (summ.get('review') or {}).get('metrics') or {}
        if r['three_valley'] and m.get('inner_peak_low_dB') is not None:
            r['diff_vs_codex'] = dict(lo=r['peak_lo_dB'] - m['inner_peak_low_dB'], hi=r['peak_hi_dB'] - m['inner_peak_high_dB'],
                                      BW15=(r['BW15'] - m['BW15_GHz']) if r['BW15'] and m.get('BW15_GHz') else None,
                                      valley=r['valley_GHz'] - m['central_valley_GHz'])
        out.append(r)
    return out


def ladder(new, old):
    by_old = {r['case']: r for r in old}
    lad = {}
    for fam in ('N04', 'N14'):
        pts = {}
        for a, c in EXISTING[fam].items():
            o = by_old[c]
            f, s11, s21 = None, None, None
            pts[a] = dict(case=c, role='retrospective', Ws=o['Ws'], **{k: o[k] for k in ('valley_GHz', 'D_dB', 'peak_mean_dB', 'BW15', 'BWref')})
            d = o['peak_mean_dB'] - REF
            pts[a].update(BW15_star=o['BW15'] - S15 * d, BWref_star=o['BWref'] - SREF * d, usable=bool(usable(o)))
        for r in new:
            if r['family'] == fam and r['kind'] == 'EQ' and r['usable'] and r['material'] == 'archived_lossy':
                a = r['nominal_a']
                if a not in pts or pts[a]['role'] != 'prospective':
                    pts[a] = dict(case=r['case'], role='prospective', Ws=r['Ws'],
                                  **{k: r[k] for k in ('valley_GHz', 'D_dB', 'peak_mean_dB', 'BW15', 'BWref', 'BW15_star', 'BWref_star', 'BW20', 'tip_distance_mm', 'S21_min_in_BW15_dB')}, usable=True)
        lad[fam] = dict(sorted(pts.items()))
    return lad


if __name__ == '__main__':
    out = HERE / 'out'; out.mkdir(exist_ok=True)
    new = new_cases()
    old = collect()
    lad = ladder(new, old)
    json.dump(new, open(out / 'R7_3R_RECOMPUTED.json', 'w'), indent=1)
    json.dump(lad, open(out / 'LADDER.json', 'w'), indent=1)
    dv = [r['diff_vs_codex'] for r in new if 'diff_vs_codex' in r]
    mx = lambda k: max(abs(x[k]) for x in dv if x[k] is not None)
    print('n', len(new), 'crosscheck n', len(dv), {k: mx(k) for k in ('lo', 'hi', 'BW15', 'valley')})
    print('mesh', min(r['mesh'] for r in new), max(r['mesh'] for r in new), 'maxdS', max(r['delta_s'] for r in new),
          'fstep', sorted({round(r.get('f_step_GHz', 0), 4) for r in new}))
    for r in new:
        print(f"{r['case']:28s} use={r['usable']!s:5} v={r.get('valley_GHz')} D={r.get('D_dB', float('nan')):+.3f} L={r.get('peak_mean_dB', float('nan')):.3f} "
              f"BW15={r.get('BW15') or float('nan'):.4f} BW20={r.get('BW20') or float('nan'):.4f} S21min={r.get('S21_min_in_BW15_dB', float('nan')):.3f} tip={r['tip_distance_mm']} Ws={r['Ws']} ds={r['delta_s']} mesh={r['mesh']}")
    for fam, p in lad.items():
        print(fam)
        for a, x in p.items():
            print(f"  a={a} {x['role'][:5]} {x['case']:24s} Ws={x['Ws']} BW15*={x['BW15_star']:.4f} BWref*={x['BWref_star']:.4f} D={x['D_dB']:+.3f} L={x['peak_mean_dB']:.3f} v={x['valley_GHz']}")
