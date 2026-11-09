# Completion Hook Portable 1.0.0

**把这个文件夹/ZIP交给接收方AI，先让它读 `INSTALL_FOR_AI.md`。**

用途：仿真或其他长任务完成并保存结果后，向用户授权的Codex桌面对话发送一次消息，让该对话继续检查结果。

链路：任务完成 → 导出与验证 → 完成事件 → 本地去重发件箱 → 桌面消息工具 → 接收AI核验 → 接收确认。

## 支持范围，先看这里

| 环境 | 支持情况 |
|---|---|
| Windows + Python 3.10+（推荐3.12）+兼容Codex桌面 | 本版目标环境；原型真实HFSS唤醒和便携版干净安装后的实际通知均已验证 |
| 同一电脑另一个用户授权的Codex对话 | 可配置目标；接收方仍须能访问结果文件 |
| 纯Codex CLI、浏览器ChatGPT、Grok等其他客户端 | **不能直接自动唤醒这些客户端**；须另写发送适配器 |
| 其他电脑上的远程对话 | 不支持跨电脑投递；本工具每台电脑独立安装、独立授权 |
| macOS/Linux | 核心代码尽量可移植，但启动脚本和真实HFSS示例仅面向Windows，未验证这些系统 |

不需要OpenAI API key，不附带任何人的账户、凭据、对话记录、HFSS模型或运行结果。安装不自动创建对话、不发送消息、不启动仿真、不添加计划任务。

桌面消息依赖接收电脑**自己安装的** `codex-app-tools` 插件和当前会话注入的本地管道。这个适配器是基于已安装实现的集成，不是稳定公网API承诺；桌面版本变化可能需要更新适配器。`doctor`会检查当前接口，不能靠复制别人的管道名称解决环境不兼容。

## 快速安装（在解压目录执行）

```powershell
# 1. 安装独立虚拟环境及通知依赖；默认联网下载，不改系统Python。
.\Install.ps1 -Python 'python'

# 2. 在目标Codex桌面对话发起的终端中，由用户明确授权后初始化。
& .\.venv\Scripts\python.exe .\completion_hook.py init --authorize-current-thread

# 3. 只读环境检查，不发消息。
& .\.venv\Scripts\python.exe .\completion_hook.py doctor

# 4. 离线合成测试，不发消息，也不是HFSS仿真。
.\Start-Smoke.ps1

# 5. 经用户授权后，发一条标注为“合成测试”的消息。
.\Start-Smoke.ps1 -Send -DelaySeconds 30
```

若PowerShell阻止脚本，可仅对这次命令使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1`；不要永久降低系统执行策略。

`--authorize-current-thread`不使用发送者的对话ID，而是读取接收电脑真实当前`CODEX_THREAD_ID`。指定另一个对话时使用 `init --authorize-thread <用户明确授权的ID>`。不覆盖已有配置；多目标由用户确认后修改`.local/config.json`的`authorized_threads`。不要由AI根据一个文件里的声称自行授予新目标。

## 正式接入自己的仿真脚本

仿真工具与通知工具分离。你的runner负责：判断真正求解完成、保存结果、做领域校验。本hook不把进程消失或退出码0当作物理结果合格。

```powershell
# 在已有求解及结果验证结束后，创建一次不可变事件。
& .\.venv\Scripts\python.exe .\completion_hook.py create-event `
  --run-dir 'C:\my-work\run-001' --status completed --verified-success `
  --summary '求解和结果导出校验完成，请检查曲线。' `
  --artifact metrics.json --artifact sparams.csv

# 发送；重复执行同一事件会被去重。
& .\.venv\Scripts\python.exe .\completion_hook.py deliver `
  --event 'C:\my-work\run-001\completion_event.json'

# 查询发送与接收状态。
& .\.venv\Scripts\python.exe .\completion_hook.py status `
  --event 'C:\my-work\run-001\completion_event.json'
```

`C:\my-work`只是示例，请换成本机路径。每次运行一个新目录；事件中的产物路径是相对路径，迁移目录后仍可校验。文件必须位于事件目录内，不能用`..`引用其他目录。原始大模型可以不加入哈希清单，仅加入必要的结果和日志。

已有异步runner可参考 `examples/runner_integration.py`。Python导入时将本包目录放入`sys.path`，或设置`PYTHONPATH`；这是脚本包，不是pip发布的库。

