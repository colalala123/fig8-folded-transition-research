"""Offline human-readable presentation only; never changes numeric JSON or any verdict."""
from prepare_r9 import *
import shutil

def num(v,n=6):
    if v is None:return '—'
    if isinstance(v,bool):return '是' if v else '否'
    return f'{v:.{n}f}' if isinstance(v,(float,int)) else str(v)
def table(cols,rows):return ['|'+'|'.join(cols)+'|','|'+'|'.join(['---']*len(cols))+'|']+['|'+'|'.join(map(str,r))+'|' for r in rows]

def build():
    out=HERE/'final';ss=read(out/'SELECTED.json');S={s['parent']:s for s in ss};q=read(out/'REVIEWER_SCORES.json');tt=read(out/'TOLERANCE.json');t1=read(out/'T1_SCORES.json');a=read(out/'AUDIT.json');ar=read(out/'ALLOCATION.json');cfg=read(ROOT/'authorization.json')
    old=ROOT/'offline_report_raw_after_replay.md'
    if not old.exists():shutil.copyfile(out/'REPORT.md',old)
    q10=q['Q10'];B=[S['S5R9_'+p] for p in ('B1','B2','B3')];dense=S['S5R9_B1dense']
    L=['# R9 阶段5执行报告（中文）','','## 一、总结','','**R9 已执行完并停止，未进入阶段6。三个形状均达到名义交付目标；B1 的唯一密网格确认也通过。但 ±0.02 mm 联合线性公差估计不能保证 −20 dB，加工鲁棒性尚未解决。**','',
       '- 共使用 **22/26 个几何预算槽**（21个普通几何 + 1个同几何密网格确认），新增 **227 次实际 Analyze**；累计 **173/187**、**1633 次实际请求**。14核、1组、串行，无hook。',
       '- **5A：5/6 研究可用**。W1/W2 的 BW15* 为 **6.627842 / 6.824813 GHz**；按预注册门槛，2.06–2.35 mm 段没有出现所定义的饱和。W3用满三次后中心谷6.68 GHz，偏差40 MHz，不入可用平台或5B宽度选择。',
       '- **N04分配阶梯支持“多分给g更便宜”**：D1c、S1相对6.332 GHz平台的代价为 **3.566、17.301 MHz**；Q7通过。这是近似同折叠量的相关性，不是严格同跨度因果实验，更不是单凭带宽证明纯辐射损耗。',
       '- **Q8：R9冻结的a阈值模型本轮预测胜出**，新可用点RMSE **16.603 MHz**；第二名端头净距33.435 MHz。满足≤25 MHz且领先≥30%的规则，但本轮可用点a≤1.8，未检验其2.39 mm拐点以上机制。',
       f"- **T1四门槛联合 {sum(t['primary_span_four_joint_pass'] for t in t1)}/{len(t1)}**。完整几何反解仍依赖局部HFSS反馈；不能宣称公式一次命中或已有通用神经网络逆向器。",'']
    L+=table(['名义交付','两内峰 dB','中心 GHz','BW20 GHz','BW20内最差S21 dB'],[[s['parent'].replace('S5R9_',''),' / '.join(num(p['S11_dB'],4) for p in sorted(s['inner_peaks'],key=lambda z:z['GHz'])),num(s['center'],2),num(s['BW20']),num(s['S21_min_dB']['BW20'],4)] for s in B])
    L+=['',f"B1确认：**208,845单元**、ΔS=**0.0017234**，两个内峰 **−20.6697 / −20.4308 dB**，均≤−20.0；相对名义峰变化 **+0.1261 / +0.2558 dB**，Q10通过。确认后BW20 **6.466249 GHz**，增加 **11.326 MHz**；中心谷6.73→6.70 GHz。",'',
        '固定a/g、与1b一致的参数口径下，Ws/Lm/Ls1各±0.02 mm、三者联合8个角点的最坏内峰依次 **−19.5955、−19.4237、−19.3851 dB**，**0/3保证−20 dB**。这不是加工认证。','',
        '## 二、执行顺序、冻结和预算','',
        'R9-1冻结并推送 `29a425c` 后才启动W1；5A按 W1→W2→W3→D1c→D3c→S1 执行。W2相对W1增长196.970 MHz，满足W3≥120 MHz的放行条件。D1c/D3c在T4即达到首个可用点，没有使用T5。',
        '5A结束后，R9-2重拟合和三项T1于 `1d8e024` 冻结并推送，再按 B1→B2→B3 执行；最后仅对B1同一几何做一次密网格确认。Wm*=2.35 mm；B3选择N04阶梯最高BW15*的a=1.0、g=2.0 mm。',
        'B1的形状元组已在W2训练中出现，但完整几何/目标纹波不同，因此只是求解前的新完整几何预测，**不称作未见元组盲测**。B2/B3为新宽度组合。所有T1永久保留，不用调参后结果回填其预测。','']
    L+=table(['阶段','几何预算槽','实际Analyze'],[['起始累计',151,1406],['5A',13,129],['5B三个名义形状',8,85],['B1密网格确认',1,13],['本轮合计',22,227],['累计',173,1633]])
    L+=['','普通几何每项≤14请求；确认解13/20请求。所有几何预算、发布、进程角色、原生收敛历史和清理证据逐项保存。剩余槽位不转作新的授权。','',
        '## 三、5A可用点和T1前瞻检验','','BW15* = BW15 − 0.125×(L+20.3) GHz；它不是硬BW20。未调准点保留原始曲线，不用于规律评分。','']
    L+=table(['设计','选定案例','中心 GHz','D dB','L dB','BW15* GHz','研究可用'],[[s['parent'].replace('S5R9_',''),s['case'],num(s['center'],2),num(s['D'],4),num(s['L'],4),num(s['BW15_star']) if s['usable'] else '不评分',num(s['usable'])] for s in ss if s['parent'] in cfg['parent_order'][:6]])
    L+=['','D3c在6.75 GHz边界，沿用既定含边界的R7门槛；未为追求更居中而追加一次。W3中心偏低不是数值失败或物理不可达结论。','',
        'T1评分门槛：谷误差≤30 MHz，D≤0.7 dB，L≤0.3 dB，BW15≤40 MHz。主带宽模型在R9-1冻结为span；BW15误差按计划使用实测L条件化，不重新拟合。完整五模型预测均见 [T1_SCORES.json](T1_SCORES.json)。','']
    L+=table(['T1案例','谷 预测/实测 GHz','D 预测/实测 dB','L 预测/实测 dB','span BW15误差 MHz','四门槛联合'],[[t['case'],f"{num(t['frozen']['central_valley_GHz'],4)} / {num(t['actual']['center'],2)}",f"{num(t['frozen']['D_dB'],3)} / {num(t['actual']['D'],3)}",f"{num(t['frozen']['L_dB'],3)} / {num(t['actual']['L'],3)}",num(t['BW15_conditioned_on_actual_L_errors_MHz']['span'],3),num(t['primary_span_four_joint_pass'])] for t in t1])
    L+=['','D1c/D3c接续原T1–T3的Broyden更新，T4/T5是调参，不是新的独立T1。5B交付选定点也均为调参所得。','',
        '## 四、Q6–Q10预注册评分','',
        '- **Q6通过可评分部分**：W1、W2均在预测区间内；W2≥6.75 GHz，不触发“2.06–2.35之间开始饱和”。W3不可判，不用不平衡/偏移数据替代。',
        '- **Q7通过**：D1c/S1代价均≤50 MHz。四个N04阶梯点a+g约3.0–3.15，不严格等跨度。',
        '- **Q8胜出：a阈值模型**。它是看过阶段4后在R9冻结的模型，不是R8或R7-only的旧模型。不能把本次带宽预测胜出解释为完整反解已成功，也不能据此证明唯一物理原因。','']
    L+=table(['冻结代价模型','5A五个可用点RMSE MHz'],[[k,num(v['RMSE_MHz'],3)] for k,v in sorted(q['Q8']['models'].items(),key=lambda z:z[1]['RMSE_MHz'])])
    L += ['',f"- **Q9通过**：同Wm等纹波平台6.824813 − B1名义BW20 6.454922 = **{q['Q9']['difference_GHz']:.6f} GHz**，在0.30–0.40区间。",'- **Q10通过**：最大单峰网格变化0.255825 dB≤0.35，且两个密网格内峰均≤−20.0 dB。它支持所规定的0.5 dB名义余量，但不替代B2/B3各自确认或加工公差认证。','',
          '![Wm平台](WM_PLATFORM.png)','','![N04折叠分配](ALLOCATION.png)','']
    L+=table(['N04案例','a mm','g mm','Ls1 mm','BW15* GHz','代价 MHz','数据身份'],[[r['case'],num(r['a'],1),num(r['g'],2),num(r['Ls1'],3),num(r['BW15_star']),num(r['cost_MHz'],3),'新调参' if r['case'].startswith('S5') else ('归档参考，L超出当前R7窗口' if not r['current_R7_response_usable'] else '历史调参')] for r in ar])
    L+=['','旧g=1.2点的L=−21.1951 dB：在原阶段2及R9计划中是已接纳的历史候选，但不满足后来R7的L窗口。这里保留为归档归一化参考，**不冒充新R7可用点**。图中空心点及误差条给出0.110–0.140归一化斜率的变化，不是制造置信区间。R9-2构造器比较了全部四个历史/新候选；该口径差异不改变D1c为最高者。五个新可用点的Q8评分不包含这条旧点。','',
        '## 五、三项交付尺寸及曲线','','所有尺寸单位mm；Wm/a/g在各形状调参中固定，未改变P/R去换另一个设计。基板半宽15 mm；完整原生CSV和每次输入见上级results、pre_solve目录。','']
    L+=table(['形状','Wm','Ws','Lm','Ls1','Ls2','Ls3','a','g','端头到微带净距','两端头横向净距'],[[s['parent'].replace('S5R9_','')]+[num(s['geometry_mm'][k],3) for k in ['Wm','Ws','Lm','Ls1','Ls2','Ls3']]+[num(s['a'],1),num(s['g'],2),num(s['tip_line_clearance_mm'],3),num(s['tip_tip_clearance_mm'],3)] for s in B])
    L+=['','![三项S11/S21与B1密网格对比](DELIVERY_CURVES.png)','',
        '相对B1，B2/B3的名义BW20分别少28.256/36.582 MHz，约0.44%/0.57%；不是数学上“完全不掉带宽”。其跨度更紧凑，实际Ls1见表。B3最差内峰−20.50995 dB，只比−20.5门槛低0.00995 dB，应保留完整精度，不将它描述为额外裕量充足。','',
        '## 六、唯一B1密网格确认','']
    n=S['S5R9_B1'];de=dense
    L+=table(['项目','名义网格','密网格','密−名义'],[['单元数',n['mesh'],de['mesh'],de['mesh']-n['mesh']],['ΔS',num(n['delta_s'],7),num(de['delta_s'],7),'均满足各自门槛'],['低频内峰 dB',num(q10['nominal_peaks'][0]),num(q10['dense_peaks'][0]),num(q10['difference_dB'][0])],['高频内峰 dB',num(q10['nominal_peaks'][1]),num(q10['dense_peaks'][1]),num(q10['difference_dB'][1])],['中央谷 GHz',num(n['center'],2),num(de['center'],2),num(q10['center_difference_GHz'],2)],['BW20 GHz',num(n['BW20']),num(de['BW20']),num(q10['BW20_difference_GHz'])]])
    L+=['','几何与选定B1逐尺寸完全相同；只改变网格/ΔS设置，扫频仍为原插值方式，没有添加直接频点或基板加宽确认。B2/B3没有独立密网格验证，其−20dB推断依赖本B1确认和0.5dB名义余量。','',
        '## 七、离线±0.02 mm公差','','采用各设计自身最后可获得的局部J：B1未触发更新，使用初始J；B2/B3按实际触发条件做Broyden更新，不伪造一次更新。主口径与1b相同：固定a/g，δLc=δLs1+2δWs，Ls2/Ls3随派生关系调整。以下为线性估计，不提交新求解。','']
    for p,t in tt['designs'].items():
        L+=['','### '+p.replace('S5R9_','')]
        rows=[]
        for k in ('Ws','Lm','Ls1'):
            x=t['single_parameter_pm002'][k]['plus_response'];rows.append([k+' ±0.02',num(abs(x[0])*1000,3),num(abs(x[2]-x[1]/2),4),num(abs(x[2]+x[1]/2),4),num(t['single_parameter_pm002'][k]['worst_peak_dB'],4)])
        L+=table(['单独扰动','中央谷变化 ±MHz','低内峰变化 ±dB','高内峰变化 ±dB','最坏绝对内峰 dB'],rows)
        L += [f"三变量同时取8个角点：最坏内峰 **{t['worst_inner_peak_dB']:.4f} dB**；中央谷范围 **{t['valley_range_GHz'][0]:.5f}–{t['valley_range_GHz'][1]:.5f} GHz**，不能保证−20dB或原中心窗。",f"J给出的Ws每0.01mm两内峰灵敏度：{[round(v,4) for v in t['Ws_sensitivity_vs_1b']['predicted_per_001mm']]} dB；归档1b实测线性拟合：{[round(v,4) for v in t['Ws_sensitivity_vs_1b']['empirical']]} dB。两者口径一致但来自不同宽度/形状，不将其强制校准为相同数值。"]
    L+=['','**口径边界**：若实际蚀刻只改变Ws而固定Ls2/Ls3，δLc=δLs1−4δWs，同时δa=−δWs、δg=−2δWs。现有J缺独立a/g导数，不能给出完整加工最坏界。[TOLERANCE.json](TOLERANCE.json)另列忽略未知a/g项的条件投影，明确不作认证。不能把固定a/g参数公差表当成所有制造误差。','',
        '## 八、数值、独立复算与披露','','- 22/22原生CSV按既定R2规则独立复算，中央谷、D、L、BW15/BW20最大差 **0**，严格1e−9检查通过；实际看图ACK、14核1组角色、串行无重叠、发布先于求解、原生Lm/Wm回读和旧冻结哈希均通过。详见 [AUDIT.json](AUDIT.json)。',
        '- 旧独立审核辅助函数在B3 T1遇到小局部波纹，先选8.50 GHz局部极大而非两主谷之间真正的8.84 GHz最大内峰。新独立重放器按原R2“相邻显著谷之间最大值”复算，未修改任何原结果、判据或T1预测。差异原样保留在 [LEGACY_REPLAY_DIFFERENCES.json](LEGACY_REPLAY_DIFFERENCES.json)。',
        '- R9-2离线目录创建和旧字段兼容问题在派发前由版本化freeze_5b_v2.py解决；旧文件保留，未消耗Analyze。重复发布B2证明被独占写保护挡下，随后复用原有效证明，没有清理标记、覆盖证明或重复求解。',
        '- 原始status/decision中的`delivery=false`是通用占位字段，正式名义判据看`delivery_pass`及明细；确认解另按R9的−20.0 dB规则，不能把普通−20.5配方检查当作确认判定。详见 [字段说明](../DATA_SCHEMA_DISCLOSURE.md)。',
        '- 默认研究测试11项、R9离线测试11项、独立CSV重放测试3项、旧归档8765文件校验无误；最终验证记录和文件清单见上级FINAL_VERIFICATION.json、FINAL_MANIFEST.json。','',
        '## 九、停止与接续边界','','本轮已正式写入STOP，所有本轮worker/自建AEDT已退出，无新仿真、无自动接续、无hook，**未授权阶段6**。W3仅保留未调准，不扩额；确认通过后不追加调参。未来若继续加工鲁棒优化、直接频点/其它形状独立密网格确认、通用理论P/R或神经网络逆向器，需新计划/授权。',
        '反演P_eff/R_eff等细节保存在SELECTED.json及各项提取文件，但它们是电路拟合量，不是独立理论参数唯一性或完整物理损耗认证。旧均匀数据与旧闭账批次均未操作。','']
    (out/'REPORT.md').write_text('\n'.join(L),encoding='utf-8')
    write(out/'PLOT_QA.json',dict(at=now(),actually_viewed=True,viewer='tools.view_image',files={n:sha(out/n) for n in ('DELIVERY_CURVES.png','WM_PLATFORM.png','ALLOCATION.png')},legible=True,historical_reference_label_explicit=True))
    print('POLISHED',len(L),'lines')
if __name__=='__main__':build()
