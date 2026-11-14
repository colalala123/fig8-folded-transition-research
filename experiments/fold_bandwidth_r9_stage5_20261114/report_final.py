"""OFFLINE ONLY post-freeze reporting. Not imported by dispatch, worker, fit or tuner."""
import sys,csv,itertools,json
from pathlib import Path
import numpy as np
from prepare_r9 import *
from manage import scores,delivery
from laws import cost_predictions

def updated_J(hh):
    J=J0.copy();logs=[]
    for r in hh:
        t=r.get('tuning')
        if t:
            base=next(b for b in hh if b['case']==t['base_case'])
            J,log=broyden(np.array(t['J']),coordinate(r['q']['geometry_mm'],'folded')-coordinate(base['q']['geometry_mm'],'folded'),state(r['q'])-state(base['q']))
            logs.append(dict(case=r['case'],**log))
    return J,logs

def tolerance(q,hh):
    J,logs=updated_J(hh);K=np.array([J[0],J[1],2*J[1]+J[2]])
    y=state(q);peak=lambda yy:[float(yy[2]-yy[1]/2),float(yy[2]+yy[1]/2)]
    singles={}
    for i,k in enumerate(['Lm','Ls1','Ws']):
        dx=np.zeros(3);dx[i]=.02;v=dx@K
        singles[k]=dict(plus_response=v.tolist(),minus_response=(-v).tolist(),plus_peaks=peak(y+v),minus_peaks=peak(y-v),worst_peak_dB=max(peak(y+v)+peak(y-v)))
    corners=[]
    for c in itertools.product([-.02,.02],repeat=3):
        v=np.array(c)@K;yy=y+v
        corners.append(dict(delta_Lm_Ls1_Ws_mm=c,delta_valley_D_L=v.tolist(),peaks_dB=peak(yy),valley_GHz=float(yy[0])))
    worst=max(max(c['peaks_dB']) for c in corners)
    Klit=np.array([J[0],J[1],J[2]-4*J[1]]);literal=[]
    for c in itertools.product([-.02,.02],repeat=3):
        yy=y+np.array(c)@Klit;literal.append(dict(delta_Lm_Ls1_Ws_mm=c,peaks_dB=peak(yy),valley_GHz=float(yy[0])))
    return dict(J_Lm_Lc_Ws=J.tolist(),J_Lm_Ls1_Ws_fixed_a_g=K.tolist(),updates=logs,single_parameter_pm002=singles,corners=corners,worst_inner_peak_dB=worst,worst_still_below_minus20=bool(worst<=-20),valley_range_GHz=[min(c['valley_GHz'] for c in corners),max(c['valley_GHz'] for c in corners)],assumption='Primary: same parameterization as archived 1b, a/g held fixed, deltaLc=deltaLs1+2deltaWs. This adjusts derived Ls2/Ls3 consistently, and is not a literal independent etch-width model.',literal_Ws_only_conditional_projection=dict(J_Lm_Ls1_Ws=Klit.tolist(),corners=literal,worst_peak_dB=max(max(c['peaks_dB']) for c in literal),not_full_tolerance_prediction=True,missing_derivatives='If only Ws changes and Ls2/Ls3 are held fixed: deltaLc=-4deltaWs, deltaa=-deltaWs, deltag=-2deltaWs. Local J has no independent a/g derivatives, so this projection omits those unknown effects and cannot certify even a nominally passing corner.'),manufacturing_certified=False)

