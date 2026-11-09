# 最终直接复核准备情况

初值执行期间已在本批final_review目录准备独立的4点小批次直接复核实现，没有启动直接求解。

前3项初值的接收审查、native参考兼容性、实际峰谷带边选频及比较函数自检已通过；见final_review/preparation_verification.json。频点为63/62/63，每项拆成16次Analyze，每次不超过4个频率。自检使用已有插值数据，不是独立EM验收。

最后一项I02G05完成后：

1. 按父目录CONTINUATION完成review_phase_geometry、实际看图及acknowledge_review，确认四项设计通过。
2. 若四项均通过，运行final_review/initialize_direct.py冻结四个真实来源和全部直接频点；不重新运行prepare_direct_review.py，不改初值冻结实现/输入。若最后一项设计未过，则先在原授权预算内准备独立有界长度调谐子段，不能带病进入最终复核。
3. 按final_review/CONTINUATION.md运行dispatch_smallbatch.py --case I01G02 --solve，随后supervise_smallbatch.py保存16核真实启动证据。第一项最初两个频率批次应实际观察其网格不变、导出完整且native比较正常，再让该有限任务继续。
4. 以后每个完整配置复核完成时hook通知本聊天，receive_verified.py和实际看叠图后ACK，逐项接续。尚未配置无条件定时通知，心跳仍仅在完成送达后300秒无新真实求解时检查对话。

直接阶段实际执行器是smallbatch_worker.py；phase_final_direct.py保留的整批入口不用于派发，仅复用它的频点和比较函数。不要绕过小批次调度器。

新增几何始终计入父批最多4项/配置、共16项的预算；缓存直接核验不增加几何数，Analyze另记。结束后还需完整结果与等带宽/匹配对比报告及心跳关闭证明。
