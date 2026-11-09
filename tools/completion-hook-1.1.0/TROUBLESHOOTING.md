# 排查与恢复

## No desktop app pipe / No actual caller thread metadata

说明命令没有从有效的Codex桌面对话终端启动，或桌面会话已结束。普通系统终端不会自动拥有这些环境变量。请让该桌面对话里的AI启动工具。不要把别人的管道值复制过来，不要伪造caller线程ID。没有兼容Codex桌面时本发送适配器不能使用。

## 找不到codex-app-tools/server.mjs

本包不附带桌面插件。检查本机Codex桌面是否具有消息工具。若实际安装布局不同，可在`.local/config.json`填写本机`app_tools_server`和`node_path`的绝对路径，再doctor。必须基于本机实际安装文件，不要猜路径或下载不明脚本。

## pip失败 / 没有网络

安装脚本报错后不会发送消息。可在有网络的Windows电脑为同Python版本下载wheel（不要复制整个虚拟环境），在接收电脑使用 `Install.ps1 -Wheelhouse <本机wheel目录>`。依赖的系统/架构/Python版本必须兼容。若锁定版本在包源不可获得，明确报告，不能声称安装成功。修改版本后重跑自检和真实通知测试。

## pending

尚未开始发送，常见于doctor连接失败。修复桌面环境后对原completion_event.json重新deliver即可，不重跑求解、不重建事件。

## sending / delivery_unknown

可能在发送后断线，或进程在登记回执之前退出。先在目标对话查事件ID：

- 找到消息：由接收方检查产物并写receiver_ack.json；即使ledger还显示unknown，也不能重复投递。
- 没找到：仍不能仅凭暂时没看到就推断未送达，检查排队消息/目标ID。必要时由用户决定一次显式恢复通知，并标明可能重复。

工具故意不提供自动清空发件箱或强制重复发送选项，也不宣称严格恰好一次交付。

## accepted但没有receiver_ack.json

桌面已接受，不代表AI已处理。可能当前对话忙碌、排队、账户额度或接收方文件权限问题。检查目标对话；不要自动循环发送。工具不为消除等待而改变对话模型/额度/权限。

## 产物哈希不匹配

事件创建后文件被修改。不要改事件SHA256来掩盖。检查是哪一步仍在写文件；待结果冻结后另建独立恢复目录与新事件，保留旧记录。

## HFSS示例接口不兼容

本包核心不要求AEDT。可选示例依赖明确列出的三个MCP工具；若接收方是别的MCP实现，用runner_integration.py把通知接在自己的已有runner中，不必为了hook替换整个仿真平台。Ansys版本、许可证、端口、核数、PyAEDT兼容性都由本机检查。

## 卸载/搬迁

工具没有服务、启动项、计划任务或全局配置。先确认本工具后台发送/仿真进程已结束，不关闭用户的其他AEDT任务。保留需要的事件和`.local/state`记录，然后再由用户删除解压目录即可。搬迁保留`.local`发件箱可维持去重；新电脑安装应使用原始干净ZIP并重新授权，不能复制本机配置冒充授权。

## 1.1.0：收到完成消息后没有继续

1. 确认runner调用的是 `continuation_guard.py deliver`/`guarded_deliver`，而不是旧的基础deliver。
2. 查原运行目录的 `guard_start_error.json` 以及 `continuation_guard/launch.json`、`claim.json`、`status.json`、`process.log`、`error.json`。
3. `accepted`仅说明桌面收到了消息。检查ACK是否绑定正确事件SHA256；expect-next还要求下一真实worker及输入哈希。运行 `continuation_guard.py inspect --event ... --expect-next` 查看原因。
4. `record-next`拒绝PID时，核对实际worker而不是venv启动器；输入必须含run_dir，进程须有对应的--spec参数。不要绕过校验。
5. 超过15分钟仍未提醒：检查电脑是否休眠、守护进程是否退出、当前桌面管道是否失效，以及是否曾对同事件dry-run占用了claim。
6. 不删除claim或outbox强行重发；先核对目标对话。真实阻塞可record-stop说明，不能以假ACK或假batch_complete消除告警。
7. 下一worker记录为存活后本次守护即结束。它不能发现随后任意时刻的求解器崩溃；下一个runner仍须在成功和异常分支创建新事件。
