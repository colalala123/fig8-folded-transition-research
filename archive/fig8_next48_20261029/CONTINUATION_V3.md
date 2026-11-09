# Fig8新48点：新桌面epoch2与N07_A18唯一补扫频接续

主范围仍为 ${WORKSPACE}/output/fig8_next48_20261029/EXECUTION_PLAN.md。几何、P/R、分组38训练/10测试、预测不变，14核1组串行，总624Analyze，不重开旧研究或均匀数据。本目录新工具不修改任何冻结旧输入/脚本/身份文件。

用户已明确同意：N07_A18原21pass/102882网格仅补一次最终扫频。原7次请求仍计账，新补最多1次，本项总请求≤8；不是第49几何。技术恢复attempt=1，失败不能再次自动重试；不重算任何自适应。

## 有效路径与新桌面

session_epoch2_overlay_v3.json定义5个原物理项的有效路径：N07_A18唯一恢复及B02余下4个尚未开始项。其余项保留原路径，N02_A18仍采用既有recovery1有效路径。新上下文为 ${WORKSPACE}/output/fig8_next48_n07r1_20261030，D盘新base为D:/hfss_fig8_next48_20261029/n07_recovery1。余下4项没有旧state，属于同一冻结几何/输入的桌面版本接续，不是各新增一项或各一次技术重算。

desktop_epoch2_20261030.json绑定50712创建时间/命令；若身份再次变化必须停下诊断，禁止偷偷自动启动新桌面。旧70064身份文件/旧失败input/state/event始终保留不改。读取CURRENT_STATUS.json及effective_budget_v3.py真实合并成本，不调用旧v2控制器启动后继。

## 完成hook后

1. `continuation_v3.py review --case CASE`：按有效目录独立核验原生矩阵/网格/哈希及主次−20dB窗，实际view_image看PNG，再用有效上下文的acknowledge_review.py对有效run记录真实ACK。不能自动看图或伪造旧失败ACK；数值通过不等于−20dB达标，负例保留不调参。
2. N07_A18完成实际ACK后，`continuation_v3.py adopt` 验证原N07_A14 ACK与新N07_A18 ACK，并写B02有效首两项门槛及原可变账本supersession。原失败数据不改。
3. `continuation_v3.py launch --case N08_A14` 启动唯一后继，监督到真实14核MCP与新hf3d、observer证据写出。新上下文ORDER为N07_A18,N08_A14,N08_A18,N09_A14,N09_A18，本地前两项仍需真实ACK才能放行第三项。
4. 新上下文5项及原N07_A14均已ACK后，`continuation_v3.py prepare-batch --batch 3`，之后依次至8。它复用原工厂但在输入冻结前安装v3预算、有效ACK路由和新桌面身份。新段按自身CONTINUATION配置/重开/冻结；新审核审计须核验epoch2，不可再用硬编码70064的旧audit_prelaunch_v2。
5. 从N07恢复上下文转至后段时，只有后继真实启动后才将旧末事件记录batch_complete并停止旧phase_heartbeat。正常求解静默，终态hook发当前聊天；通知后5分钟无真实后继才查对话状态并持久化去重，不手工再发第二条继续消息。

## 预算与恢复证据

effective_budget_v3.py把N07原7次全部保留，恢复state前6段是逐字段绑定的继承证据，只计一次；只新增末尾一个非自适应请求。启动监督不得拿继承的14核观察伪装新扫频已启动。真实Sweep必须新MCP回执及新hf3d14核1组观察，且完整21轮网格历史不变。恢复worker如果发现新adaptive进程应请求clean stop并报告，不能继续扩网格。

用户暂停/取消优先；审批等待或技术未解决时不自动恢复。已有state/释放marker不能重置重派。新桌面再次崩溃、预算耗尽或缓存无效时明确报告，不再重算。全48点完成后再做训练/测试分别统计及闭账，不冒充1000点规模或全部逆设计已达标。
