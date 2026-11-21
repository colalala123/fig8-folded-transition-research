"""R17 审核：独立复算 R16/R8 阶段 8（C2W、C3W、W5R T1–T3、C1W5），合并阶段 7 求五曲线保证带，
并离线回放 W5R 的调参器，找出 T3 与 T2 重复的原因，给出 R9（顺序割线）的参考 T4。
离线，只读，不启动 HFSS，不发消息。数据在 codex 分支；用环境变量 S8_EXP 指向其 experiments 目录
（阶段 7 与阶段 8 两个目录都要在里面）。回放会导入该目录下阶段 8 的 tuning.py（纯离线模块）。"""
import hashlib, json, os, pathlib, sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r16_20261116'))
for p in ('fold_bandwidth_review_r7_20261113', 'fold_bandwidth_review_r8_20261113', 'fold_bandwidth_review_r10_20261114'):
    sys.path.insert(0, str(EXP / p))
import review_s7 as r16  # noqa: E402  (edges, one)
SRC = pathlib.Path(os.environ.get('S8_EXP', EXP))
S7 = SRC / 'fold_bandwidth_r15_stage7_r7_20261116/results'
S8DIR = SRC / 'fold_bandwidth_r16_stage8_r8_20261121'
S8 = S8DIR / 'results'
CASES = {'W4R': S7 / 'S7R15_W4R__T2', 'W4Rdense': S7 / 'S7R15_W4Rdense__T1', 'C1W': S7 / 'S7R15_C1W__T1',
         'C2W': S8 / 'S8R16_C2W__T1', 'C3W': S8 / 'S8R16_C3W__T1',
         'W5R_T1': S8 / 'S8R16_W5R__T1', 'W5R_T2': S8 / 'S8R16_W5R__T2', 'W5R_T3': S8 / 'S8R16_W5R__T3',
         'C1W5': S8 / 'S8R16_C1W5__T1'}
G = lambda db: 10 ** (db / 20)
TARGET = np.array([6.74, 0.0, -22.79507702516665])   # R16 policy nominal_target
B1_LINEAR_MHz = {'C1W': (-62, None), 'C2W': (58, -209), 'C3W': (103, -80)}   # R16 第 1 节
DELTA_MESH = 0.002336


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def delivery_err(r):
    """R8 的交付误差：max(|谷−6.74|/0.01, |D|/0.2, max|峰−目标|/0.1)。"""
    return max(abs(r['valley_GHz'] - TARGET[0]) / .01, abs(r['peak_hi_dB'] - r['peak_lo_dB']) / .2,
               max(abs(r['peak_lo_dB'] - TARGET[2]), abs(r['peak_hi_dB'] - TARGET[2])) / .1)


def replay():
    """用阶段 8 自己的 tuning.py 回放 W5R：冻结的 R8 规则 vs 顺序割线（force_sequential，R9 拟用）。"""
    sys.path.insert(0, str(S8DIR))
    import tuning
    fz = json.load(open(S8DIR / 'freeze/R16_R8.json', encoding='utf-8'))
    req = fz['margin']['P_req_dB']
    def hist(cs):
        out = []
        for c in cs:
            w = S8 / f'S8R16_W5R__{c}'
            out.append(dict(case=f'S8R16_W5R__{c}', q=json.load(open(w / 'review/extraction_R2.json', encoding='utf-8')),
                            tuning=json.load(open(w / 'INPUT.json', encoding='utf-8'))['design'].get('tuning'), measurement={}))
        return out
    res = {}
    for label, cs, force in (('R8_frozen_T1T2', ['T1', 'T2'], False), ('R9_sequential_T1T2', ['T1', 'T2'], True),
                             ('R9_sequential_T1T2T3', ['T1', 'T2', 'T3'], True)):
        s = tuning.propose_history(hist(cs), 1.8, 'folded', target=TARGET.tolist(), force_sequential=force,
                                   peak_window=[req - .2, req])
        res[label] = {k: s.get(k) for k in ('needs_solve', 'base_case', 'geometry_mm', 'predicted_y', 'step_scale', 'J', 'actual_step')}
    h = hist(['T1', 'T2'])
    x = [tuning.coordinate(r['q']['geometry_mm'], 'folded') for r in h]
    y = [tuning.state(r['q']) for r in h]
    dx, dy = x[1] - x[0], y[1] - y[0]
    res['T1_to_T2'] = dict(dx_Lm_Lc_Ws=dx.tolist(), dy_actual=dy.tolist(), dy_pred_J0=(dx @ tuning.J0).tolist(),
                           R8_trigger_rule='only D/mean with |pred|>0.3 and |err|>0.5|pred|; valley row never updated')
    res['J0'] = tuning.J0.tolist()
    res['P_req_dB'] = req
    return res, tuning


