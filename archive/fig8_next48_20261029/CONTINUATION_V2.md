# 新48点：N02_A18一次恢复后的版本化接续

主范围仍为 EXECUTION_PLAN.md：48个原几何、38训练/10测试、14核单组串行、每物理几何最多13 Analyze，总624。不调谐，不追加直接频点，不操作旧闭账或均匀数据。

所有下列脚本位于 ${WORKSPACE}/output/fig8_next48_20261029。

1. 先读 CURRENT_STATUS.json、recovery1_overlay.json、RECOVERY_REQUIREMENTS_N02_A18.md。effective_budget_v2.py 合计原路径与恢复路径成本；原失败N02_A18输入/state/event永久保留且零Analyze，绝不伪造原成功ACK。
2. 终态后运行 `continuation_v2.py review --case CASE`，按有效路径生成科学标签/图。标签已存在时不得覆盖；先核验当前状态。实际 view_image 看图，再使用**有效上下文** acknowledge_review.py 对**有效run**记录真实观察。operation成功不代表−20dB达标，保留负例。
3. N02_A18恢复ACK后运行 `continuation_v2.py adopt`，它独立验证两份真实ACK、写全局pilot_gate、保存原B01可变账本快照、记录supersession并将原调度账本第二项转至恢复路径；原失败工程数据不变。不得手工造ACK。此操作不能先于真实恢复ACK。
4. 之后 `continuation_v2.py launch --case N05_A14`，再按原冻结ORDER。脚本先检查真实合并成本再进入原单项派发/真实14核监督。已有state不重发。冻结B01旧worker虽按旧路径计总数，但各物理几何仍≤13，原失败项0+唯一恢复≤13，因此624硬上限不被突破；每次新释放用覆盖账本报告真实成本。
5. 第一段6项实际ACK后 `continuation_v2.py prepare-batch --batch 2`（以后依次至8）。它在内存适配旧工厂的有效ACK路径，不修改冻结旧脚本；新段输入冻结**之前**将预算检查改为effective_budget_v2并绑定覆盖表/接续控制器/真实ACK。若出现部分准备输出则先检查，不重建覆盖。
6. 新段按自己的CONTINUATION完成 desktop_preflight、verify_live_hook、configure_projects --all、prepared_reopen、finalize_and_authorize。后继使用本版本launch/review/prepare-batch命令，不能回旧工厂检查失败原路径。
7. 新恢复上下文 ${WORKSPACE}/output/fig8_next48_r1_20261029，仅N02_A18，run为D:/hfss_fig8_next48_20261029/recovery1/N02_A18/g01_initial。不是第49几何；technical_recovery_attempt=1，失败不得再自动恢复。原项无求解缓存，所以从未求解准备工程的字节相同副本开始。
8. 完成hook仅向当前聊天发消息；正常求解静默，通知后5分钟无新真实仿真才检查对话是否中断并持久化去重。恢复转回B01后，先见到真实后继启动再用恢复上下文phase_heartbeat.py stop停止旧心跳。任何失败先读真实进程/缓存，不清锁、不重复Analyze。用户暂停/取消优先。
9. 完成后训练/测试分开总结、保留负例，数据采集不冒充所有点达标或与1000点等规模。
