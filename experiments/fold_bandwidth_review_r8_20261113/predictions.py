"""R8 审核方登记预测（回顾拟合，事后选的形式，只用来登记，不当作已验证规律）。离线，只读。"""
import json, pathlib
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
T = json.load(open(HERE / 'out/TIP_VS_ARM.json'))
pts = [p for p in T['points'] if p['g'] is not None]
# 用 3R 后的 12 点阶梯 + 阶段 2 的 g 阶梯；直槽单列
fam_Wm = {f: np.median([p['Wm'] for p in T['points'] if p['family'] == f]) for f in ('N04', 'N14', 'N08')}
plat = T['family_plateau_GHz']
W = np.array([fam_Wm[f] for f in ('N08', 'N14', 'N04')]); B = np.array([plat[f] for f in ('N08', 'N14', 'N04')])
quad = np.polyfit(W, B, 2); lin = np.polyfit(W, B, 1)
# 每个点的 Lc 与 Ws（3R 调准），用于估计新点的端头距离
def hinge(x, x0, k):
    return np.where(x < x0, k * (x0 - x), 0.0)
def fit_hinge(x, y, grid=np.arange(1.5, 4.01, 0.05)):
    best = None
    for x0 in grid:
        h = np.where(x < x0, x0 - x, 0.0)
        if h @ h == 0:
            continue
        k = float(h @ y / (h @ h)); r = float(np.sum((y - k * h) ** 2))
        if best is None or r < best[2]:
            best = (float(x0), k, r)
    return best
c = np.array([p['cost_MHz'] for p in pts])
clr = np.array([p['tip_line_clear'] for p in pts]); s = np.array([p['a'] + p['g'] for p in pts]); a = np.array([p['a'] for p in pts])
m_tip = fit_hinge(clr, c)
m_sum = fit_hinge(-s, c, -np.arange(1.5, 3.51, 0.05))   # 以 −(a+g) 为自变量：a+g 超过阈值才有代价
m_a = fit_hinge(-a, c, -np.arange(0.6, 2.81, 0.05))
rms = lambda m, x: float(np.sqrt(np.mean((c - hinge(x, m[0], m[1])) ** 2)))
out = dict(Wm=fam_Wm, plateau=plat, F_quad=quad.tolist(), F_lin=lin.tolist(),
           tip_model=dict(x0_mm=m_tip[0], k_MHz_per_mm=m_tip[1], rms_MHz=rms(m_tip, clr)),
           sum_model=dict(threshold_mm=-m_sum[0], k_MHz_per_mm=m_sum[1], rms_MHz=rms(m_sum, -s)),
           a_model=dict(threshold_mm=-m_a[0], k_MHz_per_mm=m_a[1], rms_MHz=rms(m_a, -a)), n=len(pts))
# 新点：Lc、Ws 按同家族 3R/1b 数据线性内插（a 方向），g 改变时 Lc 近似不变
new = json.load(open(HERE / 'out/R7_3R_RECOMPUTED.json'))
lad = json.load(open(HERE / 'out/LADDER.json'))
def lc_ws(fam, aa):
    xs = sorted((float(k), v) for k, v in lad[fam].items() if float(k) > 0)
    A = [x for x, _ in xs]; Ws = [v['Ws'] for _, v in xs]
    return float(np.interp(aa, A, Ws))
geo = {}
for p in T['points']:
    if p['g'] is not None:
        geo.setdefault(p['family'], []).append(p)
LC = {}
for r in new:
    if r['kind'] == 'EQ' and r['usable'] and r['Ls3']:
        LC.setdefault(r['family'], []).append((r['nominal_a'], r['Ls1'] + 2 * r['Ls2'] + 2 * r['Ls3'] - 4 * r['Ws']))
cands = [('N04', 1.0, 2.0), ('N14', 1.0, 2.0), ('N04', 2.4, 0.25), ('N14', 2.4, 0.25), ('N04', 2.4, 0.55),
         ('N08', 1.0, 0.55), ('Wm1.874', 1.8, 0.55), ('Wm2.06', 1.8, 0.55)]
pred = []
for fam, aa, gg in cands:
    base = fam if fam in LC else 'N04' if fam == 'Wm2.06' else 'N14'
    Wm = fam_Wm.get(fam) or float(fam[2:])
    ws = lc_ws(base if base in lad else 'N14', aa)
    lcs = sorted(LC[base]); lc = float(np.interp(aa, [x for x, _ in lcs], [y for _, y in lcs]))
    tip = lc - 4 * aa - 2 * gg - 4 * ws + 2 * ws  # Ls1 − 2Ls3 = Lc − 4a − 2g − 4Ws（见下）
    Ls1 = lc - 2 * aa - 2 * gg - 2 * ws; Ls3 = aa + ws; tip = Ls1 - 2 * Ls3
    clear = (tip - max(Wm, 1.82)) / 2
    F = float(np.polyval(quad, Wm)); Fl = float(np.polyval(lin, Wm))
    ct = float(hinge(np.array(clear), m_tip[0], m_tip[1])); cs = float(hinge(np.array(-(aa + gg)), m_sum[0], m_sum[1]))
    pred.append(dict(design=f'{fam}_a{aa}_g{gg}', Wm=Wm, a=aa, g=gg, Ws_est=ws, Lc_est=lc, tip_est=tip, tip_line_clear_est=clear,
                     plateau_quad=F, plateau_lin=Fl, cost_tip_MHz=ct, cost_sum_MHz=cs,
                     BW15_star_tip=F - ct / 1000, BW15_star_sum=F - cs / 1000))
out['predictions'] = pred
json.dump(out, open(HERE / 'out/R8_PREDICTIONS.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'predictions'}, indent=1))
for p in pred:
    print(f"{p['design']:20s} Ws~{p['Ws_est']:.3f} tip~{p['tip_est']:.2f} clr~{p['tip_line_clear_est']:.2f} F={p['plateau_quad']:.3f}/{p['plateau_lin']:.3f} costTip={p['cost_tip_MHz']:.0f} costSum={p['cost_sum_MHz']:.0f}")
