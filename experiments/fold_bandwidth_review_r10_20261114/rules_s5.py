"""R10 审核：阶段 5 的规律复核。离线，只读 out/S5_RECOMPUTED.json 和 R9 审核的 COST_REFIT.json，不启动 HFSS，不发消息。"""
import json, pathlib
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
R9 = HERE.parent / 'fold_bandwidth_review_r9_20261114'
rs = {r['case']: r for r in json.load(open(HERE / 'out/S5_RECOMPUTED.json'))}
models = json.load(open(R9 / 'out/COST_REFIT.json'))['models']
SEL = ['S5R9_W1__T2', 'S5R9_W2__T3', 'S5R9_D1c__T4', 'S5R9_D3c__T4', 'S5R9_S1__T3', 'S5R9_B1__T2', 'S5R9_B2__T3', 'S5R9_B3__T3']


def xval(v, r):
    L1, L2, L3 = r['Ls1'], r['Ls2'], r['Ls3']
    return {'tip': -r['clear'], 'sum': r['a'] + r['g'], 'a': r['a'], 'span': -L1, 'rho': 1 - L1 / (L1 + 2 * L2 + 2 * L3)}[v]


def pred(v, m, r):
    knee = -m['knee'] if v in ('tip', 'span') else m['knee']
    return m['F_at_1p81'] + m['dF_dWm_GHz_per_mm'] * (r['Wm'] - 1.81) - m['slope_MHz_per_unit_x'] / 1000 * max(xval(v, r) - knee, 0)


cost = {}
for v, m in models.items():
    e = {c: 1000 * (pred(v, m, rs[c]) - rs[c]['BW15_star']) for c in SEL}
    cost[v] = dict(err_pred_minus_actual_MHz=e, rms_5A=float(np.sqrt(np.mean([e[c] ** 2 for c in SEL[:5]]))),
                   rms_5A_plus_B=float(np.sqrt(np.mean([x ** 2 for x in e.values()]))))

# 同一形状、同一 Wm、中央谷都在 6.72 ± 0.01 GHz 的两点：BW20 随“最高内峰”变化的斜率
pairs = []
for a_, b_ in [('S5R9_W2__T3', 'S5R9_B1__T2'), ('S5R9_B2__T2', 'S5R9_B2__T3')]:
    A, B = rs[a_], rs[b_]
    ma, mb = max(A['peak_lo_dB'], A['peak_hi_dB']), max(B['peak_lo_dB'], B['peak_hi_dB'])
    pairs.append(dict(cases=[a_, b_], max_peak_dB=[ma, mb], BW20=[A['BW20'], B['BW20']],
                      MHz_BW20_per_dB_margin=1000 * (A['BW20'] - B['BW20']) / (ma - mb)))

wm = [(1.712, 6.058), (1.811, 6.214), (1.874, 6.263), (1.936, 6.332), (2.06, 6.495),
      (2.2, rs['S5R9_W1__T2']['BW15_star']), (2.35, rs['S5R9_W2__T3']['BW15_star'])]
x, y = np.array(wm).T
k, b0 = np.polyfit(x, y, 1)
out = dict(cost_models=cost, ripple_vs_BW20=pairs,
           wm_platform=dict(points=wm, slope_GHz_per_mm=k, rms_MHz=1000 * float(np.std(y - (k * x + b0))),
                            W3_unbalanced=dict(case='S5R9_W3__T3', BW15_star=rs['S5R9_W3__T3']['BW15_star'], valley=rs['S5R9_W3__T3']['valley_GHz'],
                                               linear_extrapolation=k * 2.5 + b0)),
           dense_vs_nominal_B1=dict(lo=rs['S5R9_B1dense__T1']['peak_lo_dB'] - rs['S5R9_B1__T2']['peak_lo_dB'],
                                    hi=rs['S5R9_B1dense__T1']['peak_hi_dB'] - rs['S5R9_B1__T2']['peak_hi_dB'],
                                    BW20_MHz=1000 * (rs['S5R9_B1dense__T1']['BW20'] - rs['S5R9_B1__T2']['BW20'])))
json.dump(out, open(HERE / 'out/S5_RULES.json', 'w'), indent=1, default=float)
for v, c in cost.items():
    print(f"{v:5s} rms5A={c['rms_5A']:5.1f} rms8={c['rms_5A_plus_B']:5.1f}", ' '.join(f"{e:+6.1f}" for e in c['err_pred_minus_actual_MHz'].values()))
for p in pairs:
    print(p['cases'], [round(z, 3) for z in p['max_peak_dB']], [round(z, 4) for z in p['BW20']], round(p['MHz_BW20_per_dB_margin'], 1))
print('Wm slope', round(k, 3), 'rms', round(out['wm_platform']['rms_MHz'], 1), 'W3', out['wm_platform']['W3_unbalanced'])
print('dense-nominal', out['dense_vs_nominal_B1'])
