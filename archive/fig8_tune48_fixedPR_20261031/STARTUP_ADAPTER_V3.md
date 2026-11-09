# 启动操作补充：不修改已冻结输入/源码

首探针N17_A18_S已真实14核开始。旧lifecycle_watch在父ensure仍持有非阻塞文件锁时，子watch抢锁失败；不是HFSS失败。原worker/Analyze没有重派，原被冻结脚本保持不变。独立observer_retry_v2适配器只等待启动锁释放并运行原只读监护，已经核验真实observer。

后续新项用本目录 **run_context_v3.py --context CONTEXT --case CASE**。先检查本轮coordination/protocol.lock不存在及唯一桌面身份/无hf3d，不抢已有工作项的阶段间隙。这个lease检查只用于未开始的后继，不可拿它重跑当前S。v3保存当前启动器哈希并核验真实observer，solver派发语义/14核/冻结参数不变。

终态仍先独立review、实际view_image、真实ACK，再continue_tuning.py离线决定唯一后继/新候选。跨上下文旧心跳只有新后继真实启动后才停。没有新Analyze授权从这个补充文件产生；新阶段人类授权/主计划继续约束所有动作。

若启动器报监护异常但supervised_start/state已存在，**不能重跑run_context/launch_one**；只用finish_start_and_monitor_v2.py读取已有worker和修复只读observer。新的技术异常先保留原证据，不修改worker源码，不清工程锁。
