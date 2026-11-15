"""R11 审核：独立复算 R10 阶段 6 已完成的 P1–P9（相对 B1 T2 名义点）。离线，只读，不启动 HFSS，不发消息。
数据在 codex 分支；用环境变量 S6_EXP 指向含 fold_bandwidth_r10_stage6_r1/r2 与 r9_stage5 的 experiments 目录。"""
import json, os, pathlib, sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r7_20261113'))
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r8_20261113'))
sys.path.insert(0, str(EXP / 'fold_bandwidth_review_r10_20261114'))
from review_checks import load
from review_3r import metrics
from review_s5 import bw_at
SRC = pathlib.Path(os.environ.get('S6_EXP', EXP))
DIRS = {'B1': SRC / 'fold_bandwidth_r9_stage5_20261114/results/S5R9_B1__T2'}
for i in range(1, 9):
    DIRS[f'P{i}'] = SRC / f'fold_bandwidth_r10_stage6_r1_20261115/results/S6R10_P{i}__T1'
DIRS['P9'] = SRC / 'fold_bandwidth_r10_stage6_r2_20261115/results/S6R10_P9__T1'
PAIRS = {'Ws': ('P1', 'P2'), 'Lm': ('P3', 'P4'), 'Ls1': ('P5', 'P6'), 'Wm': ('P7', 'P8')}


def one(k, d):
    f, s11 = load(d / 'native/full_modes.csv')[:2]
    r = dict(metrics(*load(d / 'native/full_modes.csv')))
    r['BW205'] = bw_at(np.asarray(f), np.asarray(s11), -20.5, r['valley_GHz'])
    r['worst_peak_dB'] = max(r['peak_lo_dB'], r['peak_hi_dB'])
    inp = json.load(open(d / 'INPUT.json', encoding='utf-8'))['design']
    r['perturbation'], r['signed_change'] = inp.get('perturbation'), inp.get('signed_change')
    if k != 'B1':
        m = (json.load(open(d / 'SUMMARY.json', encoding='utf-8')).get('review') or {}).get('metrics') or {}
        r['codex_diff'] = dict(lo=r['peak_lo_dB'] - m['inner_peak_low_dB'], hi=r['peak_hi_dB'] - m['inner_peak_high_dB'],
                               BW20=r['BW20'] - m['BW20_GHz'])
    return r


if __name__ == '__main__':
    R = {k: one(k, d) for k, d in DIRS.items()}
    b = R['B1']
    out = dict(points=R, pairs={})
    print(f"{'pt':4s} {'pert':10s} {'chg':>6s} {'valley':>6s} {'lo':>8s} {'hi':>8s} {'dlo':>7s} {'dhi':>7s} {'dWorst':>7s} {'BW20':>7s} {'dBW20':>7s}")
    for k, r in R.items():
        print(f"{k:4s} {str(r['perturbation']):10s} {str(r['signed_change']):>6s} {r['valley_GHz']:6.3f} {r['peak_lo_dB']:8.3f} {r['peak_hi_dB']:8.3f} "
              f"{r['peak_lo_dB']-b['peak_lo_dB']:+7.3f} {r['peak_hi_dB']-b['peak_hi_dB']:+7.3f} {r['worst_peak_dB']-b['worst_peak_dB']:+7.3f} "
              f"{r['BW20']:7.4f} {1e3*(r['BW20']-b['BW20']):+7.1f}")
    for name, (p, m) in PAIRS.items():
        rp, rm = R[p], R[m]
        e = dict(half_lo=(rp['peak_lo_dB'] - rm['peak_lo_dB']) / 2, half_hi=(rp['peak_hi_dB'] - rm['peak_hi_dB']) / 2,
                 half_valley_MHz=1e3 * (rp['valley_GHz'] - rm['valley_GHz']) / 2,
                 curv_lo=(rp['peak_lo_dB'] + rm['peak_lo_dB']) / 2 - b['peak_lo_dB'],
                 curv_hi=(rp['peak_hi_dB'] + rm['peak_hi_dB']) / 2 - b['peak_hi_dB'],
                 worst_rise=max(rp['worst_peak_dB'], rm['worst_peak_dB']) - b['worst_peak_dB'],
                 half_BW20_MHz=1e3 * (rp['BW20'] - rm['BW20']) / 2)
        out['pairs'][name] = e
        print(name, {k: round(v, 3) for k, v in e.items()})
    print('max |codex diff|', max(abs(v) for k, r in R.items() if k != 'B1' for v in r['codex_diff'].values()))
    json.dump(out, open(HERE / 'out/S6_RECOMPUTED.json', 'w'), indent=1, default=float)
    # P9（过蚀刻）= P1 + P5 + P4 + P8 + 未测项（Ls2 −0.02 即 g −0.02；馈线 1.82→1.80）。用单项实测差做线性叠加，看可加性。
    terms = ['P1', 'P5', 'P4', 'P8']
    sup = {k: sum(R[t][k] - b[k] for t in terms) for k in ('peak_lo_dB', 'peak_hi_dB', 'valley_GHz', 'BW20')}
    act = {k: R['P9'][k] - b[k] for k in sup}
    out['etch_superposition'] = dict(terms=terms, predicted=sup, actual=act, residual={k: act[k] - sup[k] for k in sup},
                                     note='残差 = 未测项（g −0.02、馈线 −0.02）+ 非可加性 + 网格噪声')
    print('P9 superposition pred', {k: round(v, 3) for k, v in sup.items()}, 'actual', {k: round(v, 3) for k, v in act.items()})
    json.dump(out, open(HERE / 'out/S6_RECOMPUTED.json', 'w'), indent=1, default=float)