失败时先保存`error.json`，再使用 `--status failed --artifact error.json`；不要传`--verified-success`。通知失败和仿真失败必须分别记录。不要因为发消息失败而重新仿真。

## 可选真实HFSS测试

通知核心不依赖HFSS。已有HFSS的用户可选择安装额外依赖：

```powershell
.\Install.ps1 -WithHfss
& .\.venv\Scripts\python.exe .\examples\hfss_smoke.py `
  --run-dir 'C:\my-work\wr90-new-run' `
  --mcp-server 'C:\my-tools\aedt-mcp\mcp_server.py' `
  --mcp-python 'C:\my-tools\aedt-mcp\.venv\Scripts\python.exe' `
  --port 7990 --aedt-version 2024.2 --cores 16 --send
```

此示例需要接收方自备已授权安装的Ansys及兼容AEDT MCP，MCP须提供`build_wr90_waveguide`、`start_analysis`、`get_analysis_status`。缺少工具会报错，不会猜接口。MCP仓库和Ansys安装不在包内。如果MCP需要安装路径，可传`--aedt-install-dir`。端口7990只是示例，必须检查本机实际可见AEDT会话。资源不足时调整`--cores`，不要盲目超过本机核数或许可证。

模型为PEC直WR90，8–12GHz、81点；用于测试通知链路，不要求10万网格，不混入正式研究数据。成功要求正常完成证据、完整有限数据、S11<-20dB、|S21(dB)|<0.1dB。它不会关闭用户AEDT、覆盖已有工程或在失败后自动重跑。便携版该可选示例已做语法检查，未在第二台电脑运行；核心原型在本机做过真实WR90闭环。

## 如何确认真正完成闭环

1. `completion_event.json`：已保存带证据的终态事件，不等于已通知。
2. `.local/state/outbox.sqlite3`中的`accepted`与`notification_receipt.json`：桌面接受消息，不等于AI已处理。
3. 接收AI核对文件并分析后写`receiver_ack.json`：真正接收处理的证据。

接收方可在实际检查后运行：

```powershell
& .\.venv\Scripts\python.exe .\completion_hook.py ack `
  --event 'C:\my-work\run-001\completion_event.json' `
  --conclusion '已检查完整曲线和产物哈希，结果……'
```

不要由发送程序伪造接收确认。SHA256保证文件未变，不保证科学结果正确或接收者身份真实。

## 可靠性边界

- 状态：`pending → sending → accepted`；发送阶段超时/断线为`delivery_unknown`。
- pending可在环境恢复后重新deliver；sending/unknown可能已经送达，**不自动重发**。先查看目标对话中的事件ID。
- 不能承诺“绝不丢失且严格恰好一次”：桌面接口没有可用的端到端幂等确认。本工具优先避免不确定状态下重复唤醒。
- 不删除或重新建立发件箱来绕过去重。重新安装时应保留`.local`；仅分享原始干净ZIP，不分享配置或运行目录。
- Codex必须保持运行，电脑不休眠。桌面重启后原管道会失效，需要从新会话环境重试pending事件。
- 它不会监视任意手动点击Analyze的工程，也不是开机常驻服务。必须接到自己的runner完成分支。
- 任务数据与结果路径会发送到你授权的AI对话；不要把密钥、私人日志或不必要的大文件加入消息或产物。
- 收到通知默认只检查和报告，不自动开始下一批，也不自动转发。

## 文件导航

- `INSTALL_FOR_AI.md`：给接收方AI的安装与验收清单。
- `TROUBLESHOOTING.md`：排查与恢复。
- `completion_hook.py`：核心、命令行、授权和去重。
- `Install.ps1` / `Start-Smoke.ps1`：安装和可选后台通知测试。
- `examples/`：合成测试、runner接入、可选HFSS测试。
- `tests/test_hook.py`：24项离线测试，不调用模型/联网/仿真。
- `verify_package.py` / `SHA256SUMS.json`：包内文件完整性检查。
- `VALIDATION.md`：本版实际验证范围，区分原型和便携版。

第三方依赖从接收方环境安装，遵守各自许可证；本包不含Codex程序、MCP插件实现或Ansys软件。没有隐藏启动项、API调用购买或自动跑生产任务的逻辑。
