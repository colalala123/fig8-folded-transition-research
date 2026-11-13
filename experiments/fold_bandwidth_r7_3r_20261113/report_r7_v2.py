"""R7 final evidence-driven offline report. Never starts stage4."""
from prepare_r7 import *
from manage import status
import numpy as np

def bandwidth(data,q,thr):
    if state(q) is None:return None
    f=data['f_GHz'];d=20*np.log10(abs(data['S'][:,0,0]));pp=q['shape']['inner_peaks'];lo,hi=[int(np.argmin(abs(f-p['GHz']))) for p in sorted(pp,key=lambda r:r['GHz'])]
    if max(d[lo],d[hi])>thr:return None
    l,h=lo,hi
    while l>0 and d[l]<=thr:l-=1
    while h<len(f)-1 and d[h]<=thr:h+=1
    if l==0 or h==len(f)-1:return None
    xl=float(np.interp(thr,[d[l+1],d[l]],[f[l+1],f[l]]));xh=float(np.interp(thr,[d[h-1],d[h]],[f[h-1],f[h]]))
    return xh-xl

def metrics(q,npz):
    z=np.load(npz);y=state(q)
    if y is None:return dict(usable=False)
    L=float(y[2]);out=dict(central_GHz=float(y[0]),D=float(y[1]),L=L,peaks=[p['S11_dB'] for p in q['shape']['inner_peaks']],**classify(q))
    for label,thr in [('BW15',-15),('BW20',-20),('BWref',L+.3)]:out[label]=bandwidth(z,q,thr)
    for key,s,ds in [('BW15',.125,.015),('BWref',.19,.02)]:
        b=out[key];out[key+'_star']=None if b is None else b-s*(L+20.3)
        out[key+'_star_range']=None if b is None else sorted([b-(s-ds)*(L+20.3),b-(s+ds)*(L+20.3)])
    return out

