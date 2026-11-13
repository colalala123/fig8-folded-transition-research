"""R7 审核的复核计算。离线，只读已提交的数据，不启动 HFSS，不发消息。"""
import csv, glob, json, pathlib, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXP = ROOT / 'experiments'
DIRS = ['fold_bandwidth_r6_20261111', 'fold_bandwidth_r6_stage2_20261111',
        'fold_bandwidth_r6_stage2b_20261112', 'fold_bandwidth_r6_stage3_20261112',
        'fold_bandwidth_r6_stage3_corrected_20261113']


def load(path):
    rows = list(csv.reader(open(path, encoding='utf-8')))
    h, a = rows[0], np.array(rows[1:], float)
    col = lambda n: a[:, h.index(n + '_real')] + 1j * a[:, h.index(n + '_imag')]
    return a[:, 0], 20 * np.log10(abs(col('S(1:1,1:1)'))), 20 * np.log10(abs(col('S(2:1,1:1)')))


def shape(f, d, centre=6.72):
    """中央谷、两个内峰；不是三谷形状时返回 None。"""
    mins = [i for i in range(1, len(f) - 1) if d[i] < d[i - 1] and d[i] <= d[i + 1] and 5.8 < f[i] < 7.6]
    if not mins:
        return None
    v = min(mins, key=lambda i: abs(f[i] - centre))
    lo = next((i for i in range(v - 1, 0, -1) if d[i] > d[i - 1] and d[i] >= d[i + 1]), None)
    hi = next((i for i in range(v + 1, len(f) - 1) if d[i] >= d[i - 1] and d[i] > d[i + 1]), None)
    if lo is None or hi is None or not (4.0 < f[lo] and f[hi] < 9.2):
        return None
    return v, lo, hi


def band(f, d, thr, lo, hi):
    """含两个内峰的连续主带（阈值 thr）；任一内峰不低于 thr 时无效。"""
    if d[lo] >= thr or d[hi] >= thr:
        return None
    a, b = lo, hi
    while a > 0 and d[a] < thr:
        a -= 1
    while b < len(f) - 1 and d[b] < thr:
        b += 1
    if d[a] < thr or d[b] < thr:
        return None
    x = f[a] + (thr - d[a]) / (d[a + 1] - d[a]) * (f[a + 1] - f[a])
    y = f[b - 1] + (thr - d[b - 1]) / (d[b] - d[b - 1]) * (f[b] - f[b - 1])
    return float(x), float(y)


def geometry(case_dir):
    j = json.load(open(case_dir / 'INPUT.json', encoding='utf-8'))
    g = j['design']['geometry_mm'] if 'design' in j else j['geometry_mm']
    fam = (j.get('design') or j).get('family')
    return g, fam


def n04_baseline():
    d = EXP / 'fold_bandwidth_r4_20261110/r5_cache_results/S1_BASE_N04'
    meta = json.load(open(d / 'metadata.json', encoding='utf-8'))
    rev = json.load(open(d / 'REVIEW_R5.json', encoding='utf-8'))
    return d / 'full_modes.csv', 'S1_BASE_N04', 'fold_bandwidth_r4_20261110', meta['geometry'], 'N04', rev['redo_mesh_cells'], rev['redo_delta_s']


