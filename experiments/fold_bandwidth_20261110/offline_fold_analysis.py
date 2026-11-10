"""Offline-only retrospective fold analysis on the frozen 80-run archive.

No solver, no network, no notification. Reads model/dataset.npz and model/DATASET.json,
never writes into model/, data/ or results/. Needs only numpy and scipy.

    python experiments/fold_bandwidth_20261110/offline_fold_analysis.py [--out DIR]

Default DIR is out_rerun/ next to this file, so the committed out/ is never overwritten.

Evidence label for everything this script produces: RETROSPECTIVE, DESCRIPTIVE, development
data only (78 development + 2 retrospective holdout geometries). Fold arm a has two levels
(1.4, 1.8 mm) and gap g is fixed at 0.55 mm in this archive, so nothing here is a fitted law
for other a or g. Not a prospective test, not a certificate.
"""
import argparse, csv, json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import brentq, least_squares

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'analysis'))
from line_models import microstrip, slotline  # noqa: E402

C = 299.792458  # mm*GHz
ER = 3.55
F0 = 6.72


def circuit(fr, zm, zs, fm, fs):
    """Paper Fig. 2(b): series open microstrip stub, two shunt shorted slot stubs, series open stub."""
    z1 = -1j * zm / np.tan(np.pi / 2 * fr / fm)
    y = -2j / (zs * np.tan(np.pi / 2 * fr / fs))
    a = 1 + z1 * y
    b = z1 * (2 + z1 * y)
    den = 2 * a + b + y
    return (b - y) / den, 2 / den


def fit_circuit(f, s11_abs, zm0, zs0):
    win = (f >= 2.0) & (f <= 11.5)
    fr, target = f[win], s11_abs[win]
    sol = least_squares(lambda p: np.abs(circuit(fr, *p)[0]) - target, [zm0, zs0, F0, F0],
                        bounds=([0.3, 0.5, 4, 4], [3, 6, 10, 10]))
    return sol.x, float(np.sqrt(np.mean(sol.fun ** 2)))


def level_f(db):
    r = 10 ** (db / 10)
    return np.sqrt(r / (1 - r))


def bw_closed(p_eff, zm_eff, f0, db):
    """Width of the band where the lossless circuit (fm = fs = f0) has |S11| <= db."""
    if p_eff <= 1:
        return float('nan')
    big_f = level_f(db)
    u = brentq(lambda v: (v ** 3 - (p_eff - 1) * v) / p_eff - big_f, np.sqrt(p_eff - 1), 50)
    return 2 * f0 * (1 - 2 * np.arctan(zm_eff / u) / np.pi)


