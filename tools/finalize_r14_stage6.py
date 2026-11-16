"""Offline R14 closeout audit and normal STOP. No AEDT API or solver dispatch."""
import collections,datetime,hashlib,json,os,sys
from pathlib import Path
import psutil
REPO=Path(__file__).resolve().parents[1]
H=REPO/'experiments/fold_bandwidth_r14_stage6_r6_20261116'
sys.path.insert(0,str(H))
from common_stage2 import read,sha,case_dir
from prepare_r10 import ROOT
import manage,r13

def save(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
def main():
    out=H/'final'; assert not (out/'CLOSURE.json').exists(),'Already closed; do not repeat'
    cfg=read(ROOT/'authorization.json'); res=read(out/'RESULTS.json')
    assert read(out/'POST_TESTS.json')['passed'] and read(out/'ENTRY_TESTS_POST_RUN.json')['passed']
    assert type(res['predictions']['Q16']['passed']) is bool
    frozen={**cfg['code_hashes'],**cfg['frozen_hashes'],**cfg['plan_hashes']}
    for rel,digest in frozen.items():assert sha(REPO/rel)==digest,rel
    for path,digest in cfg['historical_hashes'].items():assert sha(path)==digest,path
    r13.audit_cache_files(r13.SOURCE,cfg)
    native=[];workers=[]
    for p in psutil.process_iter(['name','cmdline','create_time']):
        name=(p.info['name'] or '').lower();cmd=' '.join(p.info['cmdline'] or []).replace('\\','/').lower()
        if name in ('ansysedt.exe','hf3d.exe'):native.append(dict(pid=p.pid,name=name,create_time=p.info['create_time']))
        if p.pid!=os.getpid() and name in ('python.exe','pythonw.exe') and any(x in cmd for x in ('worker_stage2.py','observer_r13.py','controller_stage2.py')) and (str(ROOT).replace('\\','/').lower() in cmd or H.name.lower() in cmd):workers.append(dict(pid=p.pid,name=name,create_time=p.info['create_time']))
    assert not native and not workers,(native,workers)
    ledger=[read(p) for p in (ROOT/'ledger').glob('Analyze_*.json')]
    counts=dict(collections.Counter(x['case'] for x in ledger))
    expected={'S6R10_B1Rdense__T1':1,'S6R10_C1R__T1':11,'S6R10_W3__T4':12,'S6R10_W4__T1':10}
    assert counts==expected,counts
    assert all(x['cores']==14 and x['tasks']==1 for x in ledger)
    assert len(list((ROOT/'ledger').glob('geometry_*.json')))==3
    assert not case_dir(ROOT,'S6R10_W4__T2',cfg).exists(),'Unused W4 T2 must not be prepared'
    cases=[]; identities=[]
    for case in expected:
        w=case_dir(ROOT,case,cfg);pub=H/'results'/case
        for rel,digest in read(pub/'MANIFEST.json').items():assert sha(pub/rel)==digest,(case,rel)
        summary=read(pub/'SUMMARY.json');rec=summary['record'];ack=read(w/'review/visual_ack.json')
        assert rec['solve_completed'] and rec['numerical_pass'] and rec['new_Analyze_requested']==expected[case]
        assert summary['cleanup']['released'] and summary['cleanup']['scratch_restored']
        assert ack['actually_viewed'] and ack['plot_sha256']==sha(w/'review/S11_S21.png') and ack['extraction_sha256']==sha(w/'review/extraction_R2.json')
        assert read(w/'review/REVIEW_STAGE3.json')['numerical_pass']
        for p in (w/'evidence').glob('*_role_check.json'):assert read(p)['passed'],str(p)
        for p in [w/'owner.json',w/'worker_started.json',*list((w/'evidence').glob('*.ready'))]:
            if not p.exists():continue
            d=read(p);pid=d.get('pid');ct=d.get('create_time')
            if pid is None or ct is None:continue
            same=psutil.pid_exists(pid) and abs(psutil.Process(pid).create_time()-ct)<.01
            assert not same,('Historical process still alive',p,pid)
            identities.append(dict(case=case,source=p.name,pid=pid,create_time=ct,same_identity_alive=False))
        cases.append(dict(case=case,record=rec,cleanup=summary['cleanup'],roles=summary['roles'],public_manifest_verified=True,actual_view_ack_verified=True))
    # The user asked to stop at the end. This is normal closure, not a technical failure or a user pause.
    at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    closure=dict(at=at,normal_completion=True,technical_failure=False,user_paused=False,
        reason='R14 finite authorized sequence completed and reviewed; no further dispatch authorized',
        new_geometries=3,new_Analyze=34,cumulative_geometries=196,cumulative_Analyze=1880,
        stage6_geometries=23,stage6_Analyze=247,per_case_new_Analyze=counts,
        unused_W4_T2_not_prepared=True,unused_allowance_is_not_new_authorization=True,
        runtime_self_fixes=[],stage7_authorized=False,next_action='Await human review; do not resume automatically')
    save(ROOT/'STOP.json',closure);save(ROOT/'COMPLETED.json',closure);save(out/'CLOSURE.json',closure)
    status=manage.status(ROOT);assert status['stop']['normal_completion']
    save(out/'FINAL_AUDIT.json',dict(at=at,passed=True,cases=cases,process_identity_checks=identities,
        native_processes=native,owned_workers=workers,source_cache_file_count=597,
        frozen_hashes_verified=len(frozen),historical_hashes_verified=len(cfg['historical_hashes']),
        public_case_manifests_verified=4,ledger_count=len(ledger),closure_sha256=sha(out/'CLOSURE.json'),
        RESULTS_Q16_is_boolean=True,report_builder_sha256=sha(REPO/'tools/report_r14_stage6.py'),
        finalizer_sha256=sha(Path(__file__))))
    save(out/'VISUAL_QA.json',dict(at=at,file='DELIVERY_CURVES.png',sha256=sha(out/'DELIVERY_CURVES.png'),
        actually_viewed=True,reviewer='Codex',notes='Viewed with view_image: S11/S21 axes and legends readable; C1R high peak visibly crosses -20 dB. Plot is intentionally zoomed to -40..-15 dB, not a full-valley depth measurement.'))
    # Supplement the main report using already frozen predictions and recorded outputs only.
    f=read(H/'freeze/R10_1.json');lines=['# 阶段6逐点离线核对附表','','所有差值为实测减B1；null表示完整主窗不存在，不当作0。','',
        '|点|Δ中央谷 MHz|Δ低峰 dB|Δ高峰 dB|ΔBW20 MHz|Δ最差S21 dB|','|---|---:|---:|---:|---:|---:|']
    def fmt(x,scale=1):return 'null' if x is None else f'{x*scale:.6f}'
    for n,d in res['differences_vs_B1'].items():lines.append('|'+n+'|'+'|'.join(fmt(d[k],s) for k,s in [('center_GHz',1000),('low_peak_dB',1),('high_peak_dB',1),('BW20_GHz',1000),('S21_min_dB',1)])+'|')
    lines+=['','## 正负扰动的非线性判定','','使用冻结阈值逐指标判断；这只是给定扰动幅度内的判定。','','|来源|被判为明显非线性的指标|不可判指标|','|---|---|---|']
    for n,d in res['linearity'].items():lines.append('|'+n+'|'+(', '.join(k for k,v in d.items() if v.get('clearly_nonlinear')) or '无')+'|'+(', '.join(k for k,v in d.items() if not v['assessable']) or '无')+'|')
    lines+=['','## P1–P6 的冻结J与实测','','只对求解前已有J预测的前六点比较；不为其余点事后补预测。','','|点|J中央谷 GHz|实测中央谷 GHz|J低峰 dB|实测低峰 dB|J高峰 dB|实测高峰 dB|','|---|---:|---:|---:|---:|---:|---:|']
    jcheck=[]
    for d in f['stage6A'][:6]:
        n=d['design'];p=d['prediction'];m=res['stage6A'][n]
        lines.append('|'+n+'|'+'|'.join(fmt(x) for x in [p['central_valley_GHz'],m['center_GHz'],p['low_peak_dB'],m['low_peak_dB'],p['high_peak_dB'],m['high_peak_dB']])+'|')
        jcheck.append(dict(point=n,frozen_prediction=p,actual=m))
    lines+=['','Q11量级核查：Ws高峰中心差分每±0.02mm为0.560542dB，J为0.655653dB；Lm移频每±0.02mm为35MHz，J为45.785MHz。35MHz是区间端点，二进制浮点表示为34.9999999999997MHz，按测频分辨率解释，不偷偷扩大其他阈值。',
        'Ws、Lm量级大体对，但Ls1的高峰等指标有非线性；后续余量采用两侧直测，不用J替代。',
        '', '## W4首次候选的前瞻误差','', '|指标|实测−冻结预测|','|---|---:|']
    w=next(t for t in res['platform_trials_and_frozen_predictions'] if t['case']=='S6R10_W4__T1')
    delta=[a-b for a,b in zip(w['measured_y'],w['predicted_y'])]
    lines +=[f'|中央谷|{delta[0]*1000:.6f} MHz|',f'|两内峰差D|{delta[1]:.6f} dB|',f'|两内峰均值|{delta[2]:.6f} dB|',f"|BW15*相对主要线性预测|{w['BW15_star_primary_residual_MHz']:.6f} MHz|",f"|BW15*相对预登记二次备选|{w['BW15_star_alternative_residual_MHz']:.6f} MHz|",'', '两种带宽预测均为事前冻结备选，不事后只挑误差较小的模型作为主模型。W4满足名义条件不是全响应代理模型已获普适验证。']
    (out/'DETAILS_6A_J_AND_W4.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(out/'J_COMPARISON.json',jcheck)
    report=out/'REPORT.md';text=report.read_text(encoding='utf-8')
    text=text.replace('三步流程（6C按可用性门槛执行/跳过）','三步流程（6C门槛通过，已完成W3 T4和W4 T1）')
    text=text.replace('各点相对B1的完整差分及逐指标非线性判定见RESULTS.json。','各点相对B1的完整差分、逐指标非线性判定和冻结J对照见[逐点附表](DETAILS_6A_J_AND_W4.md)，机器可读值见RESULTS.json。')
    text=text.replace('## 3. 6A公差直测回顾','![B1、B1R与联合角点原生S参数](DELIVERY_CURVES.png)\n\n## 3. 6A公差直测回顾')
    text += '\n## 7. 最终复核与文档修订披露\n\n收尾再次通过R5 55项、R6 55项、默认11项、8765文件校验，以及20次全新解释器导入和2次实际观察器空跑。最终4套结果清单、597文件原R4缓存及冻结/历史哈希复核一致。详见POST_TESTS.json和FINAL_AUDIT.json。\n\n报告生成阶段修过两个离线展示问题：W3预测为列表而W4为对象，现保留原预测并统一显示；NumPy布尔值现转为标准JSON布尔值。未发布错误中间稿DRAFT_RESULTS_SERIALIZATION_ISSUE.json仅保留审计，**正式科学结果只认RESULTS.json**。这两项没有改运行代码或冻结输入，没有新增Analyze，不是R14运行中技术重试。\n\nW4首次候选相对冻结预测：中央谷+19.397MHz、两内峰差−0.168986dB、均值−0.088825dB；BW15*相对主要线性预测−47.278MHz、相对预登记二次备选−23.208MHz。详见逐点附表。\n\n已写入正常完成STOP和COMPLETED标记，禁止继续派发。STOP不是技术故障，也不是用户暂停；闭账详情见CLOSURE.json。剩余额度不自动使用。RESULTS.json中的预算为生成报告时快照，最终停止状态以CURRENT_STATUS.json和CLOSURE.json为准。\n'
    report.write_text(text,encoding='utf-8')
    readme=H/'README.md';text=readme.read_text(encoding='utf-8')
    text += '\n## 最终交付（已完成并正常停止）\n\n- [中文收尾报告](final/REPORT.md)\n- [逐点公差、J对照与W4前瞻误差](final/DETAILS_6A_J_AND_W4.md)\n- [正式机器可读结果](final/RESULTS.json)\n- [正常闭账](final/CLOSURE.json)与[最终审计](final/FINAL_AUDIT.json)\n\n新增3几何/34 Analyze，累计196/200几何、1880 Analyze。W4首次通过，未创建T2；C1R为有效负例。运行入口现受正常完成STOP阻断，不得自动恢复。\n'
    readme.write_text(text,encoding='utf-8')
    with (H/'CURRENT_STATUS.md').open('a',encoding='utf-8') as f:f.write('\n正常完成闭账（不是技术故障或用户暂停）；W4 T2未启用。见 final/REPORT.md。\n')
    print(json.dumps(dict(closed=True,new_Analyze=34,geometries=196,total_Analyze=1880),ensure_ascii=False))
if __name__=='__main__':main()
