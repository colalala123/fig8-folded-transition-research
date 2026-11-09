# 弯折模型理论加机器学习首版基准

52个历史几何、26组宽度。按设计系列固定分割：训练40条，留出测试12条；两折臂不跨组。
先在训练部分内做5折分组验证选模型，再一次性评估留出集。没有将原六项盲测用于训练。
这不是1000条均匀模型的同规模比较，也不代表输入目标带宽后的HFSS命中率。

输入为理论P/R、折臂和独立传输线初始长度；当前学习Lm/Ls1修正，Wm/Ws仍由P/R确定，不把它们的构造性零误差算成机器学习能力。
实际rho/eta由已调好的Ls1计算，本版只用于描述，不输入模型，避免泄漏输出。

|任务|模型|参数|留出MAE|留出P95|
|---|---|---|---:|---:|
|length_residual|quadratic_ridge|delta_Lm_mm|0.015138|0.044606|
|length_residual|quadratic_ridge|delta_Ls1_mm|0.050189|0.130437|
|length_residual|RF|delta_Lm_mm|0.026989|0.048964|
|length_residual|RF|delta_Ls1_mm|0.211765|0.479132|
|length_residual|shared_MLP|delta_Lm_mm|0.012965|0.026994|
|length_residual|shared_MLP|delta_Ls1_mm|0.048489|0.149900|
|forward_performance|quadratic_ridge|S21_minus2_BW_GHz|0.023739|0.047455|
|forward_performance|quadratic_ridge|worse_inner_peak_dB|0.245077|0.392623|
|forward_performance|RF|S21_minus2_BW_GHz|0.127468|0.367903|
|forward_performance|RF|worse_inner_peak_dB|1.128356|2.598057|
|forward_performance|shared_MLP|S21_minus2_BW_GHz|0.019799|0.048033|
|forward_performance|shared_MLP|worse_inner_peak_dB|0.133325|0.274291|

依据训练内分组验证选择：length_residual=quadratic_ridge, forward_performance=quadratic_ridge
注意：forward_performance混合了宽域历史样本，不能用它取代局部18点公式的精度结论。
两条旧插值曲线的带边限制仍保留；本版只用已选定长度及S21/内峰标量标签，不重新认证其全曲线。
神经网络仅为小样本基准，未预设其优于简单模型。按实际验证选用。

验证方法参考：[scikit-learn分组交叉验证](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)。
