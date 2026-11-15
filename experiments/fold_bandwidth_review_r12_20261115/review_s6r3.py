"""R12 审核：独立复算 R11/R3 阶段 6 的七个新点（P9c、P10–P14、N0），并与 P1–P9 合并分析灵敏度与机理。
离线，只读，不启动 HFSS，不发消息。数据在 codex 分支；用环境变量 S6_EXP 指向其 experiments 目录。"""
import json, os, pathlib, sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r11_20261115'))
import review_s6 as r6  # noqa: E402  复用 R11 的提取器与 P1–P9 路径
SRC = r6.SRC
NEW = SRC / 'fold_bandwidth_r11_stage6_r3_final_20261115/results'
DIRS = dict(r6.DIRS)
for k in ('P9c', 'P10', 'P11', 'P12', 'P13', 'P14', 'N0'):
    DIRS[k] = NEW / f'S6R10_{k}__T1'
PAIRS = {'Ws': ('P1', 'P2', 0.02), 'Lm': ('P3', 'P4', 0.02), 'Ls1': ('P5', 'P6', 0.02), 'Wm': ('P7', 'P8', 0.02),
         'etch': ('P9c', 'P10', 0.01), 'er': ('P12', 'P11', 0.05), 'h': ('P14', 'P13', 0.038)}  # (+侧, −侧, 步长)
EQ = ('N1', 'N2', 'P_eff', 'R_eff', 'fm_GHz', 'fs_GHz')


def one(k, d):
    try:
        r = r6.one(k, d)
    except (TypeError, KeyError):  # P13 无完整 −20 dB 主窗：BW20 为 None
        f, s11 = r6.load(d / 'native/full_modes.csv')[:2]
        r = dict(r6.metrics(*r6.load(d / 'native/full_modes.csv')))
        r['worst_peak_dB'] = max(r['peak_lo_dB'], r['peak_hi_dB'])
        r['codex_diff'] = None
    m = (json.load(open(d / 'SUMMARY.json', encoding='utf-8')).get('review') or {}).get('metrics') or {}
    r['eq'] = {q: m.get(q) for q in EQ}
    return r


