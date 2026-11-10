# R3 审核的复核数据

对应文档：[docs/PLAN_20261110_FOLD_BANDWIDTH_R3.md](../../docs/PLAN_20261110_FOLD_BANDWIDTH_R3.md)。

证据等级：回顾性、描述性，加上未校准的先验。只读取已提交的表格和 R1 目录里的规律链，没有新的求解数据，不启动 HFSS，不发消息。

```sh
python experiments/fold_bandwidth_review_r3_20261110/review_checks.py
```

默认写到 `out_rerun/`（已忽略）。已提交的结果在 `out/REVIEW_CHECKS.json`，包含两部分：

- `weekly_report_check`：07-25 周报 4 个弯折点的带宽变化，与归档 80 条曲线里“线宽固定只改折臂”和“折臂固定线宽不同”两种趋势的比较。周报的 4 个点不在本仓库，只比较相对变化。
- `stage3_retarget`：阶段 3 的纹波目标从 −21 dB 改为 −20.3 dB 之后，两个基准各档折臂的初值、带宽先验和净距筛选结果。这是先验，不是 HFSS 预测。

依赖 `experiments/fold_bandwidth_20261110/out/fold_table.csv` 和 `experiments/fold_bandwidth_r1_20261110/chain.py`。
