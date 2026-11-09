# 当前交付快照（非24点最终报告）

生成时间：2026-10-10T02:12:23.243019+00:00。动态状态见[实时进度](../实时进度.md)。

已按冻结协议核验的合格配置 4/24；保留的数值已核验设计失败 2；其余 18 待处理。四个宽度角点模式检查尚未完成。

原 Broadband 收集器已恢复；新配置正在按可见 AEDT/MCP、16核1任务串行监督运行。源工程及所有历史/失败结果保留。

- `configuration_status_24.csv`：24行真实状态。
- `all_iterations.csv`：已有可读取结果的历史和新迭代；原迭代与实际采用的恢复目录分别记录，数值通过和配置选定分开标记；未选定点不提供正式P/R值。
- `accepted_designs.csv`、`failed_designs.csv`：绑定冻结协议与证据哈希的选定结果。
- `pilot_width_coverage.png`、`pilot_PR_BW_coverage.png`、`pilot_representative_curves.png`：当前覆盖与响应。
- `pilot_fixed_f0_PR_BW_coverage.png`：采用旧均匀特征法同定义 R 的覆盖图；角点检查未完成，无关系拟合。

当前样本不足以判断一般带宽关系。P_response来自S11双峰线性幅度均值；R_side_poles_fixed_f0使用固定6.85GHz及两侧S11外谷的mean(abs(cot))，与旧均匀模型特征法公式一致。R_zero使用本点中央谷，先分别计算左右R再平均，属于另一种诊断口径。R_BW来自S21带宽，不能拿R_BW与原带宽的相关性充当独立新规律。前三者也属于响应提取参数，不等于仅凭几何进行独立预测。只有完整宽度组/折臂配对和角点检查完成后，才能作首批可研究性结论。