def collect():
    rows = []
    items = [n04_baseline()]
    for d in DIRS:
        for p in sorted(glob.glob(str(EXP / d / 'results/*/native/full_modes.csv'))):
            case = pathlib.Path(p).parents[1]
            summ = json.load(open(case / 'SUMMARY.json', encoding='utf-8'))
            if not summ['record'].get('solve_completed'):
                continue
            g, fam = geometry(case)
            items.append((p, case.name, d, g, fam, summ['record']['mesh_cells'], summ['record']['delta_s']))
    for p, name, d, g, fam, mesh, ds in items:
        if True:
            f, s11, s21 = load(p)
            r = dict(case=name, batch=d, family=fam, **{k: g[k] for k in ('Wm', 'Ws', 'Lm', 'Ls1', 'Ls2', 'Ls3')},
                     mesh=mesh, delta_s=ds)
            r['a'] = g['Ls3'] - g['Ws'] if g['Ls3'] else 0.0
            r['g'] = g['Ls2'] - 2 * g['Ws'] if g['Ls2'] else None
            r['Lc'] = g['Ls1'] + 2 * g['Ls2'] + 2 * g['Ls3'] - 4 * g['Ws'] if g['Ls3'] else g['Ls1']
            sh = shape(f, s11)
            r['three_valley'] = sh is not None
            if sh:
                v, lo, hi = sh
                r.update(valley_GHz=float(f[v]), valley_dB=float(s11[v]), peak_lo_dB=float(s11[lo]),
                         peak_hi_dB=float(s11[hi]), peak_lo_GHz=float(f[lo]), peak_hi_GHz=float(f[hi]))
                r['peak_max_dB'] = max(r['peak_lo_dB'], r['peak_hi_dB'])
                r['peak_mean_dB'] = (r['peak_lo_dB'] + r['peak_hi_dB']) / 2
                r['peak_gap_dB'] = abs(r['peak_lo_dB'] - r['peak_hi_dB'])
                r['D_dB'] = r['peak_hi_dB'] - r['peak_lo_dB']
                for name, thr in (('BW15', -15.0), ('BW20', -20.0), ('BWown', r['peak_max_dB'] + 0.3), ('BWref', r['peak_mean_dB'] + 0.3)):
                    b = band(f, s11, thr, lo, hi)
                    r[name] = b[1] - b[0] if b else None
                    r[name + '_edges'] = b
                # 主带边沿斜率（MHz/dB）：阈值在 own 与 own+0.5 dB 之间的带宽变化
                b2 = band(f, s11, r['peak_max_dB'] + 0.8, lo, hi)
                r['skirt_MHz_per_dB'] = ((b2[1] - b2[0]) - r['BWown']) * 1000 / 0.5 if b2 and r['BWown'] else None
            rows.append(r)
    return rows


def codex_crosscheck(rows):
    """与 Codex 审核文件中的内峰、BW15 对照。"""
    out = []
    for r in rows:
        for pat in ('review/REVIEW_STAGE2.json', 'review/REVIEW_STAGE3.json', 'SUMMARY.json'):
            p = EXP / r['batch'] / 'results' / r['case'] / pat
            if p.exists():
                j = json.load(open(p, encoding='utf-8'))
                m = j.get('metrics') or (j.get('review') or {}).get('metrics')
                if m and m.get('inner_peak_low_dB') is not None and r['three_valley']:
                    out.append(dict(case=r['case'], d_lo=r['peak_lo_dB'] - m['inner_peak_low_dB'],
                                    d_hi=r['peak_hi_dB'] - m['inner_peak_high_dB'],
                                    d_BW15=(r['BW15'] - m['BW15_GHz']) if r.get('BW15') and m.get('BW15_GHz') else None))
                    break
    return out


def balanced(rows, gap=0.6, dv=0.035, g055=True):
    return [r for r in rows if r['three_valley'] and r['peak_gap_dB'] <= gap and abs(r['valley_GHz'] - 6.72) <= dv
            and (not g055 or r['g'] is None or abs(r['g'] - 0.55) < 1e-6)]


