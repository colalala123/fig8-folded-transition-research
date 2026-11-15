"""Post-STOP offline audit/report only. Never imports or starts an AEDT session."""
import math,shutil
from common_stage2 import *
from prepare_r10 import ROOT,INITIAL
from manage import baseline,measurement,measured_case_path
import independent_response as ir,tolerance_analysis as ta

def build():
    import psutil
    cfg=read(ROOT/'authorization.json');stop=read(ROOT/'STOP.json');out=HERE/'stop_review';out.mkdir(exist_ok=False)
    if stop['case']!='S6R10_P1dense__T1':raise RuntimeError('unexpected stop')
    if (ROOT/'runs/S6R10_P1dense/attempt_001').exists():raise RuntimeError('dense should not have been prepared')
    b=baseline();ms={};rows=[];replay=[];maxdiff=0.
    for n in [f'P{i}' for i in range(1,10)]+['P9c','P10','P11','P12','P13','P14','N0']:
        dec=read(ROOT/'decisions'/('S6R10_'+n+'_FINAL.json'));c=dec['selected_case']
        w=REPO/cfg['inherited_public_result_paths'][c] if c in cfg.get('inherited_public_result_paths',{}) else HERE/'results'/c
        m=measurement(w);ms[n]=m;q=ir.metrics(*ir.load_csv(w/'native/full_modes.csv'))
        diffs={}
        for key,k2 in [('center_GHz','valley_GHz'),('low_peak_dB','peak_lo_dB'),('high_peak_dB','peak_hi_dB'),('BW20_GHz','BW20')]:
            if m[key] is None or q[k2] is None:
                if m[key] is not None or q[k2] is not None:raise RuntimeError('replay null mismatch '+n)
                diffs[key]=None
            else:
                diffs[key]=q[k2]-m[key];maxdiff=max(maxdiff,abs(diffs[key]))
                if abs(diffs[key])>1e-10:raise RuntimeError('independent raw CSV replay mismatch '+n)
        f,s11,s21=ir.load_csv(w/'native/full_modes.csv');edge=q['BW15_edges'];s21bw15=None
        if edge is not None:
            import numpy as np
            s21bw15=float(np.min(s21[(f>=edge[0])&(f<=edge[1])]))
        rows.append(dict(point=n,case=c,measurement=m,S21_min_in_BW15_dB=s21bw15,
            differences={k:(m[k]-b[k] if m.get(k) is not None and b.get(k) is not None else None) for k in ta.RESPONSES},
            highest_peak_rise_dB=ta.highest(m)-ta.highest(b),review_path=w.relative_to(REPO).as_posix(),
            mesh=read(w/'SUMMARY.json')['record']['mesh_cells'],delta_s=read(w/'SUMMARY.json')['record']['delta_s']))
        replay.append(dict(point=n,case=c,raw_csv_sha256=sha(w/'native/full_modes.csv'),independent=q,differences=diffs))
    primary=read(ROOT/'decisions/6A_PRIMARY.json');analysis=ta.stage6a(b,{k:v for k,v in ms.items() if k!='P9'})
    if analysis['complete'] or not analysis['conditional_dense_required']:raise RuntimeError('must remain incomplete until conditional dense')
    sides={};linearity={}
    for source,(a,z) in ta.PAIRS.items():
        chosen=max([a,z],key=lambda n:ta.highest(ms[n]));sides[source]=dict(worst_point=chosen,rise_dB=max(0.,ta.highest(ms[chosen])-ta.highest(b)),signed_rise_dB=ta.highest(ms[chosen])-ta.highest(b))
        linearity[source]=ta.linearity(b,ms[a],ms[z])
    rss=math.sqrt(sum(sides[k]['rise_dB']**2 for k in ('etch','er','h')));noise=primary['noise_dB'];provisional_M=rss+(noise if noise>.1 else 0.)
    req=-20-provisional_M-.256-.1
    provisional=dict(ordinary_grid_RSS_dB=rss,noise_dB=noise,noise_linear_addition_dB=noise if noise>.1 else 0.,
        M_dB=provisional_M,P_req_dB=req,conservative_linear_margin_dB=sum(sides[k]['rise_dB'] for k in ('Ws','Lm','Ls1','Wm','er','h')),
        release_R10_2=False,status='Ordinary-grid arithmetic only; conditional dense P1/P2 missing. NOT R10-2 freeze or dispatch authorization.',
        expected_R10_6B_rule_if_confirmed='skip_B1R_ripple_only_not_cost_effective' if req<-21.8 else 'follow_R10',
        corner_sides={k:sides[k]['worst_point'] for k in ('etch','er','h')})
    q11ws=abs(ms['P1']['high_peak_dB']-ms['P2']['high_peak_dB'])/2
    q11lm=abs(ms['P3']['center_GHz']-ms['P4']['center_GHz'])/2*1000
    p10rise=ta.highest(ms['P10'])-ta.highest(b);p10bw=(ms['P10']['BW20_GHz']-b['BW20_GHz'])*1000
    comparison={k:ms['P9c'][k]-ms['P9'][k] for k in ta.RESPONSES}
    er_delta={n:(ms[n]['center_GHz']-b['center_GHz'])*1000 for n in ('P11','P12')}
    Q=dict(
        Q11=dict(raw_frozen_endpoint_pass=.45<=q11ws<=.95 and 35<=q11lm<=60,encoding_audit_pass=.45<=q11ws<=.95 and 35-1e-8<=q11lm<=60+1e-8,
            Ws_high_half_dB=q11ws,Lm_center_half_MHz=q11lm,note='Prediction interval unchanged; 10MHz frequency grid quantizes half-shifts to 5MHz. IEEE endpoint artifact retained.'),
        Q12=dict(passed=sides['etch']['rise_dB']>=sides['Ws']['rise_dB'],etch=sides['etch']['rise_dB'],Ws=sides['Ws']['rise_dB']),
        Q13=dict(passed=all(20-1e-8<=abs(v)<=50+1e-8 for v in er_delta.values()) and er_delta['P11']>0 and er_delta['P12']<0 and sides['er']['rise_dB']<=.25,er_center_delta_MHz=er_delta,highest_rise_dB=sides['er']['rise_dB']),
        Q14=dict(passed=sides['h']['rise_dB']>=max(sides[k]['rise_dB'] for k in ('etch','er','h'))),
        Q15=dict(assessable=False,reason='6B not started'),Q16=dict(assessable=False,reason='6C not started'),
        Q17=dict(passed=-.25<=p10rise<=.1 and -60<=p10bw<=-20,highest_rise_dB=p10rise,BW20_delta_MHz=p10bw),
        Q18=dict(passed=ta.highest(ms['P9c'])>ta.highest(ms['P10'])),
        Q19=dict(passed=all(abs(comparison[k])<=.05 for k in ('low_peak_dB','high_peak_dB')),P9c_minus_P9=comparison,
            caveat='Includes board outline and remeshing. N0 >.05dB; cannot isolate a boundary-only effect.'),
        Q20=dict(assessable=False,reason='Conditional dense and R10-2 pending; 6B not started',ordinary_grid_arithmetic_in_predicted_interval=-21.3<=req<=-20.7,ordinary_grid_P_req_dB=req))
    records=[]
    for n in ['P10','P9c','P11','P12','P13','P14','N0']:
        c='S6R10_'+n+'__T1';w=case_dir(ROOT,c,cfg);rec=read(w/'RUN_RECORD.json');v=w/'evidence/design_validation'
        if not read(v/'VERDICT.json')['passed']:raise RuntimeError('worker native validation failed '+c)
        shutil.copytree(v,out/'worker_native_validation'/c)
        records.append(dict(case=c,record=rec,actual14core=read(w/'evidence/actual_start_observed.json')['actual_14core_1group'],
            roles=[p.name for p in (w/'evidence').glob('*_role_check.json') if read(p)['passed']]))
    process=[dict(pid=p.pid,name=p.info['name'],create_time=p.info['create_time']) for p in psutil.process_iter(['name','create_time']) if (p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe')]
    if process:raise RuntimeError('unexpected active AEDT/HF3D after stopped closure')
    ledger=[read(p) for p in (ROOT/'ledger').glob('Analyze_*.json')];geoms=list((ROOT/'ledger').glob('geometry_*.json'))
    if len(ledger)!=77 or len(geoms)!=6:raise RuntimeError('R3 cost mismatch')
    costs={r['case']:sum(x['case']==r['case'] for x in ledger) for r in records}
    if sum(costs.values())!=77 or costs['S6R10_P10__T1']+1!=13:raise RuntimeError('per-case ledger mismatch')
    for r in records:
        if costs[r['case']]!=r['record']['Analyze_requested'] or not r['actual14core']:raise RuntimeError('actual cost/start mismatch')
    d=dict(at=now(),stop=stop,all_R11_complete=False,all_seven_ordinary_solved_reviewed=True,completed_new_controls=7,
        stage6_geometry_used=16,stage6_geometry_cap=27,cumulative_geometry=189,cumulative_geometry_cap=200,
        stage6_actual_Analyze=174,cumulative_actual_Analyze=1807,R3_actual_Analyze=77,R3_new_geometries=6,P10_aggregate_Analyze=13,
        per_case_costs=costs,rows=rows,ordinary_per_source=sides,ordinary_linearity=linearity,provisional_margin=provisional,Q=Q,
        raw_CSV_replay=dict(cases=len(replay),maximum_abs_difference=maxdiff,results=replay),
        ordinary_primary_gate=primary,stage6a_gate=analysis,current_native_processes=process,automatic_R4_created=False,
        R10_2_frozen=False,C1_started=False,stage6B_started=False,stage6C_started=False)
    write(out/'REVIEW.json',d);write(out/'WORKER_RECORDS.json',records)
    shutil.copyfile(ROOT/'STOP.json',out/'STOP.json');shutil.copyfile(ROOT/'DENSE_COMPATIBILITY_FAILURE.json',out/'DENSE_COMPATIBILITY_FAILURE.json')
    def f(v,p=6):return '—' if v is None else f'{v:.{p}f}'
    lines=['# R11 阶段6：七点完成，条件密网格准备被门禁拦下','',
        '## 总结','**P10修复有效；P10、P9c、P11–P14、N0七点均已真实14核串行求解、独立审核并实际看图。** 新增77次Analyze，P10连同旧失败合计13/14。累计189/200几何、1807次请求。',
        '','**本轮尚未全部完成。** N0变化0.077535dB触发P1/P2密网格。我的R3准备器沿用了旧P1/P2 CAD记录，但新门禁要求额外的board_policy元数据，兼容错误在创建输入和启动HFSS之前被拦截，0新增几何/0Analyze。不是新的HFSS几何相交，也不是数值不收敛；责任在本轮接续代码未覆盖该继承分支。',
        '按停止规则保留当前冻结，不绕过门禁、不自动建R4。R10-2、C1、6B、6C未执行；以下余量算术不冒充已发布冻结或制造认证。',
        '','## 1. R3冻结、板框与真实边界','七点全检冻结93a493c，原生验证日志完整发布32ffd42，均先于首点派发。板框±15/±25mm两侧固定，空气域不变；P9c替代原P9进入蚀刻余量。原P1–P9和R1/R2记录保持不变。',
        '未发布草稿把边界清单误设为只有两个Wave Port，已0费用封存。最终R3从原生GetBoundaries、保存AEDT和对象ID映射确认：**Rad1 Radiation分配给air_box**，不是默认PEC外壁；原有边界从未更改。七点预检及各点worker的ValidateDesign均返回1，只有材料因果性建议warning，无error。',
        '','## 2. 全部普通网格公差观测','B1 T2基准：中央谷6.73GHz、低/高峰−20.795778/−20.686649dB、BW20=6.454922GHz。表中BW20只指连续包含三谷与两内峰的完整主窗；P13无完整−20dB主窗，不填0、不拿子窗口冒充。',
        '','|点|中央谷GHz|低内峰dB|高内峰dB|BW20 GHz|主窗最差S21 dB|最高内峰变化dB|网格|','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        m=r['measurement'];lines.append('|'+r['point']+'|'+ '|'.join([f(m['center_GHz'],2),f(m['low_peak_dB']),f(m['high_peak_dB']),f(m['BW20_GHz']),f(m['S21_min_dB']),f(r['highest_peak_rise_dB']),str(r['mesh'])])+'|')
    lines+=['','P13的BW15主窗最差S21为'+f(next(r for r in rows if r['point']=='P13')['S21_min_in_BW15_dB'])+'dB；S11失败不等于求解失败。公差CONTROL的complete/passed表示观测闭合，不是交付达标。全部16个旧/新公差点CSV独立重放，中央谷/两峰/BW20最大绝对差'+str(maxdiff)+'。',
        '','## 3. 灵敏度、线性与当前含义','按两侧中最高内峰的最大正升幅排序：']
    for name,v in sorted(sides.items(),key=lambda kv:kv[1]['rise_dB'],reverse=True):lines.append(f"- {name}: {v['rise_dB']:.6f} dB（{v['worst_point']}）。")
    lines+=['','**厚度是现实三来源中最敏感的。** h从0.813降到0.775mm，中央谷降90MHz，高频内峰升到−18.957dB，失去完整−20dB主窗；厚度增加的一侧中央谷升90MHz。不能据普通ΔS很小就忽略材料/几何公差。',
        'εr变3.50/3.60时中央谷分别+30/−40MHz，最高峰最差升0.129730dB；主要表现为移频。蚀刻最坏为P9c，最高峰升0.353294dB，小于单改Ws的0.502913dB，Q12不获支持。Ws仍是这四种±0.02mm尺寸扰动中最强的S11/BW杠杆。',
        '逐响应正负侧线性检查见REVIEW.json/ordinary_linearity。最高峰在两峰切换处会有拐点，不把它简单解释为单个峰的物理非线性；后续余量使用两侧直测，不用J叠加。J比较沿用原R10-1冻结预测，不用这批结果回改预测。',
        '','## 4. P9 / P9c 与N0','P9c−P9：低峰'+f(comparison['low_peak_dB'])+'dB，高峰'+f(comparison['high_peak_dB'])+'dB，中央谷'+f(comparison['center_GHz']*1000,2)+'MHz，BW20 '+f(comparison['BW20_GHz']*1000,3)+'MHz。Q19两内峰绝对差≤.05dB通过。但这包括板框差异和重新剖分，且N0>.05dB，不能单独分离为侧壁效应。',
        'N0最高峰绝对变化='+f(noise)+'dB：必须补P1/P2密网格；未超过.1dB，因此按原式暂不线性加到M。不能为了接续而放宽.05dB门槛。',
        '','## 5. 未释放的余量算术（不是R10-2）',f'仅按普通网格三项实测，RSS/M约{provisional_M:.6f}dB，P_req约{req:.6f}dB；现实最坏侧为P9c、P11、P13。保守独立线性相加为{provisional["conservative_linear_margin_dB"]:.6f}dB，仅作报告，不作设计目标。',
        '该算术已比−21.8dB更深；若密网格复核后规则不变，按R10应报告“单靠加深纹波不划算”并跳过B1R，不能花未用槽强行调过。当前条件密网格未完成，**没有冻结/推送R10-2，也没有派发C1或B1R**。不能宣称推荐了稳健加工设计。',
        '','## 6. 预测评分',
        '- Q11：编码审计通过；保留冻结代码浮点端点原始False。Ws高峰半差0.560542dB；Lm半差数学值35MHz，IEEE值34.9999999999997。频率网格10MHz，预测区间未改。',
        '- Q12：不通过（蚀刻升幅小于Ws）。Q13通过，Q14通过。',
        '- Q15、Q16：未做6B/6C，不可评分。',
        f'- Q17：通过；P10最高峰变化{p10rise:.6f}dB、BW20变化{p10bw:.3f}MHz。',
        '- Q18：通过，过蚀刻较差。Q19：通过，两峰差均≤.05dB。',
        '- Q20：尚不能正式评分；普通网格算术P_req已落在登记区间之外，也提示可能应跳过B1R而非调它。不能把算术提示说成完成6B后的评分。',
        '','## 7. 预算与停止状态','|本轮点|新Analyze|','|---|---:|']
    for c,n in costs.items():lines.append(f'|{c}|{n}|')
    lines+=['','本R3共77次；P10旧1次仍在此前1730中，不再加到77，也不重收几何。阶段6合计16/27几何、174次请求；全项目189/200、1807次。剩余11几何仅限原条件项/角点/稳健/平台，不转作新授权。',
        '全部七点普通网格100977–104032单元、ΔS最大0.0018023，实际14核1组证据、合法扫频角色、网格历史不变和清理均通过。当前没有HFSS/hf3d或本批worker。无hook、无定时任务；不关闭其他任务、不清锁。',
        '','## 8. 接续要求','见RECOVERY_REQUIREMENTS.md。先审核本次纯元数据兼容错误及有限工具修订方案；不得修改当前冻结或删除STOP。P10、七个已完成点及原P1–P9均不复算。完成条件P1/P2密网格后才能发布R10-2，再C1→6B条件→6C；W4最多2次，阶段7未授权。']
    (HERE/'STOP_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (HERE/'RECOVERY_REQUIREMENTS.md').write_text('''# R11停止后的有限接续要求（当前不执行）

## 根因与责任
R3的P1dense/P2dense继承旧P1/P2的CAD IR，缺少新board_policy及边距离证明元数据。prepare_r10.spec的decorate保留了这个旧IR，新check_ir在创建输入前拒绝它。不是新HFSS错误；是执行者未覆盖继承分支的兼容缺陷。

实际冻结对象测试已证实：从旧IR的base_geometry/e=0重新生成R11规范IR后，六尺寸、槽布尔盒、全部预期原生包络都完全相同，新离线门禁通过。该演示只在内存完成，没有写新输入、启动HFSS或替代真实密网格结果。

## 修复应怎样做
- 不能修改当前已推送的代码/授权/输入或删除STOP来直接重跑。审核后以版本化有限工具修订冻结兼容适配。
- 在新数据边界统一重建R11规范IR，既覆盖P1dense/P2dense，也离线测试未来C1、C1R、B1Rdense、W3/W4各分支；不可只补字段掩盖物理差异。
- 回归须从本次真实继承配置调用spec/make_input路径，不只测试新生成的干净IR。断言规范化前后物理包络、槽布尔盒和参数等价；保留旧P10失败拦截、正负蚀刻板框及数值预算门禁。
- 两个密网格点及后续C1在第一次Analyze之前，分别做零Analyze HFSS原生设计验证并推送输入/代码/证据。任何error停止，不改几何绕过。

## 必须保留的成本与范围
- 当前累计189/200几何、1807次Analyze；阶段6为16/27、174次，本R3为6新增几何、77次。
- P10已关闭，原1+新12=13次，不再重开；P1–P9与本轮七点全保留且不复算。
- 剩余11几何的上界分配：条件密网格2、C1=1、6B最多5、6C=3（W3 T4一次，W4最多2次）；不转新点。
- 普通每几何含数值重试≤14次，密网格≤20次，14核1组串行，ΔS/网格原标准不变，不发hook，不加直接频点。
- N0为0.0775352703dB，密网格条件必须执行，不能放宽阈值。完成后才R10-2，按普通网格直测规则计算M并核对跳过B1R条件。
- 保留R1/R2及R3草稿/最终版本所有STOP、claim、锁、账本、工程与缓存。当前停止，不自动建立R4。

本文件只是接续方案，不是新授权；等待人类/审核方明确接续。
''',encoding='utf-8')
    write(out/'MANIFEST.json',{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()})
    print(dict(raw_cases=len(replay),max_difference=maxdiff,provisional_margin=provisional,costs=costs,current_native_processes=process))

if __name__=='__main__':build()
