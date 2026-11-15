# R12 审核：R11/R3 阶段 6 的七个新点（P9c、P10–P14、N0）

离线、只读，不启动 HFSS，不发消息。

- `review_s6r3.py`：复用 R11 的 `review_s6.py` 提取器，从原生 CSV 独立复算七个新点，与执行者 SUMMARY 对比；把 P1–P14、N0 合起来做七组中心差分（Ws、Lm、Ls1、Wm、蚀刻、εr、h）；检验“两内峰均值只跟 P_eff 走、倾斜只跟失谐 fm − fs 走”的两参数规律；用 |Γ| 口径重算稳健设计需要的最高内峰 P_req，并按 h 公差 ±0.025 / ±0.038 / ±0.051 和“板厚实测 ±0.005”给出对应值。
- 数据在 `codex/fold-bandwidth-r4-execution`（`9ba51a5`）。运行：`S6_EXP=<该分支的 experiments 目录> python review_s6r3.py`。
- 输出 `out/S6R3_RECOMPUTED.json`。

结论见 `docs/PLAN_20261115_FOLD_BANDWIDTH_R12.md`。这些是名义插值数据，不是直接频点、收敛或制造认证。
