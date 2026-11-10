# R5 审核的复核数据

对应文档：[docs/PLAN_20261110_FOLD_BANDWIDTH_R5.md](../../docs/PLAN_20261110_FOLD_BANDWIDTH_R5.md)。

证据等级：回顾性、描述性。只读取已提交的数据，不启动 HFSS，不发消息。

```sh
python experiments/fold_bandwidth_review_r5_20261110/review_checks.py
```

默认写到 `out_rerun/`（已忽略）。已提交的结果在 `out/REVIEW_CHECKS.json`，包含两部分：

- `first_run_vs_archive`：首次仿真 `S1_BASE_N04`（96,396 单元）与归档 `N04_A18`（101,852 单元）的比较，含复数 S 参数的最大差、内峰、带宽。
- `archive_mesh_rule`：归档的 81 条运行记录里，分段加密的做法和最终网格、ΔS 的范围。