if __name__ == '__main__':
    R = {k: one(k, d) for k, d in DIRS.items()}
    b = R['B1']
    bm = json.load(open(DIRS['B1'] / 'SUMMARY.json', encoding='utf-8'))
    b['eq'] = {q: ((bm.get('review') or {}).get('metrics') or {}).get(q) for q in EQ}
    print(f"{'pt':4s} {'valley':>6s} {'lo':>8s} {'hi':>8s} {'dlo':>7s} {'dhi':>7s} {'dWorst':>7s} {'BW20':>7s}  eq(N1,N2,P_eff,R_eff,fm,fs)")
    for k, r in R.items():
        bw = r.get('BW20')
        print(f"{k:4s} {r['valley_GHz']:6.3f} {r['peak_lo_dB']:8.3f} {r['peak_hi_dB']:8.3f} {r['peak_lo_dB']-b['peak_lo_dB']:+7.3f} "
              f"{r['peak_hi_dB']-b['peak_hi_dB']:+7.3f} {r['worst_peak_dB']-b['worst_peak_dB']:+7.3f} {bw if bw is None else round(bw,4)!s:>7s}  "
              + ' '.join('—' if v is None else f'{v:.4f}' for v in r['eq'].values()))
    diffs = [abs(v) for k, r in R.items() if k != 'B1' and r.get('codex_diff') for v in r['codex_diff'].values() if v is not None]
    print('max |codex diff|', max(diffs))
    out = dict(points=R, pairs={})
    for name, (p, m, step) in PAIRS.items():
        rp, rm = R[p], R[m]
        e = dict(step=step, half_lo=(rp['peak_lo_dB'] - rm['peak_lo_dB']) / 2, half_hi=(rp['peak_hi_dB'] - rm['peak_hi_dB']) / 2,
                 half_valley_MHz=1e3 * (rp['valley_GHz'] - rm['valley_GHz']) / 2,
                 curv_lo=(rp['peak_lo_dB'] + rm['peak_lo_dB']) / 2 - b['peak_lo_dB'],
                 curv_hi=(rp['peak_hi_dB'] + rm['peak_hi_dB']) / 2 - b['peak_hi_dB'],
                 worst_rise=max(rp['worst_peak_dB'], rm['worst_peak_dB']) - b['worst_peak_dB'],
                 half_eq={q: (None if rp['eq'][q] is None or rm['eq'][q] is None else (rp['eq'][q] - rm['eq'][q]) / 2) for q in EQ})
        out['pairs'][name] = e
        print(f"{name:5s} step {step}: half lo {e['half_lo']:+.3f} hi {e['half_hi']:+.3f} valley {e['half_valley_MHz']:+.0f} MHz "
              f"curv lo {e['curv_lo']:+.3f} hi {e['curv_hi']:+.3f} worst_rise {e['worst_rise']:+.3f}  "
              + ' '.join(f"{q}:{'—' if v is None else f'{v:+.4f}'}" for q, v in e['half_eq'].items()))
    # R10 第 3.3 节余量：三项现实来源取两侧较大升幅（下限 0）
    rise = {s: max(0.0, out['pairs'][s]['worst_rise']) for s in ('etch', 'er', 'h')}
    M = float(np.sqrt(sum(v * v for v in rise.values())))
    P_req = -20.0 - M - 0.256 - 0.1
    out['margin'] = dict(rise=rise, M=M, P_req=P_req, rule='P_req < -21.8 → 不做 B1R（R10 §3.4.5）')
    print('rise', {k: round(v, 3) for k, v in rise.items()}, 'M', round(M, 3), 'P_req', round(P_req, 3))
    # h 的作用是否经由微带阻抗？h −4.7% 在阻抗上约等于 Wm +0.1 mm（Q14 的依据）。用 Wm 实测斜率外推比较。
    wm = out['pairs']['Wm']
    k = 0.11 / 0.02
    out['h_vs_Wm_impedance'] = dict(Wm_equiv_mm=0.11, pred_from_Wm=dict(lo=k * wm['half_lo'], hi=k * wm['half_hi'], valley_MHz=k * wm['half_valley_MHz']),
                                   actual_P13=dict(lo=R['P13']['peak_lo_dB'] - b['peak_lo_dB'], hi=R['P13']['peak_hi_dB'] - b['peak_hi_dB'],
                                                   valley_MHz=1e3 * (R['P13']['valley_GHz'] - b['valley_GHz'])))
    print('h via Z0?', out['h_vs_Wm_impedance'])
    json.dump(out, open(HERE / 'out/S6R3_RECOMPUTED.json', 'w'), indent=1, default=float)
    # 规律检验（全部 16 个公差点，相对 B1）：两内峰均值只跟 P_eff 走，倾斜 D = hi − lo 只跟失谐 fm − fs 走。
    pts = [k for k in R if k != 'B1']
    dP = np.array([R[k]['eq']['P_eff'] - b['eq']['P_eff'] for k in pts])
    dmean = np.array([(R[k]['peak_lo_dB'] + R[k]['peak_hi_dB']) / 2 - (b['peak_lo_dB'] + b['peak_hi_dB']) / 2 for k in pts])
    ddet = np.array([1e3 * ((R[k]['eq']['fm_GHz'] - R[k]['eq']['fs_GHz']) - (b['eq']['fm_GHz'] - b['eq']['fs_GHz'])) for k in pts])
    dD = np.array([(R[k]['peak_hi_dB'] - R[k]['peak_lo_dB']) - (b['peak_hi_dB'] - b['peak_lo_dB']) for k in pts])

    def fit0(x, y):  # 过原点的一元线性
        s = float(x @ y / (x @ x)); res = y - s * x
        return s, 1 - float(res @ res) / float(y @ y), float(np.sqrt(np.mean(res ** 2)))
    sm, r2m, rm = fit0(dP, dmean)
    sd, r2d, rd = fit0(ddet, dD)
    out['laws'] = dict(points=pts, mean_vs_Peff=dict(slope_dB_per_unit=sm, R2=r2m, rms_dB=rm),
                       tilt_vs_detune=dict(slope_dB_per_MHz=sd, R2=r2d, rms_dB=rd),
                       rows={k: dict(dP_eff=float(p), dmean=float(m), detune_MHz=float(t), dD=float(d)) for k, p, m, t, d in zip(pts, dP, dmean, ddet, dD)})
    print(f'mean = {sm:.1f}·ΔP_eff  R2 {r2m:.3f} rms {rm:.3f} dB;  D = {sd:+.4f}·Δ(fm−fs)[MHz]  R2 {r2d:.3f} rms {rd:.3f} dB')
    # 余量的 |Γ| 口径：公差在反射系数上可加，dB 只是对数。B1R 越深，同样 Δ|Γ| 对应的 dB 升幅越大。
    g = lambda db: 10 ** (db / 20)
    gB = g(b['worst_peak_dB'])
    dG = {s: max(0.0, max(g(R[p]['worst_peak_dB']), g(R[m]['worst_peak_dB'])) - gB) for s, (p, m, _) in PAIRS.items() if s in ('etch', 'er', 'h')}
    G_rss = float(np.sqrt(sum(v * v for v in dG.values())))
    G_mesh = g(b['worst_peak_dB'] + 0.256) - gB
    G_tune = g(b['worst_peak_dB'] + 0.1) - gB
    G_req = 0.1 - G_rss - G_mesh - G_tune
    out['margin_gamma'] = dict(dGamma=dG, rss=G_rss, mesh=G_mesh, tune=G_tune, Gamma_req=G_req, P_req_dB=20 * np.log10(G_req))
    print('|Γ| margin', {k: round(v, 4) for k, v in dG.items()}, 'P_req(|Γ|) dB', round(20 * np.log10(G_req), 3))
    for tol in (0.025, 0.038, 0.051):  # h 公差按线性缩放（P13/P14 两侧近线性，曲率 0.16 dB）
        dGh = dG['h'] * tol / 0.038
        Gr = 0.1 - np.sqrt(dG['etch'] ** 2 + dG['er'] ** 2 + dGh ** 2) - G_mesh - G_tune
        out['margin_gamma'][f'P_req_h±{tol}'] = float(20 * np.log10(Gr))
        print(f'  h ±{tol}: P_req {20*np.log10(Gr):.2f} dB')
    Gr = 0.1 - np.sqrt(dG['etch'] ** 2 + dG['er'] ** 2 + (dG['h'] * 0.005 / 0.038) ** 2) - G_mesh - G_tune
    out['margin_gamma']['P_req_h_measured±0.005'] = float(20 * np.log10(Gr))
    print(f'  h 实测 ±0.005: P_req {20*np.log10(Gr):.2f} dB')
    json.dump(out, open(HERE / 'out/S6R3_RECOMPUTED.json', 'w'), indent=1, default=float)
