# HFSS 完成通知 hook

## 目的和范围

用户授权：新建工具；仿真完成后通知当前对话，随后读取结果。默认接收对话为 `REDACTED-ID`。只有用户明确指定时才更换目标。

链路：**HFSS 求解 → 导出并核验结果 → 不可变完成事件 → 本地 outbox 去重 → 已安装的 Codex 桌面 MCP `send_message_to_thread` → 对话读取结果并写接收确认。**

不是30分钟定时任务，也不另外启动一个CLI agent。仿真期间Python每3秒查询求解状态，不消耗模型调用；结束后发一次消息，接收对话的后续分析会正常消耗模型额度。没有设置自启动或系统计划任务。

## 文件

- `completion_hook.py`：事件校验、持久化发件箱、桌面消息投递。
- `run_wr90_smoke.py`：独立WR90真实HFSS测试，通过现有AEDT MCP建模和启动求解。
- `test_completion_hook.py`：9项单元测试；均已通过。
- `recover_result.py`：显式恢复已有求解的导出，不会调用Analyze或覆盖原失败事件。
- `outbox.sqlite3`：**本工具自己创建**的发件箱，不是Codex内部数据库。
- `smoke_launch.json`：真实测试PID和结果目录。
- `smoke_stdout.log` / `smoke_stderr.log`：测试日志。

## 真实测试模型

WR90直波导：22.86×10.16×50 mm真空通道，PEC壁，两端各一基模端口；10GHz自适应、最多6轮、ΔS=0.02；8–12GHz共81输出点的插值扫频。16核、一个任务，AEDT 2024 R2现有可见会话7990端口。

这是快速通知链路测试，不需要10万网格，不属于均匀或弯折样本。没有改动24配置队列或研究验收协议。

成功事件要求：实际正常完成消息、已求解结果、81个有限且频率正确的数据点、最大S11<-20dB、|S21(dB)|<0.1dB，并记录到16核单任务实际求解命令。异常会发`failed`任务事件，不伪装成成功；导出失败也不会自动重跑仿真。

## 验收层次

1. 单元测试通过：逻辑测试成功，不等于真实通知成功。
2. `completion_event.json` 的 `status=completed`：仿真和结果校验成功。
3. `notification_receipt.json` 的 `state=accepted`：桌面消息工具返回成功，不等于对话已经处理。
4. 接收对话检查结果后写 `receiver_ack.json`：**完整闭环的最终证据**。这一步不由发送脚本伪造。

如果当前对话正在执行，通知可能排队；本轮结束后才会处理。实际投递/唤醒能力以真实测试为准，不能只凭读接口成功就宣布完成。

## 使用

在当前Codex桌面会话发起的终端环境中：

```powershell
$python = '${WORKSPACE}\.venv\Scripts\python.exe'
$hook = '${WORKSPACE}\output\hfss_completion_hook_20261022'
& $python "$hook\completion_hook.py" probe
& $python -m unittest discover -s $hook -p test_completion_hook.py -v
```

当前试验已经启动，不要重复执行。另建新试验时必须使用新的、尚不存在的目录：

```powershell
& $python "$hook\run_wr90_smoke.py" --run-dir '${WORKSPACE}\tmp\hook_wr90_NEW'
```

## 后续接入24配置

先完成本次闭环，再把 `completion_hook.deliver(event_path)` 接在现有runner的“结果导出并校验、最终状态保存”之后。可以在一次配置终止后发事件，不能在每个进程消失或每次轮询时发消息。

事件JSON格式可参照本次`completion_event.json`：schema_version=1、唯一run_id、target_thread_id、created_at、status(completed/failed/cancelled)、summary、purpose、verified_success和artifacts列表。每个artifact含绝对path与sha256，必须处于事件同目录内。失败也需有日志证据。

现阶段接收提示只授权检查与报告，不授权自动运行24配置、重试或转发。生产调度策略需在接入时单独明确。

## 防重复与异常恢复

- 同一个run_id与接收对话只投递一次；输入改变则拒绝冒充同一事件。
- 连接探测失败时保持pending，可在恢复桌面会话后重新运行deliver。
- 开始发送后断线或超时，记delivery_unknown；不自动重发，因为消息可能已被桌面接收。
- 进程在发送阶段崩溃会留下sending，同样不自动重发。应先在目标聊天确认是否已有事件ID。
- 同一事件重复调用会显示duplicate_suppressed，不再次唤醒。
- 仿真成功与通知失败分别保存，通知失败不触发重新仿真。

仅对仍为pending的事件可以安全重试：

```powershell
& $python "$hook\completion_hook.py" deliver --event '运行目录的绝对路径\completion_event.json'
```

## 运行依赖与限制

使用本机已安装`codex-app-tools/0.1.6/server.mjs`的MCP接口和桌面注入的`CODEX_APP_TOOLS_PIPE_PATH`、`CODEX_MCP_NODE_PATH`、真实`CODEX_THREAD_ID`。不保存认证密钥，不编辑Codex聊天数据库，不模拟键盘发送。

Codex桌面必须保持运行，电脑不能休眠。桌面重启后原管道会失效；从新会话环境重试pending事件即可，已进入不确定发送阶段的事件需先人工核对。此工具不是独立于Codex运行的网络webhook服务；普通手动终端若缺少桌面注入环境，无法自行唤醒对话。

安装版本升级可能改变工具桥接接口，先运行probe再使用。接入的是本机已安装插件，不声称是长期稳定的公网API。

当前只覆盖由本runner/已接入runner启动的任务，不会自动监视任意手动点击Analyze的工程。仿真进程或hook被强制终止、断电等情况不保证有终态事件；应保留state和日志人工恢复。

## 本次实测记录

- 原始运行目录：`${WORKSPACE}/tmp/hook_wr90_20261022_234223`。
- 实际HFSS求解已完成；首版导出代码错误调用`data_imag`，失败事件`6549ed270f3c335fcea0e47f`已自动到达本对话，已核验哈希并保存`receiver_ack.json`。证明真实错误通知链路可用，不是手工发送或假回调。
- 已改成当前PyAEDT的`get_expression_data(..., formula='real'/'imag')`。在原求解上恢复导出，**没有重新求解**；新证据位于原运行目录的`export_recovery/`，原失败证据未覆盖。
- 恢复结果：81点，8–12GHz；最大S11=-55.4215dB；S21约-0.0000470至+0.0000634dB；功率平衡最大残差约1.46e-5。简单模型核验通过。
- **成功事件已完成空闲唤醒验证**：2026-10-22 23:48:02（日本时间）消息被桌面接受；上一轮已结束、没有用户追加消息，hook自动唤醒当前对话。接收方于23:48:19重新校验全部产物哈希，并独立从CSV计算S11/S21，保存`export_recovery/receiver_ack.json`。
- 成功事件ID：`8ff1874c913db1732774980a`。该测试使用一次性30秒投递延迟，生产默认延迟0秒。失败通知、成功通知、空闲唤醒、接收后检查结果均已实测；未启动24配置。
