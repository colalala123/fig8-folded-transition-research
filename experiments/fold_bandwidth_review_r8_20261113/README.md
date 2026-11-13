# R8 审核的复核数据

离线，只读仓库里已提交的结果，不启动 HFSS，不发消息。对应 `docs/PLAN_20261110_FOLD_BANDWIDTH_R8.md`。

`review_3r.py` 读 `experiments/fold_bandwidth_r7_3r_20261113/`，这个目录在执行者分支 `codex/fold-bandwidth-r4-execution`（提交 `4efad36`）上。要在含有该目录的检出上运行，依次：

```
python review_3r.py
python tip_vs_arm.py
python predictions.py
```

| 文件 | 内容 |
|---|---|
| `out/R7_3R_RECOMPUTED.json` | 3R 的 27 个几何用审核方自己的提取函数重算：中央谷、内峰、D、L、BW15/BW20/BWref、折算值、带内最小 S21、端头距离、与执行者的差 |
| `out/LADDER.json` | 两个家族各 6 个可用点（4 个回顾、8 个前瞻调参） |
| `out/TIP_VS_ARM.json` | 全部平衡点（含阶段 2 的 g 阶梯）的 BW15*、相对家族平台的代价、端头距离 |
| `out/R8_PREDICTIONS.json` | 三种代价模型的拟合、Wm 平台的线性和二次拟合、8 个新设计的审核方预测 |

全部是回顾性分析：模型形式是看了数据之后选的，只用来登记预测，不能当作已验证的规律。
