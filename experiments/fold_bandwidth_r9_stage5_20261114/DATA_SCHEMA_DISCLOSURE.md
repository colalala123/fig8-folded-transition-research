# R9 结果字段口径

冻结 `manage.py` 的通用 `scores()` 中，`delivery=false` 是未使用的占位字段，不是交付判定。原始 FINAL/CURRENT_STATUS 保持原样，不事后改写。

5B 的正式交付判定是 **`delivery_pass`**，由 `delivery_metrics.passed` 独立计算并列出两个内峰和 BW20 内最差 S21，还同时检查中心谷、D、L。运行放行密网格只读取此正式字段。B1 T2 的正式判定为 true；占位字段 false 不构成否定结论。

最终离线 `SELECTED.json` 和中文报告删除占位字段投影，只保留正式 `delivery_pass`。5A 的研究可用判定为 `tuned/usable`，不能用它代替交付判定。更密网格确认采用 R9 的两个内峰 ≤−20.0 dB，不采用名义解的 −20.5 dB 门槛。

这些是输出说明/离线投影，不改变任何冻结求解代码、数值、正式决策、原始记录或预算。

确认解的原始 `delivery_pass=false` 同样是普通名义配方（−20.5 dB、D/L目标）的检查结果，**不是 R9 确认解的通过判定**。R9 确认解门槛原本就是两个内峰 ≤−20.0 dB；最终 `SELECTED.json` 对确认解将名义交付设为不适用，并另列 `confirmation_minus20_pass` 和原始名义配方检查值，`REVIEWER_SCORES.json/Q10` 给出确认结论与差值。不得因该普通配方字段而追加调参或改判据。
