# R10 审核的复核数据

离线，只读仓库里已提交的结果，不启动 HFSS，不发消息。对应 `docs/PLAN_20261110_FOLD_BANDWIDTH_R10.md`。

`review_s5.py` 读 `experiments/fold_bandwidth_r9_stage5_20261114/`（执行者分支 `codex/fold-bandwidth-r4-execution`，提交 `c4e98c4`）。这个目录不在计划分支上，用环境变量 `S5_EXP` 指向含它的 `experiments` 目录。也读 R7、R8、R9 审核目录。依次运行：

```
S5_EXP=<含阶段5数据的 experiments 目录> python review_s5.py
python rules_s5.py
```

| 文件 | 内容 |
|---|---|
| `out/S5_RECOMPUTED.json` | 阶段 5 的 22 个几何（含 B1 密网格）用审核方的提取函数重算，以及与执行者的差。只有 B3 T1 高频内峰差 0.19 dB，执行者已披露 |
| `out/S5_RULES.json` | 五种冻结代价模型对 5A 和 B1–B3 的误差；同形状两点之间 BW20 与余量的换算；Wm 平台线性拟合；B1 密网格与名义网格之差 |

B1–B3 不是前瞻点（看过 5A 后在 R9-2 冻结，且都是调参结果），代价模型对它们的误差只作回顾参考。
