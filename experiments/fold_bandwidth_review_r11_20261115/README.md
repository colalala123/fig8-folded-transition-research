# R11 审核：R10 阶段 6 的 P1–P9（P10 技术停止）

离线、只读，不启动 HFSS，不发消息。

- `review_s6.py`：从原生 CSV 独立复算 B1 T2 基准和 P1–P9 的中央谷、两内峰、BW20、BW20.5，与执行者 SUMMARY 对比；算四组 ±0.02 mm 的中心差分、曲率、最高内峰升幅；检查过蚀刻 P9 与单项叠加（P1+P5+P4+P8）的一致性。
- 数据在 `codex/fold-bandwidth-r4-execution`（`bcb48cd`）。运行：`S6_EXP=<含 fold_bandwidth_r9_stage5 与 r10_stage6_r1/r2 的 experiments 目录> python review_s6.py`。
- 输出 `out/S6_RECOMPUTED.json`。

结论见 `docs/PLAN_20261115_FOLD_BANDWIDTH_R11.md`。这些是名义插值数据，不是直接频点、收敛或制造认证。
