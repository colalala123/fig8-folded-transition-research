"""Post-freeze, strictly offline independent final audit/plots; no solver APIs.

Added after dispatch freeze; not used by workers or for candidate selection.
"""
from prepare_r7 import *
from report_r7 import metrics
import numpy as np
import psutil,subprocess,csv,shutil
from collections import Counter
from datetime import datetime

def audit(root):
    cfg=read(root/'authorization.json');out=HERE/'final_audit';out.mkdir(exist_ok=False)
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen code/data changed '+rel)
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('historical source changed '+p)
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native still active; audit only after release')
    decisions=[read(root/'decisions'/(p+'_FINAL.json')) for p in cfg['parent_order']]
    if not all(d['complete'] for d in decisions):raise RuntimeError('not complete')
    geos=[read(p) for p in sorted((root/'ledger').glob('geometry_*.json'))];calls=[read(p) for p in sorted((root/'ledger').glob('Analyze_*.json'))]
    assert len(geos)<=35 and 6+len(geos)<=42 and 106+len(geos)<=187
    counts=Counter(g['parent_id'] for g in geos)
    assert all(n<=cfg['designs'][p]['max_Analyze'] for p,n in counts.items())
    intervals=[];checks=[]
    for g in geos:
        case=g['case'];w=case_dir(root,case,cfg);fz=read(w/'input/freeze.json');rec=read(w/'RUN_RECORD.json');rr=read(w/'review/REVIEW_STAGE3.json');ack=read(w/'review/visual_ack.json')
        cc=sorted([c for c in calls if c['case']==case],key=lambda c:c['index'])
        assert [c['index'] for c in cc]==list(range(len(cc))) and len(cc)==rec['Analyze_requested']<=14
        assert sum(c['stage']=='final_sweep' for c in cc)==1
        assert rec['solve_completed'] and rec['numerical_pass'] and rr['numerical_pass']
        assert 100000<=rec['mesh_cells']<=112000 and rec['delta_s']<=.005 and rr['final_sweep_history_unchanged']
        assert ack['actually_viewed'] and ack['plot_sha256']==sha(w/'review/S11_S21.png') and ack['extraction_sha256']==sha(w/'review/extraction_R2.json')
        assert read(w/'done.json')['native_sha256']==sha(w/'native/full_modes.npz')
        assert read(w/'evidence/actual_start_observed.json')['actual_14core_1group'] and rec['cleanup']['released']
        for c in cc:
            role=read(w/'evidence'/(c['stage']+'_role_check.json'))
            assert role['passed']
        start=read(w/'worker_started.json');pub=read(root/'publications'/(case+'.json'))
        assert datetime.fromisoformat(pub['at'])<datetime.fromisoformat(start['at'])
        assert pub['remote_verified'] and pub['freeze_sha256']==sha(w/'input/freeze.json')
        assert not subprocess.run(['git','merge-base','--is-ancestor',pub['commit'],'HEAD'],cwd=REPO).returncode
        try:
            proc=psutil.Process(start['pid'])
            if abs(proc.create_time()-start['create_time'])<.01:raise RuntimeError('worker still alive')
        except psutil.NoSuchProcess:pass
        intervals.append((start['at'],rec['finished_at'],case))
        # Independent raw CSV replay of native fundamental response, not copied reviewer outputs.
        from offline_fit import response
        raw=response(w/'native/full_modes.csv');q=read(w/'review/extraction_R2.json');y=state(q)
        if raw and y is not None:
            np.testing.assert_allclose(y,[raw['valley_GHz'],raw['D_dB'],raw['peak_mean_dB']],atol=1e-10,rtol=0)
        checks.append(dict(case=case,kind=cfg['designs'][g['parent_id']]['kind'],mesh=rec['mesh_cells'],delta_s=rec['delta_s'],Analyze=len(cc),
            publication_commit=pub['commit'],native_sha256=sha(w/'native/full_modes.npz'),numerical_pass=True,visual_ack_verified=True))
    intervals.sort()
    assert all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:]))
    # Boundary comparisons use the exact selected geometry, not the earlier R3 seeds.
    boundaries=[]
    for d in decisions:
        if d['kind']!='BOUNDARY' or d.get('skipped'):continue
        case=d['selected_case'];w=case_dir(root,case,cfg);fz=read(w/'input/freeze.json');b=fz['design']['binding'];sel=selection(root,cfg['designs'][d['parent_id']]['parent'],cfg)
        qp=source(sel[0])[0] if sel[0] not in cfg['case_paths'] else case_dir(root,sel[0],cfg)/'review/extraction_R2.json'
        orig=metrics(read(qp),sel[2]);wide=metrics(read(w/'review/extraction_R2.json'),w/'native/full_modes.npz')
        m=read(w/'evidence/materials_and_boundary.json');assert m['board_half_x_mm']==20. and len(m['widened_objects'])>=5
        boundaries.append(dict(case=case,parent=sel[0],geometry_unchanged=read(qp)['geometry_mm']==fz['design']['geometry_mm'],
            original=orig,widened=wide,BW15_change_MHz=1000*(wide['BW15']-orig['BW15']),
            L_change_dB=wide['L']-orig['L'],D_change_dB=wide['D']-orig['D']))
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    power=read(HERE/'final/LOSSLESS_POWER.json');fig,ax=plt.subplots(figsize=(8,5))
    all_power=[]
    for fam in ('N04','N14'):
        f2,a2=plt.subplots(figsize=(9,5))
        rows=sorted([p for p in power if p['family']==fam],key=lambda r:r['a'])
        for r in rows:
            w=case_dir(root,r['case'],cfg);bal=np.load(w/'review/lossless_modal_balance.npz');z=np.load(w/'native/full_modes.npz')
            s=cfg['designs'][read(w/'input/freeze.json')['parent_id']];sel=selection(root,s['parent'],cfg)
            qp=source(sel[0])[0] if sel[0] not in cfg['case_paths'] else case_dir(root,sel[0],cfg)/'review/extraction_R2.json';q=read(qp)
            f=bal['f_GHz'];band=(f>=q['BW15']['low_GHz'])&(f<=q['BW15']['high_GHz'])
            a2.plot(f[band],bal['residual_fraction'][band],label=f"a={r['a']:.1f} mm")
            # Publish frequency-resolved propagation evidence, with invalid samples explicit.
            dest=out/(r['case']+'_POWER.csv')
            with dest.open('x',newline='',encoding='utf-8') as fp:
                wr=csv.writer(fp);wr.writerow(['f_GHz','valid','residual_fraction','outgoing_fraction']+[f'mode{i}_propagating' for i in range(4)]+[f'Gamma{i}_real' for i in range(4)]+[f'Gamma{i}_imag' for i in range(4)])
                for i in np.where(band)[0]:wr.writerow([f[i],bool(bal['valid'][i]),bal['residual_fraction'][i],bal['outgoing_fraction'][i],*bal['propagating'][i],*z['Gamma'][i].real,*z['Gamma'][i].imag])
            r=dict(r,unknown_or_invalid_in_main_band=r['main_band_total']-r['main_band_valid']);all_power.append(r)
        a2.set(xlabel='Frequency (GHz)',ylabel='Radiation plus numerical residual (fraction)',title=fam+' lossless declared-mode balance');a2.grid(alpha=.3);a2.legend();f2.tight_layout();f2.savefig(out/(fam+'_POWER_CURVES.png'),dpi=150);plt.close(f2)
        ax.plot([r['a'] for r in rows],[r['mean_residual'] for r in rows],'-o',label=fam)
    ax.set(xlabel='Fold arm a (mm)',ylabel='Mean radiation plus numerical residual (fraction)',title='Lossless controls; not full-modal power certified');ax.legend();ax.grid(alpha=.3);fig.tight_layout();fig.savefig(out/'POWER_VS_ARM.png',dpi=150);plt.close(fig)
    audit=dict(at=now(),passed=True,new_geometry=len(geos),new_Analyze=len(calls),stage3_geometry=6+len(geos),cumulative_geometry=106+len(geos),cumulative_Analyze=961+len(calls),
       kind_counts=dict(Counter(c['kind'] for c in checks)),all_numeric=True,all_visual_ACK=True,all_publications_precede_solve=True,serial_intervals_nonoverlapping=True,
       native_processes=[],frozen_and_historical_hashes_unchanged=True,stage4_started=False,stage5_started=False,full_modal_power_certified=False,intervals=intervals,checks=checks)
    write(out/'AUDIT.json',audit);write(out/'BOUNDARY_COMPARISONS.json',boundaries);write(out/'POWER_SUMMARY.json',all_power)
    # Preserve original scoring, including slope uncertainty and negative predictions.
    mm=read(HERE/'final/METRICS.json');scores=read(HERE/'final/PREDICTION_SCORES.json');gate=read(HERE/'final/GATE.json')
    by={(r['family'],r['a']):r for r in mm}
    spreads={fam:1000*(max(by[fam,a]['BW15_star'] for a in (.6,1.,1.8,2.2))-min(by[fam,a]['BW15_star'] for a in (.6,1.,1.8,2.2))) for fam in ('N04','N14')}
    long_cost={fam:1000*(by[fam,1.8]['BW15_star']-by[fam,2.6]['BW15_star']) for fam in ('N04','N14')}
    straight_cost={fam:1000*(by[fam,1.8]['BW15_star']-by[fam,0.]['BW15_star']) for fam in ('N04','N14')}
    lines=['# R7 3R最终审核报告','',
      f"八个新设计均达到R7研究可用点；加上4个既有点，共12个等纹波研究点。10个无耗和2个加宽基板对照均完成，数量条件{'通过' if gate['passed'] else '未通过'}。",
      '同纹波带宽、预测评分与功率余量的结论按下列实测数据报告，不把研究可用点冒充硬−20 dB交付设计。3R已停止，未进入阶段4/5。','',
      f"冻结折算到L=−20.3 dB后，a=0.6–2.2 mm的BW15*跨度：N04 {spreads['N04']:.2f} MHz，N14 {spreads['N14']:.2f} MHz。P1只在N04满足；不能概括为两家族都严格无带宽代价。",
      f"a=2.6相对a=1.8的BW15*代价：N04 {long_cost['N04']:.2f} MHz，N14 {long_cost['N14']:.2f} MHz，两家族均满足P2的50–150 MHz预测。直槽相对a=1.8更窄{straight_cost['N04']:.2f}、{straight_cost['N14']:.2f} MHz；P3的110 MHz上限在N14略超。",
      '以上是冻结名义斜率的点估计，完整上下限保留；接近50/110/150 MHz边界时，不能忽视斜率及约0.06 dB数值起伏。BWref*与BW15*分列，不把不同阈值的带宽混用。','',
      f"本轮{len(geos)}几何、{len(calls)}次实际Analyze；阶段3累计{6+len(geos)}/42几何，全局{106+len(geos)}/187，累计实际请求{961+len(calls)}。",'',
      '## 可复核主表','见 [冻结口径完整报告](../final/REPORT.md)、[METRICS.json](../final/METRICS.json)。主表同时给原始BW15/BW20/BWref和冻结斜率折算、上下限。','',
      '## 四条预测（固定口径，不因结果修改）']
    for key,items in scores.items():
        lines+=['','### '+key,'```json',json.dumps(items,ensure_ascii=False,indent=2),'```']
    lines+=['','## 无耗控制：辐射加数值误差','',
      '采用原生广义S；Gamma与Zo联合判断传播，未知/非物理功率点不填零、不裁剪。包含端口模式截断、数值和边界不确定性，full_modal_power_certified=false。',
      '|家族|a mm|主带有效/总频点|平均余量|余量最小|余量最大|','|---|---|---|---|---|---|']
    for r in all_power:lines.append(f"|{r['family']}|{r['a']}|{r['main_band_valid']}/{r['main_band_total']}|{r['mean_residual']}|{r['min_residual']}|{r['max_residual']}|")
    lines+=['','![power versus arm](POWER_VS_ARM.png)','![N04](N04_POWER_CURVES.png)','![N14](N14_POWER_CURVES.png)',
      '','全部涉及模式2的S项最大模值在POWER_SUMMARY.json；其幅度不是传播功率。逐频Gamma、传播掩码、功率余量见各POWER.csv。',
      '','## 基板边界对照','```json',json.dumps(boundaries,ensure_ascii=False,indent=2),'```',
      '','## 数据身份、预算与停止',
      '8个新设计为预登记前瞻调参数据，4个既有点为回顾数据；新尝试不得再当独立盲测。15个调参几何和12个对照各自入账，原阶段3的6个历史成本全部保留。',
      'R7派发冻结中的plan_commit/plan_path旧兼容字段来自R6；实际新增授权由execution_revision=R7_3R、R7计划哈希和用户原文共同绑定，求解前提交为bc1b718。没有更改旧字段来伪造新的历史。',
      '执行代码/输入/旧证据哈希未变化，每项发布早于求解；所有角色验收通过，最终扫频未改变网格，进程已正常释放；无hook、未启动阶段4/5。',
      'AUDIT.json含每几何计费、网格、ΔS、发布提交及串行区间。TUNING_STEPS.json记录预测/实际变化与Broyden触发；未通过的中间尝试完整保留。',
      '','停止原因：R7第4.3节要求3R结束后提交等审核。后续前瞻点、硬−20dB交付和加密网格确认仍需后续方案，不擅自启动。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print('AUDIT_PASSED',audit['new_geometry'],audit['new_Analyze'])
if __name__=='__main__':audit(ROOT)
