# Fig8局部P/R候选工具（离线，不启动仿真）

依赖项目内既有Python/numpy/scipy，以及原冻结模型/传输线函数。不是脱离本项目的独立便携包。

## 指定联合通带
```powershell
& "${WORKSPACE}/.venv/Scripts/python.exe" "${WORKSPACE}/output/fig8_PR18_delivery_20261027/design_tool.py" band --bandwidth 5 --s11 -20 --s21 -2 --out "${WORKSPACE}/output/fig8_PR18_delivery_20261027/my_band_result.json"
```
带宽5表示至少覆盖关于6.72GHz对称的4.22–9.22GHz，不保证实际阈值带宽恰好5GHz。也可用`--f-low 4.22 --f-high 9.22`。已有实测匹配、严格经验余量候选、探索候选分别输出；不能把探索候选当已通过。

## 局部公式反解
```powershell
& "${WORKSPACE}/.venv/Scripts/python.exe" "${WORKSPACE}/output/fig8_PR18_delivery_20261027/design_tool.py" formula --peak -20.5 --transmission-bw 7 --arm 1.8
```
这里7是S21的-2dB带宽，不是-20dB联合带宽。新候选无HFSS验收，Lm/Ls1仍可能需要调谐。仅P2.04–2.28、R.430–.475、a1.4/1.8、固定材料和间隔，拒绝外推。

## 重建与测试
先运行本目录build_delivery.py，再运行render_report.py（两个example结果文件需要design_tool先生成）。运行`python -m unittest test_design_tool`时工作目录设为本文件目录。7项离线测试不调用HFSS、hook或网络。

请先读REPORT.md：16项整体有限数值通过、2项未解决，不能称为18项全达标；完整多模和连续极值未认证。独立逆向盲测（原第4步）未执行。