def band_at(f, y, lim, f0=F0):
    """Contiguous interval containing f0 where y <= lim; linear interpolation at the edges."""
    i0 = int(np.argmin(abs(f - f0)))
    if y[i0] > lim:
        return float('nan'), float('nan')
    i = i0
    while i > 0 and y[i - 1] <= lim:
        i -= 1
    lo = f[i] if i == 0 else f[i - 1] + (lim - y[i - 1]) * (f[i] - f[i - 1]) / (y[i] - y[i - 1])
    j = i0
    while j < len(f) - 1 and y[j + 1] <= lim:
        j += 1
    hi = f[j] if j == len(f) - 1 else f[j] + (lim - y[j]) * (f[j + 1] - f[j]) / (y[j + 1] - y[j])
    return float(lo), float(hi)


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def stats(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    return dict(n=int(len(v)), mean=float(v.mean()), sd=float(v.std(ddof=1)), min=float(v.min()), max=float(v.max()),
                n_positive=int((v > 0).sum()), n_negative=int((v < 0).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(HERE / 'out_rerun'))
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    d = np.load(REPO / 'model' / 'dataset.npz')
    z, f = d['Z'], d['f']
    rows = json.loads((REPO / 'model' / 'DATASET.json').read_text(encoding='utf-8-sig'))['rows']
    table = []
    for i, r in enumerate(rows):
        g = r['geometry']
        zm_nom = microstrip(ER, g['Wm'])['Z_ohm'] / 50
        zs_nom = slotline(ER, g['Ws'])['Z_ohm'] / 50
        (zm, zs, fm, fs), rms = fit_circuit(f, np.abs(z[i, :, 0]), zm_nom, zs_nom)
        s11 = 20 * np.log10(np.abs(z[i, :, 0]))
        s21 = 20 * np.log10(np.abs(z[i, :, 1]))
        lpath = g['Ls1'] + 2 * g['Ls2'] + 2 * g['Ls3']
        fold = 2 * (g['Ls2'] + g['Ls3'])
        half_wave = C / (2 * fs * np.sqrt(slotline(ER, g['Ws'], f=fs)['eeff']))
        rem = 1 - np.abs(z[i, :, 0]) ** 2 - np.abs(z[i, :, 1]) ** 2
        lo15, hi15 = band_at(f, s11, -15.0)
        lo20, hi20 = band_at(f, s11, -20.0)
        tlo, thi = band_at(f, -s21, 2.0)
        peaks = r['score'].get('inner_peaks') or []
        fc = 0.5 * (fm + fs)
        table.append(dict(
            case=r['case'], family=r['family'], source=r['source'], a_mm=round(r['a'], 6), g_mm=round(g['Ls2'] - 2 * g['Ws'], 6),
            Wm=g['Wm'], Ws=g['Ws'], Lm=g['Lm'], Ls1=g['Ls1'], Ls2=g['Ls2'], Ls3=g['Ls3'], mesh=r['mesh'],
            Lpath=lpath, rho=fold / lpath, eta=g['Ls2'] / (g['Ls2'] + g['Ls3']),
            zm_nominal=zm_nom, zs_nominal=zs_nom, zm_eff=zm, zs_eff=zs, fm_GHz=fm, fs_GHz=fs, fit_rms_linear=rms,
            N1=np.sqrt(zm / zm_nom), N2=np.sqrt(zs / zs_nom), P_eff=zm * zs, R_eff=zm / zs,
            slot_half_wave_mm=half_wave, slot_length_correction_mm=half_wave - lpath, path_phase_deg_at_fs=180 * lpath / half_wave,
            inner_peak_mean_dB=float(np.mean([p['S11_dB'] for p in peaks])) if peaks else float('nan'),
            bw_S11_15dB=hi15 - lo15, lo_S11_15dB=lo15, hi_S11_15dB=hi15,
            bw_S11_20dB=hi20 - lo20, bw_S21_2dB=thi - tlo, hi_S21_2dB=thi,
            bw15_circuit=bw_closed(zm * zs, zm, fc, -15.0), bw20_circuit=bw_closed(zm * zs, zm, fc, -20.0),
            residual_power_6p72=float(np.interp(6.72, f, rem)), residual_power_8p5=float(np.interp(8.5, f, rem)),
            residual_power_9p5=float(np.interp(9.5, f, rem)), min_S21_dB=r['score']['min_S21_dB']))
    write_csv(out / 'fold_table.csv', table)

    keys = ['N1', 'N2', 'zs_eff', 'P_eff', 'R_eff', 'fm_GHz', 'fs_GHz', 'Lm', 'Ls1', 'Lpath', 'rho', 'slot_length_correction_mm',
            'inner_peak_mean_dB', 'bw_S11_15dB', 'lo_S11_15dB', 'hi_S11_15dB', 'bw_S11_20dB', 'bw_S21_2dB', 'hi_S21_2dB',
            'bw15_circuit', 'residual_power_6p72', 'residual_power_8p5', 'residual_power_9p5', 'min_S21_dB']
    pairs = []
    for x in table:
        if abs(x['a_mm'] - 1.4) > 1e-6:
            continue
        for y in table:
            if (y['family'] == x['family'] and y['source'] == x['source'] and abs(y['a_mm'] - 1.8) < 1e-6
                    and abs(y['Wm'] - x['Wm']) < 1e-6 and abs(y['Ws'] - x['Ws']) < 1e-6):
                p = dict(family=x['family'], source=x['source'], case_a14=x['case'], case_a18=y['case'], Wm=x['Wm'], Ws=x['Ws'])
                p.update({'d_' + k: y[k] - x[k] for k in keys})
                p['rel_zs_eff'] = y['zs_eff'] / x['zs_eff'] - 1
                # circuit bandwidth change when only zs_eff moves (N2 path), other circuit parameters held at the a=1.4 member
                fcx = 0.5 * (x['fm_GHz'] + x['fs_GHz'])
                p['d_bw15_circuit_zs_only'] = bw_closed(x['zm_eff'] * y['zs_eff'], x['zm_eff'], fcx, -15.0) - x['bw15_circuit']
                pairs.append(p)
    write_csv(out / 'fold_pairs.csv', pairs)

    def block(sel):
        return {k: stats([p[k] for p in sel]) for k in pairs[0] if k.startswith(('d_', 'rel_'))}

    arr = lambda k: np.array([t[k] for t in table], float)  # noqa: E731
    x = np.c_[np.ones(len(table)), arr('Ws'), arr('a_mm')]
    coef, *_ = np.linalg.lstsq(x, arr('slot_length_correction_mm'), rcond=None)
    resid = arr('slot_length_correction_mm') - x @ coef
    cb, hb = arr('bw15_circuit'), arr('bw_S11_15dB')
    summary = dict(
        label='RETROSPECTIVE DESCRIPTIVE analysis of frozen development data; a has two levels (1.4, 1.8 mm), g fixed 0.55 mm; not a law for other a or g; not prospective',
        n_runs=len(table), n_pairs=len(pairs), delta_a_mm=0.4,
        ranges={k: [float(arr(k).min()), float(arr(k).max())] for k in ['rho', 'eta', 'a_mm', 'g_mm', 'Lpath', 'Wm', 'Ws', 'N2', 'P_eff', 'R_eff']},
        circuit_fit_rms_linear=[float(arr('fit_rms_linear').min()), float(arr('fit_rms_linear').max())],
        pairs_all=block(pairs), pairs_original48_only=block([p for p in pairs if p['source'] == 'original48']),
        circuit_vs_hfss_bw15=dict(mean_diff_GHz=float((cb - hb).mean()), sd_GHz=float((cb - hb).std(ddof=1)), corr=float(np.corrcoef(cb, hb)[0, 1])),
        slot_length_correction_fit=dict(form='half_wave(fs) - (Ls1+2Ls2+2Ls3) = c0 + c1*Ws + c2*a  [mm]', coef=[float(c) for c in coef],
                                        resid_sd_mm=float(resid.std(ddof=3)), mean_mm=float(arr('slot_length_correction_mm').mean()),
                                        path_phase_deg_mean=float(arr('path_phase_deg_at_fs').mean())))
    (out / 'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')
    s = summary['pairs_all']
    print(f"runs {len(table)}  pairs {len(pairs)}  (a 1.4 -> 1.8 mm, same Wm/Ws)")
    for k in ['d_N2', 'rel_zs_eff', 'd_P_eff', 'd_R_eff', 'd_inner_peak_mean_dB', 'd_bw_S11_15dB', 'd_bw15_circuit', 'd_bw15_circuit_zs_only',
              'd_bw_S21_2dB', 'd_residual_power_9p5', 'd_min_S21_dB', 'd_slot_length_correction_mm']:
        print(f"{k:28s} mean {s[k]['mean']:+.5f}  sd {s[k]['sd']:.5f}  +{s[k]['n_positive']}/-{s[k]['n_negative']} of {s[k]['n']}")
    print('circuit vs HFSS -15 dB bandwidth:', summary['circuit_vs_hfss_bw15'])
    print('slot length correction fit:', summary['slot_length_correction_fit'])


if __name__ == '__main__':
    main()
