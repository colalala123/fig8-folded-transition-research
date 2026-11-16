# R16 审核：阶段 7（`829569f`）独立复算

离线、只读，不启动 HFSS，不发消息。

- `review_s7.py`：复用 R7/R8/R10 审核的提取器（`load`、`metrics`），从原生 `full_modes.csv` 重算 W4R T1/T2、C1W、W4R 密网格的中央谷、两内峰、BW20，加上含中央谷的 −20 dB 主窗两端带边；与 Codex SUMMARY 比较，并算角点、网格的 Δ|Γ|。
- 运行：`S7_EXP=<codex 分支检出>/experiments python review_s7.py`，输出 `out/S7_RECOMPUTED.json`。
- 结果：可比字段差全为 0；C1W − W4R 的 Δ|Γ| 为 0.023270，网格偏差（高峰）为 0.002336，角点加偏差为 0.09508。
- B1 单项带边移动（用于 R16 第 1 节的保证带宽估算）也是用本脚本的 `edges()` 在阶段 6 的 P9c–P14 上算出的。
