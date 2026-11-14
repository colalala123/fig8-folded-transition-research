"""R9 登记预测：用冻结的五种代价模型（out/COST_REFIT.json）给阶段 5 规律设计的 BW15* 估计。
几何是粗估（Lc 按 N04 已有可用点对 a、g 线性回归），只用于登记区间；最终评分用实际调准几何代入同一冻结模型。离线。"""
import json, pathlib
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
M = json.load(open(HERE / 'out/COST_REFIT.json'))
pts = [p for p in M['points'] if abs(p['Wm'] - 1.936496) < 1e-3]


EXP = HERE.parent
old = json.load(open(EXP / 'fold_bandwidth_review_r7_20261113/out/ALL_GEOMETRIES.json'))
r7n = json.load(open(EXP / 'fold_bandwidth_review_r8_20261113/out/R7_3R_RECOMPUTED.json'))
s4 = json.load(open(HERE / 'out/S4_RECOMPUTED.json'))
GEO = {r['case']: r for r in old + r7n + s4}
rows = []
for p in pts:
    r = GEO[p['case']]
    rows.append((p['a'], p['g'], r['Ws'], r['Ls1'] + 2 * r['Ls2'] + 2 * r['Ls3'] - 4 * r['Ws']))
A = np.array([[1, a, g] for a, g, _, _ in rows]); y = np.array([x[3] for x in rows])
cL, *_ = np.linalg.lstsq(A, y, rcond=None)
cW, *_ = np.linalg.lstsq(A, np.array([x[2] for x in rows]), rcond=None)


def geom(Wm, a, g):
    Lc = cL @ [1, a, g]; Ws = cW @ [1, a, g]
    Ls1 = Lc - 2 * (a + g) - 2 * Ws; Ls2 = g + 2 * Ws; Ls3 = a + Ws
    tip = Ls1 - 2 * Ls3
    return dict(Wm=Wm, a=a, g=g, Ws=Ws, Lc=Lc, Ls1=Ls1, Ls2=Ls2, Ls3=Ls3, clr=(tip - max(Wm, 1.82)) / 2,
                rho=1 - Ls1 / (Ls1 + 2 * Ls2 + 2 * Ls3))


X = {'tip': lambda p: -p['clr'], 'sum': lambda p: p['a'] + p['g'], 'a': lambda p: p['a'], 'span': lambda p: -p['Ls1'], 'rho': lambda p: p['rho']}


def bw(v, m, p):
    k = -m['knee'] if m['variable'].startswith('-') else m['knee']
    return m['F_at_1p81'] + m['dF_dWm_GHz_per_mm'] * (p['Wm'] - 1.81) - m['slope_MHz_per_unit_x'] / 1000 * max(X[v](p) - k, 0)


DES = {'D1c': (1.936496, 1.0, 2.0), 'S1': (1.936496, 1.4, 1.6), 'S2': (1.936496, 2.2, 0.85),
       'ref_1.8_1.2': (1.936496, 1.8, 1.2), 'ref_2.6_0.55': (1.936496, 2.6, 0.55),
       'W1': (2.20, 1.8, 0.55), 'W2': (2.35, 1.8, 0.55), 'W3': (2.50, 1.8, 0.55)}
out = dict(Lc_fit=cL.tolist(), Ws_fit=cW.tolist(), designs={})
for d, (Wm, a, g) in DES.items():
    p = geom(Wm, a, g)
    out['designs'][d] = dict(geometry_estimate={k: round(float(v), 3) for k, v in p.items()},
                             BW15_star_GHz={v: round(float(bw(v, m, p)), 4) for v, m in M['models'].items()})
    print(d, {k: round(float(v), 2) for k, v in p.items() if k in ('Ls1', 'clr', 'rho', 'Ws')}, out['designs'][d]['BW15_star_GHz'])
json.dump(out, open(HERE / 'out/R9_PREDICTIONS.json', 'w'), indent=1)
