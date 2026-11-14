# R9 审核的复核数据

离线，只读仓库里已提交的结果，不启动 HFSS，不发消息。对应 `docs/PLAN_20261110_FOLD_BANDWIDTH_R9.md`。

脚本读 `experiments/fold_bandwidth_r8_stage4_20261114/`（执行者分支 `codex/fold-bandwidth-r4-execution`，提交 `afe9c0c`），也读 R7、R8 审核目录的输出。要在含有这些目录的检出上运行，依次：

```
python review_s4.py
python cost_refit.py
python predict_r9.py
```

| 文件 | 内容 |
|---|---|
| `out/S4_RECOMPUTED.json` | 阶段 4 的 18 个几何用审核方的提取函数重算：中央谷、内峰、D、L、BW15/BW20、BW15*、带内最小 S21、端头净距、与执行者的差（全部为 0） |
| `out/COST_REFIT.json` | 五种长折臂代价模型（端头净距、a+g、a、槽跨度 Ls1、折叠比 rho）：只用 R7 点拟合后对阶段 4 点的外推误差；全部点拟合的系数（R9 冻结登记用） |
| `out/R9_PREDICTIONS.json` | 用冻结系数对阶段 5 规律设计给的 BW15* 估计。几何是粗估，最终评分用实际调准的几何代入同一模型 |

全部是回顾性分析：槽跨度和折叠比两种模型是看了阶段 4 数据之后加的，只用来登记预测，不能当作已验证的规律。
