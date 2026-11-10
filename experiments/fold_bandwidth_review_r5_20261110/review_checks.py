"""R5 审核的复核计算。离线，只读已提交的数据，不启动 HFSS，不发消息。"""
import collections, csv, glob, json, pathlib, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
NEW = ROOT / 'experiments/fold_bandwidth_r4_20261110/headless_results/S1_BASE_N04/full_modes.csv'
OLD = ROOT / 'data/raw/N04_A18/sparams.csv'


def load(path):
    rows = list(csv.reader(open(path, encoding='utf-8')))
    return rows[0], np.array(rows[1:], float)


def db(z):
    return 20 * np.log10(np.abs(z))


def inner_peaks(f, s11, lo=4.3, hi=8.8):
    d = db(s11)
    return [(float(f[i]), float(d[i])) for i in range(1, len(f) - 1)
            if lo < f[i] < hi and d[i] > d[i - 1] and d[i] > d[i + 1]]


def main_band(f, s11, thr, centre):
    d = db(s11)
    i = int(np.argmin(abs(f - centre)))
    lo = hi = i
    while d[lo] < thr:
        lo -= 1
    while d[hi] < thr:
        hi += 1
    a = f[lo] + (thr - d[lo]) / (d[lo + 1] - d[lo]) * (f[lo + 1] - f[lo])
    b = f[hi - 1] + (thr - d[hi - 1]) / (d[hi] - d[hi - 1]) * (f[hi] - f[hi - 1])
    return float(a), float(b)


def first_run():
    h, a = load(NEW)
    _, b = load(OLD)
    f = a[:, 0]
    assert np.allclose(f, b[:, 0])
    col = lambda n: a[:, h.index(n + '_real')] + 1j * a[:, h.index(n + '_imag')]
    s11n, s21n = col('S(1:1,1:1)'), col('S(2:1,1:1)')
    s11o, s21o = b[:, 1] + 1j * b[:, 2], b[:, 4] + 1j * b[:, 5]
    lo, hi = main_band(f, s11o, -15, 6.74)
    m = (f >= lo) & (f <= hi)
    out = dict(archive_BW15_band_GHz=[lo, hi],
               max_abs_dS11=float(abs(s11n - s11o)[m].max()),
               max_abs_dS21=float(abs(s21n - s21o)[m].max()),
               peaks_new=inner_peaks(f, s11n), peaks_archive=inner_peaks(f, s11o))
    for name, thr in (('BW20', -20), ('BW15', -15)):
        n, o = main_band(f, s11n, thr, 6.73), main_band(f, s11o, thr, 6.74)
        out[name + '_new_GHz'], out[name + '_archive_GHz'] = n[1] - n[0], o[1] - o[0]
    level = 10 ** (-20.5 / 20)
    out['dB_equivalent_at_minus20p5'] = {
        str(x): float(20 * np.log10((level + x) / level)) for x in (0.0011, 0.0021, 0.0046, 0.005)}
    return out


def archive_mesh_rule():
    stage0, final, ds, steps, n_stage = [], [], [], collections.defaultdict(list), []
    for p in sorted(glob.glob(str(ROOT / 'data/raw/*/state.json'))):
        s = json.load(open(p, encoding='utf-8'))
        ms = s['mesh_stages']
        stage0.append((ms[0]['requested']['maximum_passes'], ms[0]['requested']['percent_refinement'],
                       ms[0]['actual_elements']))
        prev = ms[0]['actual_elements']
        for m in ms[1:]:
            steps[m['requested']['percent_refinement']].append(prev)
            prev = m['actual_elements']
        final.append(s['actual_elements'])
        ds.append(s['convergence']['final_delta_s'])
        n_stage.append(len(ms))
    return dict(cases=len(final),
                stage0_settings=sorted({(a, b) for a, b, _ in stage0}),
                stage0_elements=[min(c for *_, c in stage0), max(c for *_, c in stage0)],
                continuation_percent_vs_elements_before={str(k): [min(v), max(v), len(v)] for k, v in steps.items()},
                final_elements=[min(final), float(np.median(final)), max(final)],
                final_delta_s=[min(ds), float(np.median(ds)), max(ds)],
                final_delta_s_above_0p005=int(sum(x > 0.005 for x in ds)),
                stages_per_case=[min(n_stage), max(n_stage)])


def run(out_dir):
    out = dict(first_run_vs_archive=first_run(), archive_mesh_rule=archive_mesh_rule())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'REVIEW_CHECKS.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    return out


if __name__ == '__main__':
    here = pathlib.Path(__file__).resolve().parent
    print(json.dumps(run(here / (sys.argv[1] if len(sys.argv) > 1 else 'out_rerun')), indent=1, ensure_ascii=False))