def report(root):
    cfg=read(root/'authorization.json');st=status(root);rows=[];steps=[]
    for fam in ('N04','N14'):
        for a in (0.,.6,1.,1.8,2.2,2.6):
            p=parent(fam,a);sel=selection(root,p,cfg)
            if sel:
                case,g,npz=sel
                qp=source(case)[0] if case not in cfg['case_paths'] else case_dir(root,case,cfg)/'review/extraction_R2.json'
                rows.append(dict(family=fam,a=a,case=case,Ws=g['Ws'],role='回顾既有' if case not in cfg['case_paths'] else '前瞻调参',**metrics(read(qp),npz)))
            else:rows.append(dict(family=fam,a=a,case=None,tuned=False,role='未调准或尚未完成'))
    for p in cfg['parent_order'][:8]:
        for r in histories(root,p,cfg)[1:]:
            t=r['tuning'];steps.append(dict(case=r['case'],base_case=t['base_case'],predicted_change=t['predicted_change'],
              actual_change=(state(r['q'])-np.array(t['base_y'])).tolist(),actual_y=state(r['q']).tolist(),J=t['J'],broyden_updates=t['broyden_updates']))
    by={(r['family'],r['a']):r for r in rows};scores={}
    p1=[];p2=[];p3=[];p4=[]
    ws_predictions={'N04':{0.:.362,.6:.366,2.2:.449,2.6:.519},'N14':{0.:.322,.6:.335,1.:.337,2.6:.470}}
    for fam,low,high in [('N04',6.28,6.38),('N14',6.15,6.25)]:
        mid=[by[fam,a].get('BW15_star') for a in (.6,1.,1.8,2.2)]
        p1.append(dict(family=fam,passed=all(v is not None for v in mid) and max(mid)-min(mid)<=.05 and all(low<=v<=high for v in mid),values=mid))
        for a,bounds,arr in [(2.6,[.05,.15],p2),(0.,[0.,.11],p3)]:
            x,y=by[fam,1.8].get('BW15_star'),by[fam,a].get('BW15_star');delta=None if x is None or y is None else x-y
            arr.append(dict(family=fam,delta_GHz=delta,passed=None if delta is None else bounds[0]<=delta<=bounds[1]))
        for a,pred in ws_predictions[fam].items():
            actual=by[fam,a].get('Ws');p4.append(dict(family=fam,a=a,predicted=pred,actual=actual,passed=None if actual is None else abs(actual-pred)<=.015))
    scores=dict(P1=p1,P2=p2,P3=p3,P4=p4)
    power=[]
    for p in cfg['parent_order'][8:]:
        dp=root/'decisions'/(p+'_FINAL.json')
        if not dp.exists() or read(dp).get('skipped') or cfg['designs'][p]['kind']!='LOSSLESS':continue
        case=read(dp)['selected_case'];w=case_dir(root,case,cfg);z=np.load(w/'native/full_modes.npz');bal=np.load(w/'review/lossless_modal_balance.npz')
        bind=cfg['designs'][p]['parent'];sel=selection(root,bind,cfg);_,g,npz=sel
        qpath=source(sel[0])[0] if sel[0] not in cfg['case_paths'] else case_dir(root,sel[0],cfg)/'review/extraction_R2.json'
        q=read(qpath);f=z['f_GHz'];fr0=q['bandwidths']['BW15']['low_GHz'];fr1=q['bandwidths']['BW15']['high_GHz'];band=(f>=fr0)&(f<=fr1);valid=bal['valid']&band
        S=z['S'];mode2={f'S({o},{i})':float(abs(S[band,oi,ii]).max()) for oi,o in enumerate(['1:1','1:2','2:1','2:2']) for ii,i in enumerate(['1:1','1:2','2:1','2:2']) if ':2' in (o,i) or o.endswith(':2') or i.endswith(':2')}
        vals=bal['residual_fraction'][valid]
        power.append(dict(case=case,family=cfg['designs'][p]['family'],a=cfg['designs'][p]['nominal_a_mm'],main_band_valid=int(valid.sum()),main_band_total=int(band.sum()),
            mean_residual=None if not len(vals) else float(vals.mean()),min_residual=None if not len(vals) else float(vals.min()),max_residual=None if not len(vals) else float(vals.max()),mode2_maximum_magnitudes=mode2,full_modal_power_certified=False,quantity='辐射加数值误差；含模式截断和边界不确定性，非纯辐射'))
        import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
        fig,ax=plt.subplots();ax.plot(f[band],bal['residual_fraction'][band]);ax.set(xlabel='Frequency (GHz)',ylabel='1 - sum |S_propagating|^2',title=case);ax.grid();fig.tight_layout();fig.savefig(w/'review/RADIATION_PLUS_NUMERICAL.png',dpi=140);plt.close(fig)
    gate={}
    for fam in ('N04','N14'):
        rr=[r for r in rows if r['family']==fam and r.get('tuned')];ll={x['a'] for x in power if x['family']==fam}
        needed={r['a'] for r in rr if r['a'] in (0.,.6,1.8,2.2,2.6)}
        gate[fam]=dict(usable=len(rr),low=any(r['a']<=.6 for r in rr),high=any(r['a']>=2.2 for r in rr),lossless_complete=needed<=ll)
    gate_pass=all(r['usable']>=4 and r['low'] and r['high'] and r['lossless_complete'] for r in gate.values())
    final=HERE/'final';final.mkdir(exist_ok=False)
    for name,v in [('METRICS',rows),('PREDICTION_SCORES',scores),('TUNING_STEPS',steps),('LOSSLESS_POWER',power),('GATE',dict(passed=gate_pass,by_family=gate,stage4_authorized=False))]:write(final/(name+'.json'),v)
    lines=['# R7 3R结果报告','',f'3R数量条件{"满足" if gate_pass else "未满足或尚未完成"}。本轮仅执行3R，阶段4/5未启动；不把可用等纹波点冒充两个内峰均低于−20 dB的交付设计。',
       f"累计几何{st['geometry_total']}/187，阶段3 {st['stage3_geometries']}/42；累计实际Analyze {st['actual_Analyze_total']}。",'',
       '|家族|a mm|角色|可用|中央谷GHz|D dB|L dB|BW15 GHz|BW20 GHz|BWref GHz|BW15* GHz|BWref* GHz|','|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:lines.append('|'+ '|'.join(str(r.get(k,'—')) for k in ['family','a','role','tuned','central_GHz','D','L','BW15','BW20','BWref','BW15_star','BWref_star'])+'|')
    lines+=['','冻结斜率：s15=0.125±0.015、sref=0.19±0.02 GHz/dB；上下界见METRICS.json。不用事后拟合替换冻结折算。',
       '','## 四条预测逐条评分','```json',json.dumps(scores,ensure_ascii=False,indent=2),'```','',
       '每次尝试预测/实际变化见TUNING_STEPS.json。无耗余量与所有涉及模式2的最大模值见LOSSLESS_POWER.json；频率曲线见各对照review。',
       '','无耗广义S仅计传播模式。余量标为“辐射加数值误差”，不使用异常的Use Power S。full_modal_power_certified=false。',
       '','现有数据是回顾性数据，新点为预登记的前瞻调参尝试；非独立盲测。旧R3登记保留但已被R7取代。3R完成后停下等审核，不进入阶段4。']
    (final/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(final/'MANIFEST.json',{p.name:sha(p) for p in final.iterdir() if p.is_file()})
    print('FINAL_GATE',gate_pass,gate)
if __name__=='__main__':report(ROOT)
