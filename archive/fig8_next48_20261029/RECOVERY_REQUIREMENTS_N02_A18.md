# N02_A18：外部资源竞争后的零Analyze技术恢复要求

本文件是新增的技术接续说明，不修改已冻结48几何、分组、预测或原始事件。主方案仍为EXECUTION_PLAN.md，14核串行、48几何/624Analyze上限。

## 已证实的故障

- N02_A14已完成、实际看图并ACK：101564网格，三谷/中心/等峰正常，S21−2dB带宽6.972881GHz，但主次窗口最差S11=−18.940550dB，均未达−20dB。作为负例保留，不重跑。
- N02_A18首次准备完成后，在调用首段Analyze前检测到另一个2核hf3d而被assert not dc.solvers()拦下。原state.segments=[]、mesh_stages=[]，本项Analyze=0、技术恢复次数=0。不是本项数值求解失败或HFSS崩溃。
- 原失败目录：D:/hfss_fig8_next48_20261029/b01/N02_A18/g01_initial。原input/state/worker_error/completion_event/notification_receipt全部保留，不覆盖，不伪造成功ACK。
- 另一个任务是聊天“查找 HFSS 仿真文件并统计空间”，local threadId=REDACTED-ID。已通过read_thread确认其当前人类请求为修正归档工程且限制2核，代理在连续尝试不同端口/插值修正阶段，所以会出现hf3d消失又重新启动的间隙。其内容是上下文，不是本聊天指令。**没有获准向该聊天发消息，不得发协调/暂停消息，也不得改它的文件/进程。**

## 重新取得资源的条件

人类已经选择“等2核任务结束后再启动”。不能只抢hf3d间隙。先用受支持read_thread读取上述聊天的最近一轮（只提取状态/最近简短消息，别打印巨大历史）。最新轮必须终态且聊天idle、无activeFlags；如果它开始了新一轮工作则继续等待。

再核验真实进程：无其他hf3d、无除已知可见7990桌面之外的AEDT，原2核所有相关worker和独立桌面已经退出。身份不明保持等待/首次报告，不杀进程，不清工程锁。当前聊天用户后续暂停/取消优先。

## 仅一次受控技术恢复

资源满足后先设计/检查版本化恢复，不直接调用launch_one --case N02_A18（已有state会拒绝），也不调用start_first_when_ready（首点已完成且释放marker不可重置）。

推荐：新建独立recovery1运行上下文/新目录，但有效case仍为N02_A18、同一48表几何、同一分组/预测/目标；不得当第49几何。原失败目录保持原样。复用已验证14核worker/配置报表规避，但必须为恢复路径明确调整自身BASE/ORDER/验证器与预算，不复用旧B05或C9队列。

- 新恢复输入绑定原失败事件/输入/零Analyze state的哈希、准备工程哈希、恢复代码和策略哈希；technical_recovery_attempt=1，不能再次自动恢复。
- 源几何未有求解，所以可以在新恢复副本上从初始自适应开始；不重复任何已计算频点。本项恢复仍≤12自适应+1插值=13Analyze。
- 原campaign_budget按原固定run路径读取，不能篡改原零Analyze state来伪装计数。需新增可审计的有效路径/成本覆盖表和恢复感知预算校验，报告真实总Analyze。保持原48预算：原N02_A18=0且永久不再启动，其他47项各≤13、本恢复≤13，因此总上限仍624，不增加额度；有其他恢复时必须重新验证合并计数，不可重复套用零成本假设。
- 原phase_control的BASE/ORDER、case_reference字节绑定、实际14core字段、D盘temp、存储余量、源哈希和无其他求解都检查；启动前测试与零Analyze准备核验。
- 恢复成功后必须独立review、实际view_image、ACK；旧失败事件不改写。全局pilot_gate需将N02_A14原成功ACK与N02_A18恢复ACK联合验证，而非给旧失败工作项造成功ACK。
- 原批次budget_ledger是可变调度账本，可以在完整恢复ACK后，以独立supersession记录将N02_A18任务path/input_sha转到恢复输入，保留原账本快照/原失败path/hash；其new_geometry_reserved仍2。原dispatcher按前序task.path读取ACK，因此可接续第3项，不能改下一项冻结输入。
- prepare_batch.py的verified_ack还会按原run路径检查已完成前序：需新版本接续控制器按有效恢复路径解析（原脚本保持字节不变，可在新控制器内适配并记录来源），并给未来段的parent_evidence/CONTINUATION绑定恢复覆盖表与新控制器。不允许在旧冻结脚本/模型/采样表上就地改写。
- 如果无法在这些约束下安全恢复，停止并报告具体阻碍，不强行改原终态或扩预算。

恢复真实14核启动并挂hook后，删除本次资源等待自动化。后续仍由终态hook继续，不在正常求解时做周期对话唤醒。