def tradeoff(rows):
    """同家族、同 a、只改 Ws 的平衡点：纹波每加深 1 dB，BW15 变窄多少。"""
    out = {}
    pts = sorted([r for r in balanced(rows) if r['family'] == 'N14' and abs(r['a'] - 1.8) < 1e-6], key=lambda r: r['Ws'])
    x = np.array([p['peak_mean_dB'] for p in pts])
    out['N14_a1.8_batch1b'] = dict(n=len(pts), BW15_MHz_per_dB=float(np.polyfit(x, [p['BW15'] for p in pts], 1)[0] * 1000),
                                   mean_peak_dB_per_mm_Ws=float(np.polyfit([p['Ws'] for p in pts], x, 1)[0]))
    by = {r['case']: r for r in rows}
    for name, a, b in (('N04_a0.6', 'S2_E1_N04_a0.6__T2', 'S3R3_EQ_N04_01__T3'), ('N04_a0', 'S2_E0_N04__T3', 'S3R3_EQ_N04_00__T3')):
        p, q = by[a], by[b]
        out[name] = dict(cases=[a, b], gaps_dB=[p['peak_gap_dB'], q['peak_gap_dB']],
                         BW15_MHz_per_dB=float((p['BW15'] - q['BW15']) / (p['peak_mean_dB'] - q['peak_mean_dB']) * 1000),
                         mean_peak_dB_per_mm_Ws=float((p['peak_mean_dB'] - q['peak_mean_dB']) / (p['Ws'] - q['Ws'])))
    return out


def normalised(rows, slopes=(0.114, 0.144), ref=-20.3):
    """把平衡点的 BW15 折算到平均内峰 ref；给出两个斜率下的范围。回顾性分析，不是前瞻结论。"""
    out = []
    for r in balanced(rows):
        d = r['peak_mean_dB'] - ref
        out.append(dict(case=r['case'], family=r['family'], a=round(r['a'], 3), Ws=r['Ws'], mean_peak_dB=r['peak_mean_dB'],
                        gap_dB=r['peak_gap_dB'], BW15=r['BW15'], shift_dB=d,
                        BW15_at_ref=[r['BW15'] - s * d for s in slopes]))
    return out


def sensitivity(rows):
    """调参灵敏度：阶段 2/3 同一设计相邻两次尝试的差（|D|<6 dB），加上 1b 的 Ws 扰动。
    回归 (Δ中央谷, ΔD, Δ平均内峰) = (ΔLm, ΔLc, ΔWs)·J。D = 高频内峰 − 低频内峰。"""
    import collections
    ch = collections.defaultdict(list)
    for r in rows:
        if '__T' in r['case']:
            ch[r['case'].split('__T')[0]].append(r)
    keys = ('Lm', 'Lc', 'Ws', 'valley_GHz', 'D_dB', 'peak_mean_dB')
    S = []
    for k, v in sorted(ch.items()):
        v = sorted(v, key=lambda r: r['case'])
        for p, q in zip(v, v[1:]):
            if p['three_valley'] and q['three_valley'] and abs(p['a'] - q['a']) < 1e-6 and max(abs(p['D_dB']), abs(q['D_dB'])) < 6:
                S.append([q[x] - p[x] for x in keys] + [k])
    by = {r['case']: r for r in rows}
    b = by['S1_WS_04']
    for r in rows:
        if r['case'].startswith('S1_WS') and r['case'] != 'S1_WS_04':
            S.append([r[x] - b[x] for x in keys] + ['1b'])
    A, Y = np.array([s[:3] for s in S]), np.array([s[3:6] for s in S])
    J = np.linalg.lstsq(A, Y, rcond=None)[0]
    small = np.array([abs(s[4]) < 2.5 for s in S])
    Js = np.linalg.lstsq(A[small], Y[small], rcond=None)[0]
    return dict(steps=S, rows='Lm,Lc,Ws (per mm)', cols='valley GHz, D dB, mean peak dB',
                J_all=J.tolist(), resid_sd_all=np.std(Y - A @ J, axis=0).tolist(), n_all=len(S),
                J_small_steps=Js.tolist(), resid_sd_small=np.std(Y[small] - A[small] @ Js, axis=0).tolist(), n_small=int(small.sum()))


SEEDS = {'N04 a=0': 'S3R3_EQ_N04_00__T3', 'N04 a=0.6': 'S3R3_EQ_N04_01__T3', 'N04 a=2.2': 'S2_E1_N04_a2.2__T2',
         'N04 a=2.6': 'S2_E1_N04_a2.6__T3', 'N14 a=0': 'S2_E0_N14__T3', 'N14 a=0.6': 'S2_E1_N14_a0.6__T2',
         'N14 a=1.0': 'S2_E1_N14_a1.0__T1', 'N14 a=2.6': 'S2_E1_N14_a2.6__T3'}


