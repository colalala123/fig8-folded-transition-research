"""R2 审核复核：离线，只读 R1 回放结果。不启动 HFSS，不发消息。

用法：python experiments/fold_bandwidth_review_r2_20261110/review_checks.py [--out DIR]
"""
import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'fold_bandwidth_r1_20261110' / 'replay_r1' / 'EXTRACTED_80.json'


def main_band(q):
    """主通带口径：含中央谷的 -20 dB 连通段，且必须同时含两个内峰。"""
    b, shape = q['bandwidths']['BW20'], q['shape']
    peaks, valley = shape.get('inner_peaks', []), shape.get('central_valley_GHz')
    hit = [iv for iv in b['intervals_GHz'] if valley is not None and iv[0] <= valley <= iv[1]]
    if not hit or len(peaks) != 2:
        return None
    lo, hi = hit[0]
    if not all(lo <= p['GHz'] <= hi for p in peaks):
        return None
    return dict(low_GHz=lo, high_GHz=hi, BW_GHz=hi - lo)


def distinct_basin(q, rel=0.01, ratio=1.05):
    """不同盆地口径：任一参数与最优解相对差超过 rel 的收敛起点才算另一个解。"""
    ok = [s for s in q['circuit']['starts'] if s['success']]
    best = min(ok, key=lambda s: s['cost'])
    bp = np.array(best['parameters'])
    other = [s['cost'] / best['cost'] for s in ok
             if np.max(np.abs(np.array(s['parameters']) - bp) / np.abs(bp)) > rel]
    return dict(other_basins=len(other), min_cost_ratio=min(other) if other else None,
                nonunique=bool(other) and min(other) <= ratio)


def run():
    data = json.loads(SRC.read_text(encoding='utf-8'))
    rows = []
    for q in data:
        g, b = q['geometry_mm'], q['bandwidths']['BW20']
        m, u = main_band(q), distinct_basin(q)
        rows.append(dict(case=q['case'], a_mm=round(g.get('Ls3', 0) - g['Ws'], 6),
                         components_full_sweep=b['components'], r1_BW20_GHz=b['BW_GHz'],
                         worst_inner_peak_dB=max(p['S11_dB'] for p in q['shape']['inner_peaks']),
                         main_band=m, **u))
    valid = [r for r in rows if r['main_band']]
    widths = [r['main_band']['BW_GHz'] for r in valid]
    return dict(
        source=SRC.relative_to(HERE.parent.parent).as_posix(),
        evidence='retrospective, descriptive; archived curves only; no new solver data',
        bw20=dict(total=len(rows), main_band_valid=len(valid), split_inside_main_band=len(rows) - len(valid),
                  r1_literal_valid=sum(r['r1_BW20_GHz'] is not None for r in rows),
                  restored_by_main_band_rule=sorted(r['case'] for r in valid if r['r1_BW20_GHz'] is None),
                  valid_BW20_GHz=dict(min=min(widths), max=max(widths), mean=float(np.mean(widths))),
                  valid_by_a_mm={str(a): sum(r['a_mm'] == a for r in valid) for a in sorted({r['a_mm'] for r in valid})},
                  all_valid_have_inner_peak_below_minus20=all(r['worst_inner_peak_dB'] <= -20 for r in valid),
                  all_split_have_inner_peak_above_minus20=all(r['worst_inner_peak_dB'] > -20 for r in rows if not r['main_band'])),
        uniqueness=dict(r1_literal_flags=sum(q['circuit']['extraction_nonunique'] for q in data),
                        distinct_basin_flags=sum(r['nonunique'] for r in rows),
                        cases_with_other_basins=sum(r['other_basins'] > 0 for r in rows),
                        min_cost_ratio_of_other_basins=min(r['min_cost_ratio'] for r in rows if r['min_cost_ratio'])),
        rows=rows)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=HERE / 'out_rerun')
    out = ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    result = run()
    (out / 'REVIEW_CHECKS.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False, indent=1))
