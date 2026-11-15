# R11 阶段6 R3 有限恢复

授权：用户转交 `b9fb9b7` 的 R11 并同意第0节；仅阶段6，做完停止，不进7。普通100000–112000单元/ΔS≤.005，密网格200000–240000/ΔS≤.002，14核1组串行，不发hook。

板框是铣边：地铜外框固定 x=±15、y=±25 mm，两种蚀刻符号一致；只偏置板内槽口、线/枝节侧边及开路端。原空气域不改。P10恢复使用原槽，旧1次请求保留，新请求最多13。P9c占用一个W4槽（W4最多2次）。原P1–P9不复算，P9保持有效但单独标注板框内缩，余量只用P9c/P10。

先 `prepare_r10.py prepare`；随后 `preflight_r11.py S6R10_<点>__T1`，按 P10、P9c、P11–P14、N0 全部完成零Analyze原生设计验证，`preflight_r11.py aggregate` 全检闭合。任何原生error或工具故障均停止，不自动建R4。

七点门禁和代码/输入推送到codex分支、`manage.py publication <case>`核验成功后，才由 `controller_stage2.py launch <运行根> <case>` 显式单点派发。运行中只读文件监看；终态后离线审核、实际看图ACK、finish、collect，再派发下一点。所有后续C1/稳健/平台点同样先零Analyze原生验证和推送。

有效运行根：`F:/2026-1/circuit/test/output/fig8_r11_stage6_r3_final_20261115`。Python使用原`.venv`，PYTHONPATH沿用`output/fig8_ml_dependencies_20261028`。旧R1/R2的停止、账本、锁、marker及工程缓存保持原样。

6A完整后按R10做条件密网格、R10-2冻结/推送，再C1→6B→6C。原R10科学冻结保留；R11差异和Q17–Q20在`freeze/R11_R3.json`。未通过验证不能通过改几何绕过。

未发布R3草稿的边界审计误设已闭账（0Analyze），原记录保留。最终R3读取Rad1实际空气盒对象分配，不更改该辐射边界。见相邻草稿目录DRAFT_CLOSURE.json。
