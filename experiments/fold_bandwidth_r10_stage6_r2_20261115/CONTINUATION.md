# 阶段6当前入口（以真实状态为准，不是新增授权）

**停止更新：P10首次Analyze因地铜/空气盒相交失败，R2已停止，九项有效结果保留。下面流程仅为历史接续说明，当前不得执行。先读STOP_REPORT.md、stop_review/STOP_REVIEW.json和RECOVERY_REQUIREMENTS.md。**

授权来源：用户转交计划分支4be2f26的R10，且明确确认端口截断面固定、高度8h/横宽15.04mm。阶段6做完停，不进阶段7；不发hook。仓库可见性不在此任务内调整。

## 有效版本和冻结

- 仓库分支：`codex/fold-bandwidth-r4-execution`。
- R10-1原冻结fa8f784：派发前JSON元组/列表门禁失败，0Analyze，原记录保留并关闭。
- R1正式冻结c564af8：P1–P8完成实看图审核；P9在Analyze前深拷贝BoundaryProps失败。R1 STOP与所有数据保留；费用闭账8几何/87请求。
- R2工具修复冻结b8af587：值递归复制、原生保存文件独立端口回读、按真实OO属性XSize/ZSize改端口。40项离线测试、P9/P13/P11原生零Analyze预检通过。几何/判据/预测不变，仅接续余下范围。

有效本机运行根：`F:/2026-1/circuit/test/output/fig8_r10_stage6_r2_20261115`。
原R1本机根保持关闭，**不要再调用R1的status/接续或修改其任何文件**：R2已冻结其闭账清单和账本哈希。

## 费用和不可重开范围

R2启动前累计181几何、1720次Analyze；其中阶段6已用8几何/87请求。R2最多新增19几何，原阶段6合计≤27、累计≤200。
普通每物理几何（含数值重试）≤14次，密网格≤20次；14核/1组/串行，普通100000–112000/ΔS≤.005，密网格200000–240000/ΔS≤.002。未用额度不转新点。
P1–P8已从R2派发注册表删除；已完成结果用于公差比较，绝不重跑。其原生CSV/NPZ、审核和实看ACK在R1的results目录，R2配置有可移植的仓库相对路径。
R2若再次出现技术失败，保留证据停止报告，不自动创建R3、不清锁或marker。

## 操作入口（必须先读取状态/进程，不重复派发）

Python：`F:/2026-1/circuit/test/.venv/Scripts/python.exe`；设置PYTHONPATH为`F:/2026-1/circuit/test/output/fig8_ml_dependencies_20261028`。
所有模块用本目录版本，不能退回R1。当前独立worker/HFSS若仍运行，只监看。

1. `controller_stage2.py status <R2根> <case>`；已运行项仅用R2根`watch_readonly.py <case>`监看（不连接AEDT）。
2. 完整done且无failure后，`review_stage3.py <R2根> <case>`；用真正的view_image查看输出曲线，然后才能调用`manage.py ack <case>`。
3. `manage.py finish <case>`；再`collect_stage2.py <R2根> <case>`。控制点不调参。不要把CONTROL完成的passed字段误说成制造/−20dB交付通过。
4. 下一输入必须已冻结且推送，`manage.py publication <case>`核验；随后`controller_stage2.py launch <R2根> <case>`，必须等实际14核证据，不能把Python启动当HFSS启动。
5. EQ父项未通过且有剩余次数时，先按冻结调谐器`prepare_r10.py attempt <parent> <ordinal>`生成新独立输入，提交推送后才发布/求解。

## 之后的条件顺序

剩余6A为P9、P10、P11、P12、P13、P14、N0。七项完成后`manage.py primary`保存N0噪声对照。
若N0最高内峰绝对变化>.05dB：依序准备/推送/求解P1dense、P2dense（以旧B1dense作比较）；否则按明确条件skip二者。
6A完整后`freeze_6b.py prepare`产生M/P_req、C1符号、B1R T1；提交推送，再`freeze_6b.py publish`记录R10-2发布证据，才能解C1。
按已冻结条件用B1或尝试B1R≤3次；若P_req<−21.8则跳过B1R并报告。B1R达标后仅一次密网格和一次C1R；密网格上升偏差取max(0,两峰各自dense−nominal)。
6C先做已冻结W3 T4（只这一项）；可用才W4≤3次。否则skip W4；不替换几何。

## 评分注意

Q11实测Ws半差0.560542dB、Lm半差35MHz（包含的下端点）。冻结代码IEEE比较会把34.9999999999997判在35以下；R1的analysis/P1_P6_PARTIAL.json和PARTIAL_REPORT.md已披露。最终报告保留原始布尔及1e−8编码容差的独立评分，不改预测区间/冻结代码。
M需完整直测来源，不把缺失填零；非线性用直测两侧。预检不是仿真结果，也不是制造认证。