def raw_replay(out):
    sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_review_r7_20261113'))
    sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_review_r8_20261113'))
    from review_checks import load
    from review_3r import metrics
    cfg=read(ROOT/'authorization.json');checks=[]
    for gp in sorted((ROOT/'ledger').glob('geometry_*.json')):
        case=read(gp)['case'];w=case_dir(ROOT,case,cfg);rec=read(w/'RUN_RECORD.json');rev=read(w/'review/REVIEW_STAGE3.json');q=read(w/'review/extraction_R2.json');y=state(q);r=metrics(*load(w/'native/full_modes.csv'))
        diffs=dict(center=r['valley_GHz']-y[0],D=r['D_dB']-y[1],L=r['peak_mean_dB']-y[2])
        for b in ('BW15','BW20'):
            v=q['bandwidths'][b]['BW_GHz'];z=r[b]
            if (v is None)!=(z is None):raise RuntimeError('CSV null mismatch '+case+b)
            diffs[b]=(v-z) if v is not None else None
        if max(abs(v) for v in diffs.values() if v is not None)>1e-9:raise RuntimeError('CSV metric mismatch '+case)
        pub=read(ROOT/'publications'/(case+'.json'));start=read(w/'evidence/start_requested.json');ack=read(w/'review/visual_ack.json')
        if pub['at']>=start['at'] or not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png'):raise RuntimeError('publication/actual-view proof '+case)
        if not rev['numerical_pass'] or not rec['cleanup']['released']:raise RuntimeError('numeric/cleanup '+case)
        checks.append(dict(case=case,raw_csv_sha256=sha(w/'native/full_modes.csv'),diffs=diffs,mesh=rec['mesh_cells'],delta_s=rec['delta_s'],API=rec['Analyze_requested'],published_before_start=True,actual_view=True,cleanup=True,start=start['at'],end=rec['finished_at']))
    intervals=sorted(checks,key=lambda r:r['start'])
    if any(a['end']>b['start'] for a,b in zip(intervals,intervals[1:])):raise RuntimeError('serial overlap')
    total=len(list((ROOT/'ledger').glob('Analyze_*.json')))
    if sum(x['API'] for x in checks)!=total:raise RuntimeError('ledger mismatch')
    for p,h in cfg['historical_hashes'].items():
        if sha(p)!=h:raise RuntimeError('historical changed '+p)
    for p,h in {**cfg['code_hashes'],**cfg['plan_hashes'],**cfg['frozen_hashes']}.items():
        if sha(REPO/p)!=h:raise RuntimeError('frozen changed '+p)
    write(out/'AUDIT.json',dict(passed=True,geometries=len(checks),new_API=total,total_geometry=151+len(checks),total_API=1406+total,checks=checks,serial_nonoverlap=True,old_evidence_unchanged=True,no_hooks=True))

