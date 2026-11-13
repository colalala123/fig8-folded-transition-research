"""Post-freeze offline report/audit, never imported by worker or tuner.

No coefficients changed; all prospective scores replay the prepublished inputs.
"""
from prepare_r8 import *
import numpy as np,subprocess,psutil,csv
from datetime import datetime
from collections import Counter
import laws
def fmt(v,n=4):return '—' if v is None else f'{v:.{n}f}'
def metrics(root,case,cfg):
    w=case_dir(root,case,cfg);q=read(w/'review/extraction_R2.json');y=state(q);bw=q['bandwidths']
    fz=read(w/'input/freeze.json');g=fz['design']['geometry_mm'];z=np.load(w/'native/full_modes.npz')
    b=bw['BW15'];valid=b['BW_GHz'] is not None;edges=None if not valid else [b['low_GHz'],b['high_GHz']]
    # Extraction uses the authoritative R2 names; no redefinition of a main band.
    return dict(case=case,geometry_mm=g,central_GHz=None if y is None else float(y[0]),D=None if y is None else float(y[1]),L=None if y is None else float(y[2]),
        **classify(q),BW15=b['BW_GHz'],BW20=bw['BW20']['BW_GHz'],
        BW15_star=None if not valid or y is None else b['BW_GHz']-.125*(float(y[2])+20.3),
        BW15_star_slope_range=None if not valid or y is None else sorted(b['BW_GHz']-s*(float(y[2])+20.3) for s in (.110,.140)),
        S21_min_in_BW15_dB=None if not valid else float(np.min(20*np.log10(abs(z['S'][(z['f_GHz']>=edges[0])&(z['f_GHz']<=edges[1]),2,0])))),
        tip_clearance_mm=(g['Ls1']-2*g['Ls3']-max(g['Wm'],1.82))/2,data_role=fz['design']['data_role'])
def audit(root,cfg):
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native still running')
    for rel,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('frozen bytes changed '+rel)
    for path,h in cfg['historical_hashes'].items():
        if sha(path)!=h:raise RuntimeError('historical bytes changed '+path)
    geos=[read(p) for p in sorted((root/'ledger').glob('geometry_*.json'))];apis=[read(p) for p in sorted((root/'ledger').glob('Analyze_*.json'))]
    assert len(geos)<=24 and 133+len(geos)<=157 and 133+len(geos)<=187
    assert all(n<=3 for n in Counter(g['parent_id'] for g in geos).values())
    checks=[];intervals=[]
    from extract_run import extract
    for ge in geos:
        c=ge['case'];w=case_dir(root,c,cfg);r=read(w/'RUN_RECORD.json');rev=read(w/'review/REVIEW_STAGE3.json');ack=read(w/'review/visual_ack.json');fz=read(w/'input/freeze.json')
        cc=sorted([a for a in apis if a['case']==c],key=lambda x:x['index'])
        assert [a['index'] for a in cc]==list(range(len(cc))) and len(cc)==r['Analyze_requested']<=14 and sum(a['stage']=='final_sweep' for a in cc)==1
        assert r['solve_completed'] and r['numerical_pass'] and rev['numerical_pass'] and r['cleanup']['released']
        assert 100000<=r['mesh_cells']<=112000 and r['delta_s']<=.005 and rev['final_sweep_history_unchanged']
        assert ack['actually_viewed'] and ack['plot_sha256']==sha(w/'review/S11_S21.png') and ack['extraction_sha256']==sha(w/'review/extraction_R2.json')
        assert read(w/'done.json')['native_sha256']==sha(w/'native/full_modes.npz')
        assert read(w/'evidence/actual_start_observed.json')['actual_14core_1group']
        for a in cc:assert read(w/'evidence'/(a['stage']+'_role_check.json'))['passed']
        pub=read(root/'publications'/(c+'.json'));started=read(w/'worker_started.json')
        assert pub['remote_verified'] and datetime.fromisoformat(pub['at'])<datetime.fromisoformat(started['at'])
        assert pub['freeze_sha256']==sha(w/'input/freeze.json')
        assert subprocess.run(['git','merge-base','--is-ancestor',pub['commit'],'HEAD'],cwd=REPO).returncode==0
        try:
            proc=psutil.Process(started['pid'])
            if abs(proc.create_time()-started['create_time'])<.01:raise RuntimeError('worker alive')
        except psutil.NoSuchProcess:pass
        intervals.append((started['at'],r['finished_at'],c))
        # Independent native CSV extraction, not merely comparing two JSONs.
        with (w/'native/full_modes.csv').open(encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f);heads=next(reader);ar=np.array(list(reader),float)
        ss=[]
        for s in ('S(1:1,1:1)','S(2:1,1:1)'):ss.append(ar[:,heads.index(s+'_real')]+1j*ar[:,heads.index(s+'_imag')])
        qr=extract(ar[:,0],np.array(ss).T,read(w/'native/metadata.json'));qo=read(w/'review/extraction_R2.json')
        if state(qo) is None:assert state(qr) is None
        else:np.testing.assert_allclose(state(qr),state(qo),atol=1e-10,rtol=0)
        assert qr['bandwidths']['BW15']==qo['bandwidths']['BW15']
        checks.append(dict(case=c,numerical_pass=True,mesh=r['mesh_cells'],delta_s=r['delta_s'],Analyze=len(cc),real_image_ack=True,publication=pub['commit']))
    intervals.sort();assert all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:]))
    return dict(at=now(),passed=True,new_geometry=len(geos),new_Analyze=len(apis),total_geometry=133+len(geos),total_Analyze=1226+len(apis),
        code_and_laws_unchanged=True,historical_hashes_unchanged=True,serial_nonoverlap=True,checks=checks,
        passed_scope='technical execution/numerical/provenance audit, not scientific predictions or all data-role assumptions',
        all_eight_unseen_tuple_assumption_pass=False,data_role_issue='D5 seen Wm/a/g tuple included in frozen training; explicitly disclosed, no retrospective refit')
