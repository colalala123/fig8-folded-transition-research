"""R16 审核：独立复算 R15/R7 阶段 7 的 W4R T1/T2、C1W、W4R 密网格，并与 B1/B1R/W4 合并检验规律。
离线，只读，不启动 HFSS，不发消息。数据在 codex 分支；用环境变量 S7_EXP 指向其 experiments 目录。"""
import json, os, pathlib, sys
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
for p in ('fold_bandwidth_review_r7_20261113', 'fold_bandwidth_review_r8_20261113', 'fold_bandwidth_review_r10_20261114'):
    sys.path.insert(0, str(EXP / p))
from review_checks import load  # noqa: E402
from review_3r import metrics  # noqa: E402
SRC = pathlib.Path(os.environ.get('S7_EXP', EXP))
R7 = SRC / 'fold_bandwidth_r15_stage7_r7_20261116/results'
CASES = {k: R7 / f'S7R15_{k}' for k in ('W4R__T1', 'W4R__T2', 'C1W__T1', 'W4Rdense__T1')}
G = lambda db: 10 ** (db / 20)


def edges(f, s, valley, thr=-20.0):
    """含中央谷的连续 S11<=thr 主窗的两端（线性插值）。"""
    f, s = np.asarray(f), np.asarray(s)
    i = int(np.argmin(abs(f - valley)))
    lo = i
    while lo > 0 and s[lo - 1] <= thr:
        lo -= 1
    hi = i
    while hi < len(s) - 1 and s[hi + 1] <= thr:
        hi += 1
    if lo == 0 or hi == len(s) - 1:
        return None
    a = f[lo - 1] + (thr - s[lo - 1]) * (f[lo] - f[lo - 1]) / (s[lo] - s[lo - 1])
    b = f[hi] + (thr - s[hi]) * (f[hi + 1] - f[hi]) / (s[hi + 1] - s[hi])
    return float(a), float(b)


def one(d):
    f, s11 = load(d / 'native/full_modes.csv')[:2]
    r = dict(metrics(*load(d / 'native/full_modes.csv')))
    r['worst_peak_dB'] = max(r['peak_lo_dB'], r['peak_hi_dB'])
    r['edges20'] = edges(f, s11, r['valley_GHz'])
    m = (json.load(open(d / 'SUMMARY.json', encoding='utf-8')).get('review') or {}).get('metrics') or {}
    r['codex_diff'] = {k: (None if m.get(c) is None or r.get(k) is None else r[k] - m[c])
                       for k, c in (('peak_lo_dB', 'inner_peak_low_dB'), ('peak_hi_dB', 'inner_peak_high_dB'), ('BW20', 'BW20_GHz'))}
    r['design'] = json.load(open(d / 'INPUT.json', encoding='utf-8'))['design']
    return r


if __name__ == '__main__':
    R = {k: one(d) for k, d in CASES.items()}
    for k, r in R.items():
        print(f"{k:13s} valley {r['valley_GHz']:.3f} lo {r['peak_lo_dB']:.3f} hi {r['peak_hi_dB']:.3f} BW20 {r['BW20']} edges {r['edges20']} diff {r['codex_diff']}")
    n, c, dn = R['W4R__T2'], R['C1W__T1'], R['W4Rdense__T1']
    gN = max(G(n['peak_lo_dB']), G(n['peak_hi_dB']))
    out = dict(points=R)
    out['dGamma_corner'] = max(G(c['peak_lo_dB']), G(c['peak_hi_dB'])) - gN
    out['dGamma_mesh'] = dict(lo=G(dn['peak_lo_dB']) - G(n['peak_lo_dB']), hi=G(dn['peak_hi_dB']) - G(n['peak_hi_dB']),
                              worst=max(G(dn['peak_lo_dB']), G(dn['peak_hi_dB'])) - gN)
    out['corner_plus_mesh'] = max(G(c['peak_lo_dB']), G(c['peak_hi_dB'])) + max(0, out['dGamma_mesh']['worst'])
    # 下一步若再压浅纹波：W4R 实测余量换算成可放宽的 P_req
    out['corner_margin_Gamma'] = 0.1 - out['corner_plus_mesh']
    print(json.dumps({k: v for k, v in out.items() if k != 'points'}, indent=1, default=float))
    json.dump(out, open(HERE / 'out/S7_RECOMPUTED.json', 'w'), indent=1, default=float)
