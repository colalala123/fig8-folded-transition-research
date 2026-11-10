"""R3 审核复核：离线，只读已提交的表格和 R1 的规律链。不启动 HFSS，不发消息。

用法：python experiments/fold_bandwidth_review_r3_20261110/review_checks.py [--out DIR]
"""
import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
TABLE = EXP / 'fold_bandwidth_20261110' / 'out' / 'fold_table.csv'
R1 = EXP / 'fold_bandwidth_r1_20261110'
WEEKLY = dict(R_start=0.825, R_end=0.910, BW_start_GHz=7.16, BW_end_GHz=6.92, arm_increase_mm=0.6)


def weekly_check():
    """07-25 周报的 4 个弯折点：带宽随 R 的变化，与归档 80 条的两种趋势比较。"""
    rows = list(csv.DictReader(TABLE.open(encoding='utf-8')))
    bw = np.array([float(r['bw_S21_2dB']) for r in rows])
    a = np.array([float(r['a_mm']) for r in rows])
    r_nom = np.array([float(r['zm_nominal']) / float(r['zs_nominal']) for r in rows])
    r_eff = np.array([float(r['R_eff']) for r in rows])
    dln = float(np.log(WEEKLY['R_end'] / WEEKLY['R_start']))
    across = {}
    for name, rr in (('nominal_R', r_nom), ('circuit_R_eff', r_eff)):
        for label, sel in (('a=1.4', a == 1.4), ('a=1.8', a == 1.8)):
            x = np.log(rr[sel])
            slope = float(np.polyfit(x, bw[sel], 1)[0])
            across[f'{name}, {label}'] = dict(n=int(sel.sum()), slope_GHz_per_lnR=slope,
                                              correlation=float(np.corrcoef(x, bw[sel])[0, 1]),
                                              BW_change_for_weekly_R_change_MHz=slope * dln * 1000)
    fam = {}
    for r in rows:
        if r['source'] == 'original48':
            fam.setdefault(r['family'], {})[float(r['a_mm'])] = r
    pairs = [v for v in fam.values() if 1.4 in v and 1.8 in v]
    d_ln = [float(np.log(float(v[1.8]['R_eff']) / float(v[1.4]['R_eff']))) for v in pairs]
    d_bw = [(float(v[1.8]['bw_S21_2dB']) - float(v[1.4]['bw_S21_2dB'])) * 1000 for v in pairs]
    scale = WEEKLY['arm_increase_mm'] / 0.4
    return dict(
        evidence='retrospective, descriptive; archived 80 curves only; the 4 weekly points are not in this repository',
        weekly=dict(**WEEKLY, dlnR=dln, BW_change_MHz=(WEEKLY['BW_end_GHz'] - WEEKLY['BW_start_GHz']) * 1000,
                    slope_GHz_per_lnR=(WEEKLY['BW_end_GHz'] - WEEKLY['BW_start_GHz']) / dln),
        across_designs_widths_vary=across,
        fixed_width_pairs_a14_to_a18=dict(n=len(pairs), dlnR_eff_mean=float(np.mean(d_ln)),
                                          dlnR_eff_range=[min(d_ln), max(d_ln)],
                                          dBW_S21_mean_MHz=float(np.mean(d_bw)), dBW_S21_range_MHz=[min(d_bw), max(d_bw)],
                                          linear_scaling_to_weekly_arm_increase=dict(
                                              dlnR_eff=float(np.mean(d_ln)) * scale, dBW_S21_MHz=float(np.mean(d_bw)) * scale,
                                              share_of_weekly_R_change=float(np.mean(d_ln)) * scale / dln)),
        caveat='R conventions differ (weekly: uniform-model label; here: nominal ratio and circuit fit), so only relative changes are compared.')


def stage3_retarget(aim=-20.3):
    """阶段 3 的等纹波设计：纹波目标从 -21 dB 改为 aim 之后的初值和净距筛选。"""
    sys.path.insert(0, str(R1))
    spec = importlib.util.spec_from_file_location('r1_chain', R1 / 'chain.py')
    chain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chain)

    def design(wm, a, target):
        p = brentq(lambda q: chain.ripple_db(q) - target, 1.01, 3)

        def fun(ws):
            n = chain.nominal(wm, ws)
            n1, n2 = chain.ratios(n['Zm_ohm'], n['Zs_ohm'], a)
            return n['P'] * n1 * n1 * n2 * n2 - p
        ws = round(brentq(fun, .1, 1), 3)
        n = chain.nominal(wm, ws)
        n1, _ = chain.ratios(n['Zm_ohm'], n['Zs_ohm'], a)
        band = chain.closed_band(p, n['Zm_ohm'] / 50 * n1 * n1, 6.72, -20)
        if a == 0:
            g, topo = chain.straight(wm, ws), 'straight_control'
        else:
            g, topo = chain.base.lengths(wm, ws, a, .55), 'folded'
            g['Lm'], g['Ls1'] = round(g['Lm'], 3), round(g['Ls1'], 3)
        s = chain.geometry_screen(g, topo, 15.)
        return dict(a_mm=a, target_dB=target, Ws=ws, Lm=g['Lm'], Ls1=g['Ls1'],
                    prior_lossless_BW20_GHz=band['BW_GHz'], tip_to_line_mm=s.get('tip_to_line_x_mm'),
                    tip_to_tip_mm=s.get('tip_to_tip_x_mm'), screen_pass=s['screen_pass'], reasons=s['reasons'])

    out = {}
    for name, wm in (('N04', 1.936496), ('N14', 1.810636)):
        out[name] = dict(Wm=wm, old_target=[design(wm, a, -21.) for a in (0, .6, 1.4, 2.2, 3.0)],
                         new_target=[design(wm, a, aim) for a in (0, .6, 1.4, 2.2, 3.0, 2.9)])
    w = [design(1.810636, 1.4, t)['prior_lossless_BW20_GHz'] for t in (-21., -20.)]
    return dict(evidence='uncalibrated prior from the R1 chain; lossless circuit; not an HFSS prediction',
                aim_dB=aim, BW20_change_per_dB_of_ripple_MHz=(w[1] - w[0]) * 1000, families=out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=HERE / 'out_rerun')
    out = ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    result = dict(weekly_report_check=weekly_check(), stage3_retarget=stage3_retarget())
    (out / 'REVIEW_CHECKS.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(result['weekly_report_check'], ensure_ascii=False, indent=1))
    for name, fam in result['stage3_retarget']['families'].items():
        for d in fam['new_target']:
            print(name, d['a_mm'], d['Ws'], d['Lm'], d['Ls1'], round(d['prior_lossless_BW20_GHz'], 3), d['tip_to_line_mm'], d['screen_pass'])
    print(result['stage3_retarget']['BW20_change_per_dB_of_ripple_MHz'])
