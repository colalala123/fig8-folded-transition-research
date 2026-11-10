# R1 审核的复核数据

对应文档：[docs/PLAN_20261110_FOLD_BANDWIDTH_R1.md](../../docs/PLAN_20261110_FOLD_BANDWIDTH_R1.md)。

证据等级：回顾性、描述性。只读取已提交的表格，没有新的求解数据，不启动 HFSS，不发消息。

```sh
python experiments/fold_bandwidth_review_r1_20261110/review_checks.py
```

默认写到 `out_rerun/`（已忽略）。已提交的结果在 `out/REVIEW_CHECKS.json`，包含三部分：

- `length_law`：槽线长度规律在“参数和”与“中心线”两种口径下的均值、fs 处的电长度和回归系数。
- `straight_prior`：三个基准的直槽初值和变比先验。这是外推，不是已验证的预测。
- `regate`：阶段 0 登记的 70 个弯折设计按 R1 的净距规则重新筛选的结果，以及与原筛选不同的 5 个点。

依赖阶段 0 目录里的 `chain.py` 和 `freeze/`，以及 `experiments/fold_bandwidth_20261110/out/fold_table.csv`。
