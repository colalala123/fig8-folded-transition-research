"""R9 审核：把阶段 4 可用点并入，重比五种长折臂代价模型（端头净距、a+g、a、槽跨度 Ls1、折叠比 rho）。
只用 a>=1.0 的等纹波可用点；R7 点拟合后外推到阶段 4 点；全部点拟合的系数作为 R9 登记模型冻结。离线。"""
import json, pathlib
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
tv = json.load(open(EXP / 'fold_bandwidth_review_r8_20261113/out/TIP_VS_ARM.json'))['points']
s4 = json.load(open(HERE / 'out/S4_RECOMPUTED.json'))
old = json.load(open(EXP / 'fold_bandwidth_review_r7_20261113/out/ALL_GEOMETRIES.json'))
r7n = json.load(open(EXP / 'fold_bandwidth_review_r8_20261113/out/R7_3R_RECOMPUTED.json'))
GEO = {r['case']: r for r in old + r7n + s4}
P = [dict(case=p['case'], src='R7', Wm=p['Wm'], a=p['a'], g=p['g'], clr=p['tip_line_clear'], y=p['BW15_star']) for p in tv if p['a'] >= 1.0]
P += [dict(case=r['case'], src='S4', Wm=r['Wm'], a=r['a'], g=r['g'], clr=r['clear'], y=r['BW15_star']) for r in s4 if r['usable'] and r['a'] >= 1.0]
for p in P:
    r = GEO[p['case']]
    p['Ls1'] = r['Ls1']
    p['rho'] = 1 - r['Ls1'] / (r['Ls1'] + 2 * r['Ls2'] + 2 * r['Ls3'])
X = {'tip': lambda p: -p['clr'], 'sum': lambda p: p['a'] + p['g'], 'a': lambda p: p['a'], 'span': lambda p: -p['Ls1'], 'rho': lambda p: p['rho']}


def design(pts, var, k):
    w = np.array([p['Wm'] - 1.81 for p in pts])
    h = np.array([max(X[var](p) - k, 0) for p in pts])
    return np.c_[np.ones(len(pts)), w, -h]


def fit(pts, var, grid):
    best = None
    y = np.array([p['y'] for p in pts])
    for k in grid:
        A = design(pts, var, k)
        c, *_ = np.linalg.lstsq(A, y, rcond=None)
        if c[2] < 0:
            continue
        e = float(np.sqrt(np.mean((A @ c - y) ** 2)))
        if best is None or e < best[0]:
            best = (e, k, c)
    return best


grids = {'tip': np.arange(-4.0, -1.0, 0.02), 'sum': np.arange(2.0, 3.2, 0.01), 'a': np.arange(1.4, 2.6, 0.01),
         'span': np.arange(-13.5, -10.0, 0.02), 'rho': np.arange(0.30, 0.50, 0.002)}
if __name__ == '__main__':
    out = dict(n=len(P), points=P, models={})
    for v in X:
        e, k, c = fit(P, v, grids[v])
        loo = []
        for i in range(len(P)):
            b = fit(P[:i] + P[i + 1:], v, grids[v])
            loo.append(float((design([P[i]], v, b[1]) @ b[2])[0] - P[i]['y']))
        # 只用 R7 点拟合、对 S4 点外推
        r7 = [p for p in P if p['src'] == 'R7']
        b7 = fit(r7, v, grids[v])
        s4e = {p['case']: round(float((design([p], v, b7[1]) @ b7[2])[0] - p['y']) * 1000, 1) for p in P if p['src'] == 'S4'}
        knee = -k if v in ('tip', 'span') else k
        out['models'][v] = dict(variable={'tip': '-tip_line_clearance_mm', 'sum': 'a+g_mm', 'a': 'a_mm', 'span': '-Ls1_mm', 'rho': '1-Ls1/(Ls1+2Ls2+2Ls3)'}[v], form='BW15* = F + dF*(Wm-1.81) - slope*max(x-knee_x,0)', knee=round(float(knee), 3), slope_MHz_per_unit_x=round(float(c[2]) * 1000, 1), F_at_1p81=round(float(c[0]), 4),
                                dF_dWm_GHz_per_mm=round(float(c[1]), 3), rms_MHz=round(e * 1000, 1),
                                loo_rms_MHz=round(float(np.sqrt(np.mean(np.square(loo)))) * 1000, 1),
                                r7_only_fit_error_on_S4_MHz=s4e,
                                r7_only_rms_on_S4_excl_D5_MHz=round(float(np.sqrt(np.mean([v_ ** 2 for c_, v_ in s4e.items() if 'D5' not in c_]))), 1))
        print(v, out['models'][v])
    json.dump(out, open(HERE / 'out/COST_REFIT.json', 'w'), indent=1)
