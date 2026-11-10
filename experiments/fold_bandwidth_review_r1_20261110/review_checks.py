"""R1 review checks for the phase-0 audit. Offline only: numpy + csv + json.

Reads committed tables, writes one JSON. No HFSS, no network, no process calls.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PHASE0 = REPO / 'experiments' / 'fold_bandwidth_phase0_20261110'
sys.path.insert(0, str(PHASE0))
sys.path.insert(0, str(REPO / 'analysis'))
import chain  # noqa: E402

FEED_WIDTH = 1.82      # 50-ohm feed line width in hfss/INV01_A14.aedt (Substrate_4/5)
BOARD_HALF_X = 15.0    # substrate and air box span x = -15..15 mm
MIN_TIP_LINE = 0.813   # provisional, one substrate thickness
MIN_EDGE = 5.0         # provisional slot-end to board-edge margin
FS_TARGET = 6.588


def fit(x, y):
    c, *_ = np.linalg.lstsq(x, y, rcond=None)
    return c, float((y - x @ c).std())


def length_law():
    rows = list(csv.DictReader(open(REPO / 'experiments/fold_bandwidth_20261110/out/fold_table.csv')))
    col = lambda k: np.array([float(r[k]) for r in rows])
    wm, ws, l1, l2, l3, fs = (col(k) for k in ('Wm', 'Ws', 'Ls1', 'Ls2', 'Ls3', 'fs_GHz'))
    a = l3 - ws
    half = np.array([chain.wave_length(w, f, False) for w, f in zip(ws, fs)])
    out = {}
    for name, length in (('parameter_sum', l1 + 2*l2 + 2*l3), ('centreline', l1 + 2*l2 + 2*l3 - 4*ws)):
        d = half - length
        c4, sd4 = fit(np.c_[np.ones(len(d)), wm, ws, a], d)
        c3, sd3 = fit(np.c_[np.ones(len(d)), ws, a], d)
        phase = 180 * length / half
        out[name] = dict(
            half_wave_minus_length_mm=dict(mean=float(d.mean()), min=float(d.min()), max=float(d.max())),
            phase_deg_at_fs=dict(mean=float(phase.mean()), sd=float(phase.std(ddof=1))),
            coef_1_Wm_Ws_a=[round(float(v), 4) for v in c4], resid_sd_mm=sd4,
            coef_1_Ws_a=[round(float(v), 4) for v in c3], resid_sd_3p_mm=sd3)
    return out


def straight_prior(bases):
    out = []
    for b in bases:
        g = b['geometry']
        wm, ws = g['Wm'], g['Ws']
        half = chain.wave_length(ws, FS_TARGET, False)
        dl = 1.9644 - .4017*wm - 1.2118*ws          # centreline law at a = 0
        n = chain.nominal(wm, ws)
        n1, n2 = chain.ratios(n['Zm_ohm'], n['Zs_ohm'], 0.0)
        n1f, n2f = chain.ratios(n['Zm_ohm'], n['Zs_ohm'], 1.8)
        p0 = n['P'] * n1*n1 * n2*n2
        out.append(dict(family=b['family'], Wm=wm, Ws=ws,
                        half_wave_mm=round(half, 3), fold_law_a0_length_mm=round(half - dl, 3),
                        N2_a0_prior=round(n2, 4), N2_a1p8=round(n2f, 4),
                        zs_eff_ratio_a0_over_a1p8=round((n2/n2f)**2, 4),
                        P_eff_a0_prior=round(p0, 3), ripple_dB_a0_prior=round(chain.ripple_db(p0), 2),
                        slot_end_to_board_edge_mm=round(BOARD_HALF_X - (half - dl)/2, 3),
                        label='extrapolated prior, not a validated prediction'))
    return out


def regate():
    rows = list(csv.DictReader(open(PHASE0 / 'freeze/design_list.csv')))
    out, changed = [], []
    for r in rows:
        if r['topology'] != 'folded':
            continue
        wm, l1, l3 = float(r['Wm']), float(r['Ls1']), float(r['Ls3'])
        tip_line = (l1 - 2*l3 - max(wm, FEED_WIDTH)) / 2
        edge = BOARD_HALF_X - l1/2
        reasons = []
        if float(r['a_mm']) <= 0 or float(r['g_mm']) <= 0:
            reasons.append('nonpositive_arm_or_gap')
        if tip_line < MIN_TIP_LINE:
            reasons.append('tip_to_line_below_0p813')
        if edge < MIN_EDGE:
            reasons.append('slot_end_to_board_edge_below_5')
        rec = dict(id=r['id'], a=float(r['a_mm']), g=float(r['g_mm']), rho=round(float(r['rho']), 4),
                   tip_to_line_mm=round(tip_line, 3), slot_end_to_edge_mm=round(edge, 3),
                   r0_pass=r['screen_pass'] == 'True', r1_pass=not reasons, r1_reasons=reasons)
        out.append(rec)
        if rec['r0_pass'] != rec['r1_pass']:
            changed.append(rec)
    return dict(n_folded=len(out), n_r1_pass=sum(x['r1_pass'] for x in out), changed=changed,
                min_tip_to_line=min(out, key=lambda x: x['tip_to_line_mm']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=HERE / 'out_rerun')
    out = ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    bases = json.loads((PHASE0 / 'freeze/BASE_FAMILIES.json').read_text(encoding='utf-8'))['bases']
    res = dict(label='retrospective, descriptive; no new solver data',
               length_law=length_law(), straight_prior=straight_prior(bases), regate=regate())
    (out / 'REVIEW_CHECKS.json').write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
