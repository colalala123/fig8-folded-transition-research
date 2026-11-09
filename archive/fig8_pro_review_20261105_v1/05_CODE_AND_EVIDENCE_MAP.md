# 源码与证据地图
所有路径相对项目${WORKSPACE}；绝对路径亦见清单。这里是读取索引，不是执行命令。
主调谐目录T=output/fig8_tune48_fixedPR_20261031。
原48目录B=output/fig8_next48_20261029。
evidence/保持原项目相对路径；SOURCES_MANIFEST.json逐个列出副本SHA256。

## 权威状态与授权
T/PAUSE.json、USER_PAUSE_20261031.json优先于历史运行计划。
T/campaign.json、EXECUTION_PLAN.md：原窗口、参数固定、训练顺序、预算。
T/CURRENT_STATUS.json、CURRENT_STATUS.md：历史快照，不等于实时OS查询。

## 科研背景
output/fig8_PR_current_material_20261026/REPORT.md
output/fig8_txline_gui_check_20261027/REPORT.md
output/fig8_inverse_PR_20261027/REPORT.md
output/fig8_theory_ml_20261028/FINAL_SUMMARY.md、EXECUTION_PLAN.md、benchmark_v1/REPORT.md
B/REPORT_FINAL_V4.md、DATASET48_EFFECTIVE_INDEX_V4.json、FINAL48_AUDIT_V4.json、PROSPECTIVE_TEST10_FINAL_V4.json、PAIRED24_DESCRIPTIVE_V4.json。
较老报告的计划、16核等当时设置不覆盖最新调谐14核/暂停。

## 离线算法（只读源码，不import以免顶层副作用）
T/common.py：曲线区间/评分共享依赖。
T/b05_corrector.py：有限差分、三谷识别、带裕量优化、候选判定。
T/continue_tuning.py：决策/选定/后继，含C2更新逻辑。
T/continue_tuning_v2.py、continue_tuning_v3.py：技术恢复适配和真实预算覆盖。
T/decisions/*_c1_decision.json、*_unresolved.json、*_selected.json：原始预测/决策/选定。
T/quality_notes/*.json：边界通过、预测非实测、未用完槽位等说明。

## 执行/预算代码（暂停，禁止运行）
T/run_context_v6.py：历史最新标准入口，旧epoch4身份在N15故障时已失效；不能直接拿它恢复。
T/run_context_v4.py、run_context_v5.py：既有准备/独占/启动/监护适配链。
T/tuning_budget.py、tuning_budget_recovery_v1.py、tuning_budget_recovery_v2.py：基础与恢复真实成本。
T/runtime_registry.json、technical_recovery_registry_v1.json、technical_recovery_registry_v2.json：上下文注册及技术尝试。
T/observer_retry_v2.py、finish_start_and_monitor_v2.py：观察器启动/监督辅助，不构成HFSS根因修复。
T/N20_C2_RECOVERY_AUTHORIZATION.json、N20_RESTART_CONTINUATION_AUTH.json：仅N20特例授权。

## 每个已选定方案的核验链
selected_run/input.json → 原生sparams.csv/all_modes_sparams.csv → convergence/metrics → receiver_verification.json → review图 → receiver_ack.json → notification_receipt.json。
07收集可用文本证据及路径；ACK哈希只证明记录绑定，不替代实际曲线/图片核对。本次只整理已有图审记录，未重新图审。
06保留原48每项原始几何/名义P/R/a/g/分组/标签，以及本轮选定几何；技术失败与原设计失败两列分开。
包不复制大型AEDT工程和缓存；这些保留在原位置。不要根据“包没有工程”误判原缓存丢失。
