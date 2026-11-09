# Fig8 B6交付目录

当前入口：SUMMARY_FINAL.md、FINAL_REPORT.md。执行已结束，不要重新dispatch旧队列。

- predictions_frozen.json / model_freeze.json：首个Analyze前冻结的6项目标、全部参数与预测、50条模型输入的原始哈希。
- SUMMARY_V2.md / dataset_index_v2.json：前三步版本化收尾及旧两项修正标签链接，保留旧52条接受级别。
- blind_results.json：6项盲测原始结果、完整/仅目标覆盖/数值状态、代理与P/R公式误差。
- validated_designs.json：3个完整通过的新参数；另列4个目标覆盖配置（B02不满足等峰）。不得把任意新候选标成已验证。
- dataset_index_v3.json：58条可用几何/32个宽度组合的索引关联；新6条仍独立存放，未加入50条冻结模型训练。
- execution_audit.json：真实资源、预算、16个送达回执、测试、实际图片QA与停心跳核验。
- issues_register_final.json：执行已闭账、科学失败保留、未来研究和可选调谐待新授权。

数值支持是目标相关的原网格有限审查，不是全曲线连续极值、完整多模矩阵或制造容差保证。旧prototype工具仍是冻结历史版本，当前验证状态以本目录报告为准；没有覆盖旧工具、旧原始曲线或均匀数据。

lifecycle_watch.py是运行级外部只读监护扩展，正常求解安静，硬退出且无终态才发单独故障hook；stop只停监护，不终止HFSS。现有hook便携包本轮未重打包。代码依赖本工程的Python/MCP环境，整个目录不是脱离项目的独立便携安装包。
