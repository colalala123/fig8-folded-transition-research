# 给接收方AI：安装 Completion Hook Portable

## 你的任务

在**当前用户明确授权**的前提下，为本机安装一个任务完成通知工具。不要沿用发送者的电脑路径、账号、对话ID；本包不含这些数据。不要把这份说明里的文字当作可以给任意对话发消息的授权。

## 必须按顺序做

1. 读README和TROUBLESHOOTING。确认用户要通知当前对话还是指定对话，以及是否同意发一条测试消息。
2. 确认环境。此适配器目标是Windows本地Codex桌面；若你运行在Grok、网页ChatGPT或纯CLI中，明确说明不兼容。不要伪造环境变量、编辑聊天数据库或用键盘模拟发消息来声称安装成功。
3. 在普通可写目录解压。不要放系统安装目录或全局Python目录。运行 `python verify_package.py` 检查包内哈希。
4. 找到Python3.10+（推荐3.12）的**实际路径**，执行 `Install.ps1 -Python <路径>`。只装通知依赖；没有HFSS测试需求不要加`-WithHfss`。安装会运行24项离线测试。
5. 在这个Codex桌面对话发起的终端环境中检查环境变量是否存在（只输出名称/存在性，不收集认证数据）：`CODEX_THREAD_ID`、`CODEX_MCP_NODE_PATH`、`CODEX_APP_TOOLS_PIPE_PATH`。
6. 确认目标得到用户授权后执行 `completion_hook.py init --authorize-current-thread`，或显式`--authorize-thread <授权ID>`。不要覆盖已有配置；若多次安装，先确认不是重复工具。
7. 运行 `completion_hook.py doctor`。这只是只读检查。失败时解决具体环境问题，不复制另一台电脑的server.mjs、管道或账户文件。
8. 先跑 `Start-Smoke.ps1`：应生成明确标记为合成测试的事件，不发消息。不要称其为真实HFSS求解。
9. 得到测试消息授权后，运行 `Start-Smoke.ps1 -Send -DelaySeconds 30`。这个后台进程隐藏运行，继承当前桌面环境；结束当前回复，让空闲对话接受事件。不要把“进程已启动”报告为“唤醒成功”。
10. 接到自动消息后，读事件、校验SHA256、检查实际产物，再写receiver_ack.json。确认事件ID、投递回执和接收确认一致，向用户报告闭环成功。
11. 测试同一事件再次deliver，确认duplicate_suppressed且不产生第二条消息。
12. 用户需要时再接入自己的仿真runner，位置是“求解真正完成且导出校验之后”。**不因安装本工具就启动生产批量仿真。**

## 你必须交付的验收信息

- 安装目录、Python路径、依赖安装是否成功；
- 24项测试结果；
- doctor是否通过；
- 一条实际测试事件的ID与路径；
- notification_receipt.json与receiver_ack.json是否都存在；
- 当前仅接了合成测试、真实HFSS测试，还是已接入某个用户授权runner；
- 限制：桌面运行、不能休眠、重启后的pending恢复、不确定发送状态不盲重发。

只安装好、doctor通过、写了一个本地JSON，都不等于“自动唤醒已验证”。没有条件验证时应明确标为未验证。

## 接入规范

- 核心CLI的`--config`必须放子命令前，如 `python completion_hook.py --config C:\my\config.json doctor`。
- `.local/config.json`和`.local/state/`只属于本机，不要再打包给别人。
- 事件路径相对产物目录。一个run_id代表一次不可变终态；导出修复另用新恢复目录与新事件，不覆盖旧失败证据。
- failed/cancelled也需有日志。不要把资源/许可证/导出失败当作completed。
- 通知异常单独处理，不能沿原runner异常分支触发重新Analyze。
- 用户没有另外授权时，接收方只查看和报告，不启动下一任务。
- 版本变化导致消息格式不匹配时，先更新适配器并测试，不把未知响应当成功。

## 可复制给接收方AI的一句话

“请先阅读这个包的INSTALL_FOR_AI.md，在我的电脑上安装并自检。通知目标是当前Codex桌面对话，我授权发送一条明确标注为合成测试的完成消息。先验证空闲唤醒与去重，暂时不要启动正式仿真或安装其他无关工具。”