def build():
    out=HERE/'final';out.mkdir(exist_ok=False);cfg=read(ROOT/'authorization.json');raw_replay(out)
    ds=[read(ROOT/'decisions'/(p+'_FINAL.json')) for p in cfg['parent_order'] if (ROOT/'decisions'/(p+'_FINAL.json')).exists()]
    selected=[];t1=[];tols={}
    for d in ds:
        if d.get('skipped'):continue
        c=d['selected_case'];p=d['parent_id'];w=case_dir(ROOT,c,cfg);fz=read(w/'input/freeze.json');q=read(w/'review/extraction_R2.json');g=q['geometry_mm'];dim=chain.dimensions(g);sc=scores(q);sc.pop('delivery',None)
        rev=read(w/'review/REVIEW_STAGE3.json');zz=np.load(w/'native/full_modes.npz');mins={}
        for band in ('BW15','BW20'):
            bb=q['bandwidths'][band]
            mask=(zz['f_GHz']>=bb['low_GHz'])&(zz['f_GHz']<=bb['high_GHz']) if bb['BW_GHz'] is not None else np.zeros(len(zz['f_GHz']),dtype=bool)
            mins[band]=float(np.min(20*np.log10(abs(zz['S'][mask,2,0])))) if mask.any() else None
        selected.append(dict(parent=p,case=c,geometry_mm=g,a=dim['a_mm'],g=dim['g_mm'],tip_line_clearance_mm=(g['Ls1']-2*g['Ls3']-max(g['Wm'],1.82))/2,tip_tip_clearance_mm=g['Ls1']-2*g['Ls3'],**sc,delivery_pass=d.get('delivery_pass'),data_role=d['data_role'],inner_peaks=q['shape']['inner_peaks'],S21_min_dB=mins,main_bands={k:q['bandwidths'][k] for k in ('BW15','BW20')},mesh=rev['mesh_cells'],delta_s=rev['delta_s'],P_eff=rev['metrics'].get('P_eff'),R_eff=rev['metrics'].get('R_eff'),circuit_extraction_nonunique=q['circuit'].get('extraction_nonunique'),certification_level='nominal interpolating only; dense confirmation separately; not manufacturing'))
        if p in cfg['parent_order'][6:9]:tols[p]=tolerance(q,histories(ROOT,p,cfg))
        cc=p+'__T1';ww=case_dir(ROOT,cc,cfg) if cc in cfg['case_paths'] else None
        if ww and (ww/'review/extraction_R2.json').exists() and not p.endswith('dense'):
            qq=read(ww/'review/extraction_R2.json');f=read(ww/'input/freeze.json')['design'];ys=state(qq);pred=f['prediction'];errs=[ys[0]-pred['central_valley_GHz'],ys[1]-pred['D_dB'],ys[2]-pred['L_dB']];bw=scores(qq)['BW15'];bwerr={k:(v+.125*(ys[2]+20.3)-bw)*1000 if bw is not None else None for k,v in pred['BW15_star_GHz'].items()}
            strict=abs(errs[0])<=.030000000001 and abs(errs[1])<=.7 and abs(errs[2])<=.3 and bwerr['span'] is not None and abs(bwerr['span'])<=40
            t1.append(dict(case=cc,frozen=pred,actual=scores(qq),response_errors=errs,BW15_conditioned_on_actual_L_errors_MHz=bwerr,primary_span_four_joint_pass=bool(strict),data_role='prospective_T1_not_tuned_score'))
    sel={s['parent']:s for s in selected};usable=[s for s in selected if s['parent'] in cfg['parent_order'][:6] and s['usable']]
    write(out/'SELECTED.json',selected);write(out/'T1_SCORES.json',t1)
    q6={}
    for k,lo,hi in [('W1',6.61,6.72),('W2',6.79,6.91),('W3',6.96,7.10)]:
        s=sel.get('S5R9_'+k);v=s['BW15_star'] if s and s['usable'] else None;q6[k]=dict(actual=v,prediction=[lo,hi],passed=None if v is None else bool(lo<=v<=hi),unscorable_reason=None if v is not None else 'not R7 usable or skipped; do not infer saturation from unbalanced/shifted data')
    w2=q6['W2']['actual'];q6['saturation_between_2p06_2p35']=None if w2 is None else bool(w2<6.75)
    cs=[]
    for k in ('D1c','S1'):
        s=sel.get('S5R9_'+k);v=s['BW15_star'] if s and s['usable'] else None;cs.append(dict(design=k,cost_MHz=None if v is None else (6.332-v)*1000,passed=None if v is None else bool(6.332-v<=.05)))
    q7=dict(points=cs,passed=all(c['passed'] for c in cs) if all(c['passed'] is not None for c in cs) else None)
    q8={}
    for mode in ('tip','sum','a','span','rho'):
        e=[(cost_predictions(s['geometry_mm'])[mode]-s['BW15_star'])*1000 for s in usable];q8[mode]=dict(errors_MHz=e,RMSE_MHz=float(np.sqrt(np.mean(np.square(e)))) if e else None,cases=[s['case'] for s in usable])
    ranked=sorted((v['RMSE_MHz'],k) for k,v in q8.items() if v['RMSE_MHz'] is not None);winner=ranked[0][1] if len(ranked)>=2 and ranked[0][0]<=25 and ranked[0][0]<=.7*ranked[1][0] else 'still_indistinguishable'
    b1=sel.get('S5R9_B1');q9=None
    if b1 and b1['BW20'] is not None:
        # Equal-ripple platform belongs to 5A at the selected Wm, not the deeper delivery's normalized BW15.
        choice=read(HERE/'offline_5B/REGISTRY.json')['Wm_star'];diff=choice['BW15_star']-b1['BW20'];q9=dict(equal_ripple_platform_source=choice,difference_GHz=diff,passed=.30<=diff<=.40)
    dense=sel.get('S5R9_B1dense');q10=None
    if dense and b1:
        a=read(case_dir(ROOT,b1['case'],cfg)/'review/extraction_R2.json');b=read(case_dir(ROOT,dense['case'],cfg)/'review/extraction_R2.json');pa=[p['S11_dB'] for p in a['shape']['inner_peaks']];pb=[p['S11_dB'] for p in b['shape']['inner_peaks']];dif=np.array(pb)-pa
        q10=dict(nominal_peaks=pa,dense_peaks=pb,difference_dB=dif.tolist(),prediction_pass=bool(max(abs(dif))<=.35),margin_insufficient=bool(max(abs(dif))>.5),confirmation_hard_minus20_pass=bool(max(pb)<=-20),center_difference_GHz=b['shape']['central_valley_GHz']-a['shape']['central_valley_GHz'],BW20_difference_GHz=(dense['BW20']-b1['BW20']) if dense['BW20'] is not None and b1['BW20'] is not None else None)
    write(out/'REVIEWER_SCORES.json',dict(Q6=q6,Q7=q7,Q8=dict(models=q8,winner=winner,scope='pre-registered predictive comparison on the five new usable 5A points; not a physical causal identification',all_new_usable_a_at_most_1p8=all(s['a']<=1.8+1e-8 for s in usable),caveat='Every usable 5A a is below the frozen a-model knee 2.39mm. A win cannot independently establish the large-a hinge mechanism, and does not erase earlier retrospective/model failures.'),Q9=q9,Q10=q10))
    # Independent archival Ws-ladder check, same fixed-a/g physical dimensional coordinate.
    ws=[r for r in read(HERE/'offline/TRAINING.json')['rows'] if r['case'].startswith('S1_WS_')];xs=np.array([r['geometry_mm']['Ws'] for r in ws]);ys=np.array([r['y'] for r in ws]);Kws=np.linalg.lstsq(np.c_[np.ones(len(xs)),xs-xs.mean()],ys,rcond=None)[0][1]
    bench=dict(cases=[r['case'] for r in ws],Ws_range=[min(xs),max(xs)],empirical_response_per_mm=Kws.tolist(),empirical_low_high_peak_per_001mm=[float((Kws[2]-Kws[1]/2)*.01),float((Kws[2]+Kws[1]/2)*.01)],note='1b fixed a/g adjusted Ls2/Ls3 consistently; grid-limited valley and native noise; archival ~0.3dB/0.01mm is approximate, not an imposed calibration')
    for p,t in tols.items():
        k=np.array(t['J_Lm_Ls1_Ws_fixed_a_g'])[2];t['Ws_sensitivity_vs_1b']=dict(predicted_per_001mm=[float((k[2]-k[1]/2)*.01),float((k[2]+k[1]/2)*.01)],empirical=bench['empirical_low_high_peak_per_001mm'])
    write(out/'TOLERANCE.json',dict(designs=tols,archival_Ws_ladder=bench,certification=False))
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axs=plt.subplots(3,1,figsize=(11,12))
    for ax,p in zip(axs,cfg['parent_order'][6:9]):
        s=sel.get(p)
        if s:
            z=np.load(case_dir(ROOT,s['case'],cfg)/'native/full_modes.npz');fr=z['f_GHz'];S=z['S'];ax.plot(fr,20*np.log10(abs(S[:,0,0])),label='S11 nominal');ax.plot(fr,20*np.log10(abs(S[:,2,0])),label='S21 nominal')
            if p.endswith('B1') and dense:
                z=np.load(case_dir(ROOT,dense['case'],cfg)/'native/full_modes.npz');ax.plot(z['f_GHz'],20*np.log10(abs(z['S'][:,0,0])),ls='--',label='S11 dense')
        ax.set(xlim=(2.5,11),ylim=(-50,1),title=p,xlabel='GHz',ylabel='dB');ax.axhline(-20.5,c='gray',ls=':');ax.legend();ax.grid(alpha=.3)
    fig.tight_layout();fig.savefig(out/'DELIVERY_CURVES.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));old=read(HERE/'offline/COST_REFIT.json')['points'];plat=[r for r in old if abs(r['a']-1.8)<1e-6 and abs(r['g']-.55)<1e-6];ax.scatter([r['Wm'] for r in plat],[r['y'] for r in plat],label='Historical platform')
    for s in usable:
        if s['parent'].split('_')[-1].startswith('W'):ax.scatter(s['geometry_mm']['Wm'],s['BW15_star'],marker='*',s=120);ax.annotate(s['parent'].split('_')[-1],(s['geometry_mm']['Wm'],s['BW15_star']))
    ax.set(xlabel='Wm (mm)',ylabel='BW15* (GHz)',title='R9 measured usable platforms (tuned)');ax.grid(alpha=.3);ax.legend();fig.tight_layout();fig.savefig(out/'WM_PLATFORM.png',dpi=150);plt.close(fig)
    audit=read(out/'AUDIT.json');lines=['# R9 阶段5中文总结','','## 总结',f"本轮已按有限方案结束：新增 {audit['geometries']}/26 个几何、{audit['new_API']} 次实际 Analyze；累计 {audit['total_geometry']}/187 个几何、{audit['total_API']} 次实际请求。14核1组串行，无hook，无阶段6。",'',f"5A 可用 {len(usable)} 项；5B 名义交付 {sum(bool(s['delivery_pass']) for s in selected if s['parent'] in cfg['parent_order'][6:9])}/3。不把研究可用、两个内峰达标、名义插值、密网格确认、加工认证混为一谈。",'', '## 选定数据','|设计|案例|中心 GHz|D dB|L dB|BW15* GHz|BW20 GHz|研究可用|交付|','|---|---|---|---|---|---|---|---|---|']
    for s in selected:lines.append('|'+ '|'.join(str(v) for v in [s['parent'],s['case'],s['center'],s['D'],s['L'],s['BW15_star'] if s['usable'] else '不用于规律',s['BW20'],s['usable'],s['delivery_pass']])+'|')
    lines+=['','## T1前瞻与审核方预测','每个T1的冻结值、实测与四门槛评分见 T1_SCORES.json；T2以后永久标记调参，D1c/D3c是T4/T5，不作独立T1。','```json',json.dumps(read(out/'REVIEWER_SCORES.json'),ensure_ascii=False,indent=2),'```','','Q7缺可用点时不可判，不计失败。Q8严格使用五个求解前冻结模型和实测调准几何；未达≤25MHz且领先第二名30%就保持“分不开”。Wm是否饱和按Q6原门槛判；不把有限点线性趋势推广到任意宽度。','','## 交付尺寸与公差']
    for s in selected:
        p=s['parent']
        if p not in cfg['parent_order'][6:9]:continue
        lines += ['', '### '+p,'几何(mm)：`'+json.dumps(s['geometry_mm'])+'`',f"端头到微带净距 {s['tip_line_clearance_mm']} mm；两端头横向净距 {s['tip_tip_clearance_mm']} mm。",f"两个实际内峰：{s['inner_peaks']}；BW20带内最差S21={s['S21_min_dB']['BW20']} dB。",'公差：```json\n'+json.dumps(tols[p],ensure_ascii=False,indent=2)+'\n```']
    lines+=['','![交付曲线](DELIVERY_CURVES.png)','','![Wm平台](WM_PLATFORM.png)','','B1密网格只核验同一几何的数值变化；B2/B3没有独立更密网格确认，其−20dB推断依赖B1和0.5dB余量。若Q10偏差超过0.5dB，B2/B3结论须降级；确认失败不追加调参。','','公差是局部Broyden线性外推，不含基材、连接器及联合电磁重算，不是制造认证。坐标转换在固定a/g下为δLc=δLs1+2δWs；对三变量8个最坏角点完整枚举，不只做RSS。1b核对见TOLERANCE.json。','','## 证据与接续边界','全部原生CSV独立复算一致；每项实际看图ACK、角色/网格/串行/清理/求解前推送证据见AUDIT.json。预算逐请求记账，未使用的额度不转成新授权。阶段5完成后停止，任何后续几何或认证需新的人类授权。']
    top=['',f"- W1/W2 的可用 BW15*：{q6['W1']['actual']} / {q6['W2']['actual']} GHz；按Q6门槛，2.06–2.35mm段未显示规定的饱和。W3未调准，不能用其较宽但中心偏移的曲线判断2.50mm平台。",f"- N04 的D1c/S1代价(MHz)：{[c['cost_MHz'] for c in cs]}。Q7={q7['passed']}，支持本组近似同折叠量里把折叠分配给g更便宜；不是只凭带宽就证明辐射损耗成因。",f"- Q8预注册胜出者：{winner}；各模型RMSE(MHz)={ {k:round(v['RMSE_MHz'],3) for k,v in q8.items()} }。胜出仅限这5个新可用点；它们的a≤1.8，未触发a模型2.39mm拐点，不能据此宣布a是唯一物理原因或推翻历史失败记录。",f"- B1名义BW20={b1['BW20'] if b1 else None} GHz；密网格结果见Q10。公差是条件线性估计，不等于加工后仍保证−20dB。",'']
    ii=lines.index('## 选定数据');lines[ii:ii]=top
    lines+=['','## 公差口径特别说明','主表采用与1b宽度阶梯一致的固定a/g参数化（Ws变化时同步调整派生Ls2/Ls3），δLc=δLs1+2δWs。如果理解成只改变六尺寸中的Ws、同时固定Ls2/Ls3，则δLc=δLs1−4δWs，并且a/g也发生变化；现有J没有独立a/g导数，不能完成该蚀刻模型的完整公差预测。TOLERANCE.json另列忽略未知a/g项的条件投影，明确不作认证。不能把主表当作所有真实加工误差的最坏界。','', '|设计|固定a/g口径±0.02mm联合最坏内峰(dB)|仍≤−20dB|','|---|---|---|']
    for p,t in tols.items():lines.append(f"|{p}|{t['worst_inner_peak_dB']:.4f}|{t['worst_still_below_minus20']}|")
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(audit,ensure_ascii=False)[:600])
if __name__=='__main__':build()