def usable(r, ref=-20.3):
    return (r['three_valley'] and r['peak_gap_dB'] <= 0.5 and abs(r['valley_GHz'] - 6.72) <= 0.0301
            and abs(r['peak_mean_dB'] - ref) <= 0.6)


def first_steps(rows, ref=-20.3):
    """示例：按 J_all 从种子点一步走到 (6.72 GHz, D=0, 平均内峰 ref) 的尺寸改动。仅供执行者核对自己的实现。"""
    by = {r['case']: r for r in rows}
    J = np.array(sensitivity(rows)['J_all'])
    out = dict(existing_usable=[dict(case=r['case'], family=r['family'], a=round(r['a'], 3), mean_peak_dB=r['peak_mean_dB'],
                                     gap_dB=r['peak_gap_dB'], valley_GHz=r['valley_GHz'], BW15=r['BW15'], BW20=r['BW20'], BWref=r['BWref'])
                                for r in rows if usable(r) and r['family'] in ('N04', 'N14') and (r['g'] is None or abs(r['g'] - 0.55) < 1e-6)],
               steps={})
    for k, c in SEEDS.items():
        r = by[c]
        dx = np.linalg.solve(J.T, np.array([6.72 - r['valley_GHz'], -r['D_dB'], ref - r['peak_mean_dB']]))
        out['steps'][k] = dict(seed=c, seed_state=dict(valley_GHz=r['valley_GHz'], D_dB=r['D_dB'], mean_peak_dB=r['peak_mean_dB'],
                                                       Lm=r['Lm'], Lc=r['Lc'], Ws=r['Ws']),
                               step_mm=dict(zip(('Lm', 'Lc', 'Ws'), dx.tolist())), new_Ws=r['Ws'] + float(dx[2]))
    return out


if __name__ == '__main__':
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).parent / 'out')
    out.mkdir(exist_ok=True)
    rows = collect()
    json.dump(rows, open(out / 'ALL_GEOMETRIES.json', 'w'), indent=1)
    cc = codex_crosscheck(rows)
    mx = lambda k: max(abs(c[k]) for c in cc if c[k] is not None)
    tv = [r for r in rows if r['three_valley']]
    summary = dict(geometries=len(rows), three_valley=len(tv),
                   mesh_range=[min(r['mesh'] for r in rows), max(r['mesh'] for r in rows)],
                   max_delta_s=max(r['delta_s'] for r in rows),
                   crosscheck_vs_executor=dict(n=len(cc), max_abs_d_peak_lo=mx('d_lo'), max_abs_d_peak_hi=mx('d_hi'), max_abs_d_BW15=mx('d_BW15')),
                   skirt_MHz_per_dB_median=float(np.median([r['skirt_MHz_per_dB'] for r in balanced(rows) if r['skirt_MHz_per_dB']])))
    pts = sorted([r for r in balanced(rows) if r['family'] == 'N14' and abs(r['a'] - 1.8) < 1e-6], key=lambda r: r['Ws'])
    x = np.array([p['peak_mean_dB'] for p in pts])
    summary['BWref_MHz_per_dB_batch1b'] = float(np.polyfit(x, [p['BWref'] for p in pts], 1)[0] * 1000)
    json.dump(summary, open(out / 'SUMMARY.json', 'w'), indent=1)
    json.dump(dict(tradeoff=tradeoff(rows), normalised=normalised(rows)), open(out / 'TRADEOFF.json', 'w'), indent=1)
    json.dump(sensitivity(rows), open(out / 'SENSITIVITY.json', 'w'), indent=1)
    json.dump(first_steps(rows), open(out / 'EXAMPLE_FIRST_STEPS.json', 'w'), indent=1)
    print(json.dumps(summary, indent=1))
