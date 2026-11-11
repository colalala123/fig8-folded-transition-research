# 阶段3功率口径：离线预查，尚未原生验证

阶段2b正在按已冻结程序运行；本文件只记录后续损耗分解的准备，不修改当前求解器、当前模型或旧结果。没有新增Analyze，没有连接当前AEDT。

## 已查到的官方依据

- AEDT 2024 R2 的设计设置允许选择 Generalized / Power 两种S参数后处理定义；切换影响报告和导出，不改变求解状态。[Design Settings for HFSS](https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Content/Modeler/DesignSettingsforHFSS.htm)
- 官方脚本参数名为 `Use Power S:=`，布尔值，经 `SetDesignSettings` 设置；只修改指定新副本的后处理属性，不能盲目把其他设计设置恢复默认。[SetDesignSettings](https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Subsystems/HFSS%20Scripting/Content/SetDesignSettings.htm)
- 有耗端口的实际入射功率不一定等于 Edit Sources 输入幅值；不能把原生广义S矩阵的模平方和未经核验地称作功率。[Incident Power](https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Content/HFSS/IncidentPower.htm)
- 求解器会求所登记的模式，不论其是否传播；端口附近倏逝场可能影响结果。传播性质须以模式/传播常数证据判断，不能因登记了两个模式就把它们都当成传播模式。[Wave Port Placement](https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Content/HFSS/WaveportPlacement.htm)

## 尚需完成的实现/核验

以下为执行方案的候选实现，**不是已经通过的原生证明**：

1. 只在阶段3新副本中，先导出原始广义S、Zo、Gamma，用原始口径做S11/S21/带宽比较。
2. 读取并完整保存现有设计设置；只切换Power S后处理，核对保存后的设置和完整自适应历史。
3. 导出另一份全4×4 Power S，明确不同文件名、归一化证据、模式顺序，保留两套数据，随后恢复原设置并核对。
4. 判断传播/倏逝模式时保留Gamma、Zo；不能凭猜测填入布尔数组。近截止或有耗模态中，若仅这些量不能给出可信判别，保留“功率未认证”，不要伪称全模式功率闭合。
5. 无耗对照必须实证铜全部变为PEC、介质损耗为0且几何不变。即使如此，只有功率口径/入射模态可靠时，剩余功率才能解释为辐射加数值误差。
6. 不因功率后处理验证不足而额外提交未授权Analyze；也不改变已冻结的2b执行程序。

当前阶段2数据仍保持 `full_modal_power_certified=false`。本预查没有补造该认证。
