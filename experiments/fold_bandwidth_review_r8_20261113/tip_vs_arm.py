"""R8 回顾分析：等纹波带宽代价跟折臂长 a、间隔 g、端头距离哪个更相关。离线，只读。"""
import json, pathlib
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
old = json.load(open(HERE.parents[0] / 'fold_bandwidth_review_r7_20261113/out/ALL_GEOMETRIES.json'))
new = json.load(open(HERE / 'out/R7_3R_RECOMPUTED.json'))
S15, REF = 0.125, -20.3
pts = []
for r in old + [x for x in new if x['material'] == 'archived_lossy' and x['kind'] == 'EQ']:
    if not r.get('three_valley') or r['peak_gap_dB'] > 0.6 or abs(r['valley_GHz'] - 6.72) > 0.035 or not r.get('BW15'):
        continue
    if abs(r['peak_mean_dB'] - REF) > 1.0:
        continue
    a = r['Ls3'] - r['Ws'] if r['Ls3'] else 0.0
    g = r['Ls2'] - 2 * r['Ws'] if r['Ls2'] else None
    tip = r['Ls1'] - 2 * r['Ls3'] if r['Ls3'] else None
    pts.append(dict(case=r['case'], family=r['family'], Wm=r['Wm'], a=round(a, 3), g=None if g is None else round(g, 3),
                    Ws=r['Ws'], tip=tip, tip_line_clear=None if tip is None else (tip - max(r['Wm'], 1.82)) / 2,
                    L=r['peak_mean_dB'], D=r['D_dB'], BW15=r['BW15'], BW15_star=r['BW15'] - S15 * (r['peak_mean_dB'] - REF)))
fam_ref = {}
for f in ('N04', 'N14', 'N08'):
    pl = [p['BW15_star'] for p in pts if p['family'] == f and p['g'] == 0.55 and 0.6 <= p['a'] <= 2.2]
    fam_ref[f] = float(np.median(pl)) if pl else None
for p in pts:
    p['cost_MHz'] = (fam_ref[p['family']] - p['BW15_star']) * 1000 if fam_ref[p['family']] else None
pts.sort(key=lambda p: (p['family'], p['g'] or -1, p['a']))
json.dump(dict(family_plateau_GHz=fam_ref, points=pts), open(HERE / 'out/TIP_VS_ARM.json', 'w'), indent=1)
print(fam_ref)
for p in pts:
    print(f"{p['family']} a={p['a']:<5} g={p['g']!s:<5} tip={p['tip'] and round(p['tip'],2)!s:<6} clr={p['tip_line_clear'] and round(p['tip_line_clear'],2)!s:<5} L={p['L']:.2f} D={p['D']:+.2f} BW15*={p['BW15_star']:.3f} cost={p['cost_MHz'] and round(p['cost_MHz'])} {p['case']}")
