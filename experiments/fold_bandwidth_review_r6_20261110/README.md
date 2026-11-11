# R6 审核的复核数据

对应文档：[docs/PLAN_20261110_FOLD_BANDWIDTH_R6.md](../../docs/PLAN_20261110_FOLD_BANDWIDTH_R6.md)。

证据等级：回顾性、描述性。只读取已提交的数据，不启动 HFSS，不发消息。

```sh
python experiments/fold_bandwidth_review_r6_20261110/review_checks.py
```

默认写到 `out_rerun/`（已忽略）。已提交的结果在 `out/REVIEW_CHECKS.json`，包含两部分：

- `n04_redo_vs_archive`：`S1_BASE_N04` 按 R5 重做的结果（100,374 单元）与归档 `N04_A18` 的比较。
- `archive_process_roles`：归档的 81 条运行记录里观察到的 `hf3d.exe` 进程，按命令角色和核数统计。