def run(root):
    cfg=read(root/'authorization.json');out=HERE/'final';out.mkdir()
    decisions=[read(root/'decisions'/(p+'_FINAL.json')) for p in cfg['parent_order']]
    aud=audit(root,cfg);selected=[];scores=[];m=read(HERE/'offline/LAWS.json')
    for p,d in zip(cfg['parent_order'],decisions):
        s=cfg['designs'][p];t1=metrics(root,p+'__T1',cfg);sel=metrics(root,d['selected_case'],cfg);selected.append(dict(design=s['design'],family=s['family'],a=s['nominal_a_mm'],g=s['g_mm'],attempts=d['attempts'],**sel))
        yp=s['prediction'];bwerr={k:None if t1['BW15'] is None or t1['L'] is None else 1000*(t1['BW15']-(v+.125*(t1['L']+20.3))) for k,v in yp['BW15_star_GHz'].items()}
        er=dict(valley_GHz=None if t1['central_GHz'] is None else t1['central_GHz']-yp['central_valley_GHz'],D_dB=None if t1['D'] is None else t1['D']-yp['D_dB'],L_dB=None if t1['L'] is None else t1['L']-yp['L_dB'])
        passed={k:v is not None and abs(v)<=lim+1e-10 for k,v,lim in [('valley',er['valley_GHz'],.03),('D',er['D_dB'],.7),('L',er['L_dB'],.3),('BW15_primary',bwerr['F2_tip'],40.)]}
        overlaps=[r['case'] for r in read(HERE/'offline/TRAINING.json')['rows'] if abs(r['Wm']-s['geometry_mm']['Wm'])<1e-7 and abs(r['a']-s['nominal_a_mm'])<1e-6 and abs(r['g']-s['g_mm'])<1e-6]
        scores.append(dict(design=s['design'],T1=t1,frozen_prediction=yp,errors=er,BW15_errors_MHz=bwerr,passed_components=passed,T1_all_pass=all(passed.values()),
            unseen_Wm_a_g_tuple=not overlaps,overlapping_training_cases=overlaps,
            central_error_vs_target_GHz=None if t1['central_GHz'] is None else t1['central_GHz']-6.72,
            scoring='T1 only, six frozen models; BW15 prediction conditioned only on measured L per R8, no refit'))
    by={r['design']:r for r in selected}
    def value(n):return by[n]['BW15_star'] if by[n]['tuned'] else None
    costs={n:None if value(n) is None else 1000*(6.332 if by[n]['family']=='N04' else 6.214)-1000*value(n) for n in ('D1','D2','D3','D4')}
    tip=all(costs[n] is not None and (costs[n]<=30 if n in ('D1','D3') else 30<=costs[n]<=90) for n in costs)
    summ=all(costs[n] is not None and (50<=costs[n]<=110 if n in ('D1','D3') else costs[n]<=45) for n in costs)
    complete=all(v is not None for v in costs.values())
    q1=dict(costs_MHz=costs,scorable=complete,tip_hypothesis_pass=tip if complete else None,sum_hypothesis_pass=summ if complete else None,
       winner=('not_scorable_missing_usable_designs' if not complete else 'tip' if tip and not summ else 'a+g' if summ and not tip else 'neither' if not tip and not summ else 'both; no unique discriminator'))
    qq=dict(Q1=q1)
    for q,n,lo,hi in [('Q2','D7',6.24,6.29),('Q3','D5',6.,6.07),('Q4','D6',6.25,6.30),('Q5','D8',6.34,6.50)]:
        v=value(n);qq[q]=dict(design=n,BW15_star=v,range=[lo,hi],passed=v is not None and lo<=v<=hi)
    qq['Q5']['saturation']=None if value('D8') is None else 'saturated' if value('D8')<6.42 else 'linear' if value('D8')>6.42 else 'boundary'
    errors={k:dict(n=sum(s['BW15_errors_MHz'][k] is not None for s in scores),RMSE_MHz=float(np.sqrt(np.mean([s['BW15_errors_MHz'][k]**2 for s in scores if s['BW15_errors_MHz'][k] is not None])))) for k in scores[0]['BW15_errors_MHz']}
    for n,v in [('AUDIT',aud),('T1_SCORES',scores),('SELECTED',selected),('REVIEWER_SCORES',qq),('BANDWIDTH_MODEL_ERRORS',errors)]:write(out/(n+'.json'),v)
    usable=sum(r['tuned'] for r in selected);t1pass=sum(s['T1_all_pass'] for s in scores)
    unseen=[s for s in scores if s['unseen_Wm_a_g_tuple']]
    lines=['# R8 阶段4完成报告','', '## 总结','',f'8个指定设计均完成有限流程；{usable}/8取得R7可用点，T1四项联合预测通过{t1pass}/8。新增{aud["new_geometry"]}几何、{aud["new_Analyze"]}实际Analyze；累计{aud["total_geometry"]}/187几何、{aud["total_Analyze"]}实际Analyze。阶段4完成后停止，不进入阶段5。',
      '',f'其中只有{len(unseen)}/8是未见(Wm,a,g)组合；这些组合的T1联合通过{sum(s["T1_all_pass"] for s in unseen)}/{len(unseen)}。D5历史组合曾进入训练，须单列；见DATA_ROLE_DISCLOSURE.md。不能宣称8项全是独立未见组合。',
      '',f'Q1按预登记区间判为：{q1["winner"]}。D8的平台判断为：{qq["Q5"]["saturation"]}。此结论仅覆盖本次设计与数值口径，不是普适的P/R逆向设计定律。',
      '', '## 各T1预测与实测','', '|设计|谷预测/实测 GHz|D预测/实测 dB|L预测/实测 dB|BW15预测/实测 GHz|四项全过|', '|---|---|---|---|---|---|']
    for s in scores:
        yp=s['frozen_prediction'];t=s['T1'];bp=None if t['L'] is None else yp['BW15_star_GHz']['F2_tip']+.125*(t['L']+20.3)
        lines.append(f"|{s['design']}|{fmt(yp['central_valley_GHz'])}/{fmt(t['central_GHz'])}|{fmt(yp['D_dB'],3)}/{fmt(t['D'],3)}|{fmt(yp['L_dB'],3)}/{fmt(t['L'],3)}|{fmt(bp)}/{fmt(t['BW15'])}|{s['T1_all_pass']}|")
    lines+=['','BW15预测按R8条件化实测L；完整六模型逐点误差与四项门槛见T1_SCORES.json。T1即使失败仍永久保留前瞻身份，T2/T3绝不替代它计入盲测。','','## 三种代价及平台模型误差','','|模型|T1 n|RMSE MHz|','|---|---:|---:|']
    for k,v in errors.items():lines.append(f'|{k}|{v["n"]}|{v["RMSE_MHz"]:.3f}|')
    lines+=['','## Q1–Q5及平台结论','','```json',json.dumps(qq,ensure_ascii=False,indent=2),'```','',
       'Q1严格用原登记N04=6.332/N14=6.214平台及区间；缺少任一可用点时不可判分，不把缺失误写为两个假说都失败。若全部可评分但判neither，不把最接近的一组改称成立。D1/D3实际端头净距与计划粗估不一致，削弱区分度；不能拿本批结果再改冻结阈值。',
       '', '## 可用点表','', '|设计|Wm|a|g|选中案例|Ws|谷 GHz|D dB|L dB|BW15* GHz|可用|严格双峰≤-20|','|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|']
    for r in selected:
        lines.append(f"|{r['design']}|{r['geometry_mm']['Wm']}|{r['a']}|{r['g']}|{r['case']}|{r['geometry_mm']['Ws']}|{fmt(r['central_GHz'])}|{fmt(r['D'],3)}|{fmt(r['L'],3)}|{fmt(r['BW15_star'])}|{r['tuned']}|{r['hard_design_peaks_pass']}|")
    lines+=['','## 限制与接续','','- R7研究可用与硬-20dB交付分开；BW20缺失时保留null，不用BW15*伪造。','- 原生插值/约10万网格，不是直接频点、加密网格或制造公差认证；本批没有全模功率/辐射分解的新认证。','- 80历史点拟合与整阶梯CV均在R8-1先推送；本批不改规律系数。','- 独立AUDIT逐项核验原生CSV重提取、网格/ΔS、14核角色、实际看图ACK、发布先于启动、串行不重叠、历史字节与预算。','- 旧批STOP与旧均匀数据不动；无hook/周期唤醒。阶段5目标需审核后另定，不自动接续。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print('FINAL',usable,t1pass,aud['new_geometry'],aud['new_Analyze'])
if __name__=='__main__':run(ROOT)
