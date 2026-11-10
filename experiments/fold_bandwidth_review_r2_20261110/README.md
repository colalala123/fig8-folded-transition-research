# R2 审核的复核数据

对应文档：[docs/PLAN_20261110_FOLD_BANDWIDTH_R2.md](../../docs/PLAN_20261110_FOLD_BANDWIDTH_R2.md)。

证据等级：回顾性、描述性。只读取 R1 目录里已提交的回放结果 `replay_r1/EXTRACTED_80.json`，没有新的求解数据，不启动 HFSS，不发消息。

```sh
python experiments/fold_bandwidth_review_r2_20261110/review_checks.py
```

默认写到 `out_rerun/`（已忽略）。已提交的结果在 `out/REVIEW_CHECKS.json`，包含三部分：

- `bw20`：归档的 80 条曲线按“主通带”口径重新判断 −20 dB 带宽的结果，以及与 R1 字面规则不同的 7 条。
- `uniqueness`：按“不同参数盆地”口径重新判断提取是否唯一的结果。
- `rows`：逐条明细。
