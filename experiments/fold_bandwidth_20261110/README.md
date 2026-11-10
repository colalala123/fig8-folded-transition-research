# 弯折与带宽：离线配对分析（2026-11-10）

计划见 [docs/PLAN_20261110_FOLD_BANDWIDTH.md](../../docs/PLAN_20261110_FOLD_BANDWIDTH.md)。本目录是该计划 4.2、4.3 节数字的出处。

**证据等级：回顾性、描述性。** 只用归档的 80 次仿真（78 条开发 + 2 条回顾性留出），没有新仿真。折臂 a 只有 1.4、1.8 mm 两档，间隔 g 固定 0.55 mm，所以这里的斜率只是两档之间的局部差，不是对其他 a、g 成立的规律，也不是前瞻检验。

## 复现

在仓库根目录，只需要 `requirements.txt` 里的 numpy 和 scipy：

```bash
python experiments/fold_bandwidth_20261110/offline_fold_analysis.py
```

结果写到 `out_rerun/`，不覆盖已提交的 `out/`。脚本不启动 HFSS，不联网，不发消息，不写 `model/`、`data/`、`results/`。

## 文件

| 文件 | 内容 |
|---|---|
| `offline_fold_analysis.py` | 对每条曲线拟合论文 Fig. 2(b) 的等效电路（4 个参数），计算弯折描述量和各种口径的带宽，做 a = 1.4 对 1.8 的配对比较 |
| `out/fold_table.csv` | 80 行，每次仿真一行：几何、a、g、Lpath、ρ、η、N1、N2、z′m、z′s、fm、fs、P_eff、R_eff、各口径带宽、剩余功率 |
| `out/fold_pairs.csv` | 47 行，每对一行：同一家族、同一来源、Wm 和 Ws 相同，a = 1.8 减 a = 1.4 的差 |
| `out/SUMMARY.json` | 配对差的均值、标准差、同向对数；电路带宽与 HFSS 带宽的对比；槽线长度修正的拟合 |

## 口径说明

- `bw_S11_15dB`、`bw_S11_20dB`：包含 6.72 GHz 的、S11 连续低于门限的区间宽度。内峰高于 −20 dB 时，−20 dB 口径只剩中央谷附近的一小段，所以配对差里 `d_bw_S11_20dB` 会整段跳变，不能当平滑趋势看。
- `bw15_circuit`：由提取的 P_eff、z′m 和 f0 = (fm + fs)/2 按闭式解算出的 −15 dB 带宽。
- `residual_power_*`：1 − |S11|² − |S21|²，含辐射、导体和介质损耗，不能全部叫辐射损耗。
- `slot_length_correction_mm`：fs 处的槽线半波长减去 Ls1 + 2Ls2 + 2Ls3。
