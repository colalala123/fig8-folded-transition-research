# 功率口径与原生预检
原生设置开关/恢复成功，但Power S数据未通过必要的无源功率合理性检查。两者不能混同。此预检0次Analyze，没有改动旧源工程。

HFSS传播模按1W时均功率归一化，依据：
- https://ansyshelp.ansys.com/public/views/secured/electronics/v242/en/subsystems/hfss/Content/HFSS/PeakVersusRMSPhasors.htm
- https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Content/Modeler/DesignSettingsforHFSS.htm

无耗对照在PEC/介质tanδ及电导率为0、模阻抗近实数且传播常数近纯虚数时，保守标记传播模。近纯虚阻抗且近实传播常数标记截止模。其余频点未知，不参与功率余量定量结论。
只统计被明确判为传播的已声明模式。负余量不强行裁为0，而标不可用。未证明所有可能传播模都已包含；不因此宣布“纯辐射功率已精确分离”。有耗数据不使用本判别。
无耗预检初次被没有材料的端口片阻止，修正为跳过空材料片后在独立v2副本通过；旧失败副本保留，没有提交Analyze。
