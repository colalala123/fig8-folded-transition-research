"""R13 审核：R12 停止（c14be54）。离线、只读，不启动 HFSS，不发消息。
用环境变量 S12_EXP 指向 codex 分支的 experiments 目录。
1) 独立复算 B1R T1–T3，与执行者 SUMMARY 对比；
2) 比较 B1 与 B1R 密网格的 ΔS 历史（10 万单元以上）；
3) 按 |Γ| 口径给出 R13 的密网格判据和带宽代价。"""
import json, math, os, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent
EXP = pathlib.Path(os.environ.get('S12_EXP', HERE.parent))
sys.path.insert(0, str(HERE.parent / 'fold_bandwidth_review_r12_20261115'))
os.environ.setdefault('S6_EXP', str(EXP))
import review_s6r3 as r3  # noqa: E402  复用 R11/R12 的提取器

R12 = EXP / 'fold_bandwidth_r12_stage6_r4_20261115/results'
R9 = EXP / 'fold_bandwidth_r9_stage5_20261114/results'
G = lambda d: 10 ** (d / 20)
DB = lambda g: 20 * math.log10(g)


def hist(p):
    out = []
    for line in open(p, encoding='utf-8'):
        m = re.match(r'\s*(\d+)\|\s*(\d+)\|\s*([\d.]+)\|', line)
        if m:
            out.append((int(m[1]), int(m[2]), float(m[3])))
    return out


def clean(x):
    return {k: (float(v) if hasattr(v, 'item') else v) for k, v in x.items()}


if __name__ == '__main__':
    out = {'source_commit': 'c14be54'}
    B = {t: clean(r3.one('B1R' + t, R12 / f'S6R10_B1R__{t}')) for t in ('T1', 'T2', 'T3')}
    out['B1R'] = {t: {k: B[t][k] for k in ('valley_GHz', 'peak_lo_dB', 'peak_hi_dB', 'BW20', 'S21_min_in_BW15_dB', 'codex_diff', 'eq')} for t in B}
    dense = hist(R12 / 'S6R10_B1Rdense__T1/native/adaptive_11.txt')
    b1d = hist(R9 / 'S5R9_B1dense__T1/native/pre_final_sweep.txt')
    nom = hist(R12 / 'S6R10_B1R__T3/native/convergence.txt')
    out['dS_history_ge_1e5'] = {'B1R_dense': [(n, d) for _, n, d in dense if n >= 1e5],
                                'B1_dense': [(n, d) for _, n, d in b1d if n >= 1e5],
                                'B1R_T3_last': nom[-1]}
    plateau = [d for _, n, d in dense if 1e5 <= n <= 230000]
    out['B1R_dense_plateau_dS'] = {'min': min(plateau), 'max': max(plateau), 'n': len(plateau)}
    stat_lim = G(-22.021097504)              # R12 冻结的密网格统计判据（Γ）
    dS = dense[-1][2]
    out['R13_dense_rule'] = {'stat_limit_dB': -22.021097504, 'stat_limit_Gamma': stat_lim, 'last_dS': dS,
                             'pass_if_peak_Gamma_le': stat_lim - dS, 'pass_if_peak_dB_le': DB(stat_lim - dS),
                             'T3_worst_Gamma': G(B['T3']['peak_lo_dB']),
                             'allowed_mesh_shift_Gamma': stat_lim - dS - G(B['T3']['peak_lo_dB'])}
    b1_bw, b1_hi = 6.4549, -20.687
    t3 = B['T3']
    out['BW_cost'] = {'BW_loss_MHz': (b1_bw - t3['BW20']) * 1000,
                      'worst_peak_gain_dB': b1_hi - t3['peak_lo_dB'],
                      'MHz_per_dB': (b1_bw - t3['BW20']) * 1000 / (b1_hi - t3['peak_lo_dB']),
                      'loss_pct': (b1_bw - t3['BW20']) / b1_bw * 100}
    (HERE / 'out').mkdir(exist_ok=True)
    json.dump(out, open(HERE / 'out/R12STOP_RECOMPUTED.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print(json.dumps({k: out[k] for k in ('B1R_dense_plateau_dS', 'R13_dense_rule', 'BW_cost')}, ensure_ascii=False, indent=1, default=float))
    print({t: out['B1R'][t]['codex_diff'] for t in B})