def bw_gradient():
    """B1 实测半差（每 0.02 mm）换到调参坐标 [Lm, Lc, Ws]（Lc = Ls1 + 2Ws + 常数，跟随规则下）。"""
    pr = json.load(open(EXP / 'fold_bandwidth_review_r11_20261115/out/S6_RECOMPUTED.json'))['pairs']
    lm, ls1, ws = (pr[k]['half_BW20_MHz'] / 0.02 for k in ('Lm', 'Ls1', 'Ws'))
    return np.array([lm, ls1, ws - 2 * ls1])   # MHz/mm


if __name__ == '__main__':
    R = {k: r16.one(d) for k, d in CASES.items()}
    for k, r in R.items():
        print(f"{k:9s} valley {r['valley_GHz']:.3f} lo {r['peak_lo_dB']:.3f} hi {r['peak_hi_dB']:.3f} BW20 {r['BW20']:.4f} "
              f"edges {tuple(round(e, 5) for e in r['edges20']) if r['edges20'] else None} diff {r['codex_diff']}")
    out = dict(points={k: {kk: vv for kk, vv in r.items() if kk != 'design'} for k, r in R.items()},
               geometry={k: r['design']['geometry_mm'] for k, r in R.items()},
               cad={k: {kk: r['design']['cad_ir'].get(kk) for kk in ('er', 'h_mm', 'etch_e_mm')} for k, r in R.items()})
    # 1) W4R 五曲线保证带与带边移动
    five = ['W4R', 'W4Rdense', 'C1W', 'C2W', 'C3W']
    lo = max(R[k]['edges20'][0] for k in five); hi = min(R[k]['edges20'][1] for k in five)
    n = R['W4R']['edges20']
    shifts = {k: [1000 * (R[k]['edges20'][0] - n[0]), 1000 * (R[k]['edges20'][1] - n[1])] for k in five[1:]}
    resid = {k: [None if p is None else shifts[k][i] - p for i, p in enumerate(B1_LINEAR_MHz[k])] for k in B1_LINEAR_MHz}
    out['W4R_guarantee'] = dict(low_GHz=lo, high_GHz=hi, width_GHz=hi - lo,
                                lower_limiter=max(five, key=lambda k: R[k]['edges20'][0]),
                                upper_limiter=min(five, key=lambda k: R[k]['edges20'][1]))
    out['W4R_edge_shift_MHz'] = shifts
    out['B1_linear_residual_MHz'] = resid
    # 2) T3 是否与 T2 逐字节重复
    t2, t3 = R['W5R_T2']['design'], R['W5R_T3']['design']
    a2, a3 = (np.genfromtxt(CASES[k] / 'native/full_modes.csv', delimiter=',', skip_header=1) for k in ('W5R_T2', 'W5R_T3'))
    s2, s3 = (20 * np.log10(np.hypot(a[:, 1], a[:, 2])) for a in (a2, a3))
    out['T3_duplicate'] = dict(same_geometry=t2['geometry_mm'] == t3['geometry_mm'], same_cad_ir=t2['cad_ir'] == t3['cad_ir'],
                               byte_identical_csv=sha(CASES['W5R_T2'] / 'native/full_modes.csv') == sha(CASES['W5R_T3'] / 'native/full_modes.csv'),
                               max_abs_S_entry_diff=float(np.abs(a2 - a3).max()), max_abs_dS11_dB=float(np.abs(s2 - s3).max()),
                               note='same inputs; re-solve differs only by numerical noise, so T3 carries no new information')
    # 3) C1W5（在 T1 上）
    gT1 = max(G(R['W5R_T1']['peak_lo_dB']), G(R['W5R_T1']['peak_hi_dB']))
    gC = max(G(R['C1W5']['peak_lo_dB']), G(R['C1W5']['peak_hi_dB']))
    out['C1W5'] = dict(dGamma_corner=gC - gT1, Gamma_plus_borrowed_mesh=gC + DELTA_MESH,
                       edge_shift_vs_T1_MHz=[1000 * (R['C1W5']['edges20'][i] - R['W5R_T1']['edges20'][i]) for i in (0, 1)])
    out['delivery_err'] = {k: delivery_err(R[k]) for k in ('W5R_T1', 'W5R_T2')}
    # 4) 调参器回放与带宽梯度
    rp, tuning = replay()
    out['replay'] = rp
    g = bw_gradient()
    out['BW_gradient_MHz_per_mm_Lm_Lc_Ws'] = g.tolist()
    t12 = np.array(rp['T1_to_T2']['dx_Lm_Lc_Ws'])
    out['BW_check_T1_to_T2_MHz'] = dict(pred=float(g @ t12), actual=1000 * (R['W5R_T2']['BW20'] - R['W5R_T1']['BW20']))
    T4 = rp['R9_sequential_T1T2']['geometry_mm']
    x1 = tuning.coordinate(R['W5R_T1']['design']['geometry_mm'], 'folded'); x4 = tuning.coordinate(T4, 'folded')
    dbw4 = float(g @ (x4 - x1)); out['T4_reference'] = dict(geometry_mm=T4, predicted_y=rp['R9_sequential_T1T2']['predicted_y'],
                                                            predicted_BW20_GHz=R['W5R_T1']['BW20'] + dbw4 / 1000)
    # 调准流形上的“压深代价”：谷与 D 不变、两峰均值变浅 1 dB 时 BW 的变化
    Js = np.array(rp['R9_sequential_T1T2']['J'])
    for name, J in (('J0_B1', tuning.J0), ('J_W5R_secant', Js)):
        d = np.linalg.solve(J.T, np.array([0., 0., 1.]))
        out.setdefault('manifold_BW_per_dB_shallower_MHz', {})[name] = dict(step_mm_Lm_Lc_Ws=d.tolist(), BW_MHz=float(g @ d))
    # 5) W5R 保证带估算：T4 预测名义带边（按 T1 带边平移 ΔBW 的一半）+ W4R 实测带边移动
    e1 = R['W5R_T1']['edges20']; e4 = (e1[0] - dbw4 / 2000, e1[1] + dbw4 / 2000)
    est = [(e4[0] + shifts[k][0] / 1000, e4[1] + shifts[k][1] / 1000) for k in five[1:]] + [e4]
    out['W5R_guarantee_estimate'] = dict(nominal_edges_assumed=e4, low_GHz=max(a for a, _ in est), high_GHz=min(b for _, b in est),
                                         width_GHz=min(b for _, b in est) - max(a for a, _ in est),
                                         basis='T4 predicted BW split evenly + W4R measured edge shifts (additivity transfer)')
    # 6) R9 放宽中央谷窗（6.73–6.76，目标仍 6.74）后的基点误差：中央谷项 = 到窗口的距离 / 0.01
    def err_r9(r):
        v = r['valley_GHz']; dv = max(0.0, 6.73 - v, v - 6.76)
        return max(dv / .01, abs(r['peak_hi_dB'] - r['peak_lo_dB']) / .2,
                   max(abs(r['peak_lo_dB'] - TARGET[2]), abs(r['peak_hi_dB'] - TARGET[2])) / .1)
    out['delivery_err_R9_window'] = {k: err_r9(R[k]) for k in ('W5R_T1', 'W5R_T2')}
    # 7) W6R/W7R 的 T1：调准路径线性外推。W4R、W5R* 都用雅可比换到准确目标，再 2·W5R' − W4R'。
    #    这里假设 W5R* = T4 且正好落在预测上（W6R* 同理落在 W6R 参考上），只作参考尺寸。
    x_of = lambda gm: tuning.coordinate(gm, 'folded')
    gW4R = R['W4R']['design']['geometry_mm']; yW4R = np.array([R['W4R'][k] for k in ('valley_GHz', 'D_dB', 'peak_mean_dB')])
    yW4R[1] = R['W4R']['peak_hi_dB'] - R['W4R']['peak_lo_dB']
    def to_geom(x, ref, wm):
        xr = x_of(ref); ws = round(float(x[2]), 3)
        ls1 = round(float(ref['Ls1'] + (x[1] - xr[1]) - 2 * (x[2] - xr[2])), 3)
        return dict(Wm=wm, Ws=ws, Lm=round(float(x[0]), 3), Ls1=ls1, Ls2=round(2 * ws + .55, 3), Ls3=round(ws + 1.8, 3))
    yT1 = np.array([R['W5R_T1']['valley_GHz'], R['W5R_T1']['peak_hi_dB'] - R['W5R_T1']['peak_lo_dB'], R['W5R_T1']['peak_mean_dB']])
    ref5 = json.load(open(S8DIR / 'freeze/R16_R8.json', encoding='utf-8'))['T1_derivation']['W5R']['reference_geometry_mm']
    ext = {}
    for name, J in (('J_W5R_secant', Js), ('J0_B1', tuning.J0)):
        w4c = x_of(gW4R) + np.linalg.solve(J.T, TARGET - yW4R)
        w5c = x4 + np.linalg.solve(J.T, TARGET - np.array(rp['R9_sequential_T1T2']['predicted_y']))
        w6 = 2 * w5c - w4c; g6 = to_geom(w6, T4, 2.95)
        w7 = 2 * x_of(g6) - w5c; g7 = to_geom(w7, g6, 3.10)
        ext[name] = dict(W4R_to_target_step_Lm_Lc_Ws=(w4c - x_of(gW4R)).tolist(), tuned_width_step_Lm_Lc_Ws=(w5c - w4c).tolist(),
                         W6R_T1_reference=g6, W7R_T1_reference=g7,
                         R16_width_step_bias_at_W5R_T1=(yT1 - J.T @ (x1 - x_of(ref5)) - yW4R).tolist())
    ext['R16_fixed_width_step_Lm_Lc_Ws'] = [-0.029, 0.100 + 2 * 0.069, 0.069]
    out['width_extrapolation'] = ext
    print(json.dumps({k: v for k, v in out.items() if k not in ('points', 'geometry', 'cad', 'replay')}, indent=1, default=float))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'J'} if isinstance(v, dict) else v
                      for k, v in rp.items() if k != 'J0'}, indent=1, default=float))
    json.dump(out, open(HERE / 'out/S8_RECOMPUTED.json', 'w'), indent=1, default=float)
