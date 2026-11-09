# 固定P/R达标调谐进度

名义完整主窗通过 **10/48项**（原5项复用、新调谐5项）。
本轮局部模型/搜索暂未解决7项，尚待处理31项。暂未解决不等于物理不可达；不能写成全部达标。

## 新调谐通过项

- N10_A18 / N10_A18_C1：最差S11=-20.126340dB，最小S21=-0.908324dB，中心谷6.75GHz，内峰差0.186814dB。
- N11_A14 / N11_A14_C1：最差S11=-20.333645dB，最小S21=-0.988885dB，中心谷6.71GHz，内峰差0.038156dB。
- N11_A18 / N11_A18_C2：最差S11=-20.429876dB，最小S21=-0.908052dB，中心谷6.73GHz，内峰差0.286877dB。
- N17_A18 / N17_A18_C1：最差S11=-20.063962dB，最小S21=-0.933286dB，中心谷6.73GHz，内峰差0.145639dB。
- N20_A14 / N20_A14_C2_TR1B：最差S11=-20.589298dB，最小S21=-0.979335dB，中心谷6.73GHz，内峰差0.260384dB。

## 暂未解决

- N14_A18：No model-supported original-target candidate within fixed length trust region。详见decisions及quality_notes；原始数据保留。
- N17_A14：No model-supported original-target candidate within fixed length trust region。详见decisions及quality_notes；原始数据保留。
- N18_A14：No model-supported original-target candidate within fixed length trust region。详见decisions及quality_notes；原始数据保留。
- N18_A18：No model-supported original-target candidate within fixed length trust region。详见decisions及quality_notes；原始数据保留。
- N19_A14：No model-supported original-target candidate within fixed length trust region。详见decisions及quality_notes；原始数据保留。
- N22_A14：No model-supported original-target candidate within fixed length trust region。详见decisions及quality_notes；原始数据保留。
- N22_A18：No model-supported original-target candidate within fixed length trust region。详见decisions及quality_notes；原始数据保留。

状态时间（UTC）：2026-10-31T08:37:56.011182+00:00。截至该状态已用Analyze请求269/2236；正在运行项成本可能继续增加。

固定P/R/a/g，仅调Lm/Ls1；工程F盘、临时区D盘。原48首次盲测和模型预测保持不变，新调谐数据不是独立盲测。上述名义插值结果不等于直接频点或制造公差认证。正常求解静默，终态后独立审核、实际看图ACK再接续。
## 用户已暂停本批（最高优先级）
用户指令：先停止本批，等我检查。PAUSE.json已写入，所有本批完成提醒心跳均已关闭，不自动重启HFSS、不接续求解、不清锁，也不影响独立导出任务。工程、缓存、失败记录保留，只有收到用户明确恢复指令后才继续。当前10/48项通过；N15_A18_S为技术中断，4次Analyze及缓存保留。
