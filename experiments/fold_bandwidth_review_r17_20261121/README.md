# R17 审核：阶段 8（R16/R8）独立复算与调参器回放

离线、只读。不启动 HFSS，不发消息。

- `review_s8.py`：从原生 CSV 复算阶段 8 的 C2W、C3W、W5R T1–T3、C1W5，合并阶段 7 的 W4R、W4R 密网格、C1W，
  求 W4R 五曲线保证带、带边移动和线性预测残差；检查 T3 与 T2 的输入和输出；
  用阶段 8 自己的 `tuning.py` 回放 W5R 的调参（冻结的 R8 规则 vs 顺序割线），给出 R9 的参考 T4；
  用 B1 实测半差换算到调参坐标的带宽梯度，检验 T1→T2 的带宽变化并预测 T4 的 BW20；
  算 R9 放宽中央谷窗后的基点误差，以及 W6R、W7R 的 T1 参考尺寸（调准路径线性外推，`width_extrapolation`）。
- `out/S8_RECOMPUTED.json`：上述结果。

运行（数据在 codex 分支，`S8_EXP` 指向含阶段 7、阶段 8 两个目录的 `experiments`）：

```bash
S8_EXP=/path/to/codex-checkout/experiments python experiments/fold_bandwidth_review_r17_20261121/review_s8.py
```

复算用的是 `6abeb4a`。结论写在 `docs/PLAN_20261121_FOLD_BANDWIDTH_R17.md` 第 1 节。
