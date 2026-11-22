# 阶段 9 / R9

计划 `1770e5d`。输入：h₀ = 0.813 mm，tol_h = ±0.038 mm；同一 P_req、中央谷 6.73–6.76 GHz。R8 的 W5R T3 是 T2 的同输入重复解，保留其全部费用。新阶段先做五项历史回放和隔离入口测试，再推送冻结。任何一项回放失败，不允许启动 HFSS。

仅按 R17 §3 运行：W5R T4–T6；通过后 W6R、条件 W7R；在候选中估算五窗交集，只对选中版本补齐。每个新点先做物理输入查重和独立零 Analyze 原生设计验证，再发布绑定记录，14 核 1 组、独立进程串行。9D 的带边预测在实测前提交。原始仿真曲线交集不等于全公差/良率认证；不做 SMA、直接频点或新阶段。

- [R9 冻结](freeze/R17_R9.json) · [五项回放](freeze/REPLAY.json) · [默认离线验证](freeze/OFFLINE_TESTS.json)
- [新宽度初值 / 交付选择附录](appendices/) · [当前状态](CURRENT_STATUS.md)

## 已按 §3.2 停止

W5R T4–T6 三次实测均数值有效但未调准。9C 和 9D 未启动。累计 209/221 个几何，2017 次 Analyze。[中文报告](final/REPORT.md) · [数值附表](final/TABLES.md) · [闭账](final/CLOSURE.json)。
