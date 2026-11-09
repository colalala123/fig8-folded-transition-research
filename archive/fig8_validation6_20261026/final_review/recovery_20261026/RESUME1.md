# V01G05 AEDT桌面崩溃后的余量恢复

原AEDT91720进程于第12批启动后崩溃，Windows应用错误记录模块ucrtbase.dll、异常0xc0000409。状态查询随后超时，旧fallback自动启动了新AEDT134396但因原工程锁仍在而停止。原锁不删除，原失败事件/state/input及已完成11批44点不改写。

恢复副本J:/f8_V6_261026/V01G05/direct_resume1已从原工程与缓存复制，100001单元的整条收敛历史一致；第12批没有留下可导出的有限频点。新7990服务的MCP只读状态接口已验证正常。只对余下19点做5批（每批最多4点）直接求解，无新几何或自适应。固定新后端PID/创建时间进行附加检查，若已知后端再次丢失就停止并报告，不以原工程锁不存在作为重发Analyze的依据。

准备入口prepare_desktop_resume.py只允许一次，绑定原44点/失败记录/恢复副本及新实现。运行desktop_resume_worker.py --spec对应input。启动后supervise_smallbatch.py --run恢复目录 --seconds 600保存真实16核证据。只在本19点范围运行，保留原已用12次Analyze；额外5次记入resume1_budget.json及主账本resume_analyze_launches_reserved，不撤销失败计数。原小批次主流程最终预计90次，新恢复5次，另有最初整批失败1次与单频诊断1次，直接复核阶段预计总计97次（初值网格控制的调用另计）。

完成后：receive_desktop_resume.py --run恢复目录，实际看叠图，然后acknowledge_desktop_resume.py --run ... --visual-reviewed --note实际观察。该ACK保留主账本原输入SHA/失败目录，另记effective_run指向本恢复结果。普通小批次后续接收用receive_verified.py（见RECEIVER_NOTE），不要用缺少导入路径/冗余state字段的旧入口。

通过后继续dispatch_smallbatch.py启动V02G02、V02G05、V03G02、V03G05，16核单任务串行。最终用finish_effective_report.py解析主账本的有效结果路径，并累计额外恢复Analyze数；不得用固定路径、漏计恢复次数的旧汇总入口。全部真实验收后再收尾。当前用户已授权完成六项，无需重复询问是否启动；后续明确暂停则尊重暂停。
