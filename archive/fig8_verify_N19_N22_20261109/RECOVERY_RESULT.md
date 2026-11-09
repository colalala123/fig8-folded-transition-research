# 唯一受控恢复结果
上次MCP launch_aedt返回38128后桌面消失，未提交Analyze。后端release使用close_on_exit=False；本机MCP Python SDK的stdio子进程在Windows使用Job/process-tree清理，启动器将AEDT作为其子进程，提供了会话退出导致桌面被清理的机制证据，但未捕获上次退出调用栈，不能声称已证明每次退出根因。
本次按明确授权只恢复一次：独立启动可见AEDT2024R2，-grpcsrv 7990，PID30524。之后所有连接及求解仍使用本机AEDT MCP。多个MCP会话关闭及工程配置/重开后桌面保持存活，解决了本次启动阻碍。
旧整批PAUSE保持不动；本分支仅N19_A14_D1和N22_A18_D1。每个13Analyze，合计26，总成本旧269+本分支。无自动重启/额外几何。
