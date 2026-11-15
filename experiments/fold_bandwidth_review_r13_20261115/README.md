# R13 审核：R12 停止（B1R 名义调准，密网格触发 24 万安全上限）

离线、只读，不启动 HFSS，不发消息。

- `review_r12stop.py`：
  - 复用 R12 的提取器，从原生 CSV 独立复算 B1R T1–T3，并与执行者 SUMMARY 对比；
  - 对比 B1（R9）与 B1R 两次密网格在 10 万单元以上的 ΔS 历史；
  - 给出 R13 的密网格判据（|Γ| 口径，把最后一轮 ΔS 计为误差）；
  - 计算 B1 → B1R 的带宽代价。
- 数据在 `codex/fold-bandwidth-r4-execution`（`c14be54`）。运行：`S12_EXP=<该分支的 experiments 目录> python review_r12stop.py`。
- 输出 `out/R12STOP_RECOMPUTED.json`。

结论见 `docs/PLAN_20261115_FOLD_BANDWIDTH_R13.md`。这些是名义插值数据，不是直接频点、收敛或制造认证。
