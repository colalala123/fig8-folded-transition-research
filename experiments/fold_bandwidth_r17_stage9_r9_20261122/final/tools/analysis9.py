"""Offline stage-9 reporting, not part of the frozen solver. All frequencies GHz unless marked."""
import sys, json, csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
import stage9 as s,stage8
from common_stage2 import HERE,REPO,read,sha,case_dir
from manage import measurement
from prepare_r10 import initial,history_for,dec
from tuning import seq_j,coordinate,state
RT=s.ROOT; H=s.HERE
OUT=H/'final'
def ser(obj):
    if isinstance(obj,np.generic):return obj.item()
    if isinstance(obj,np.ndarray):return obj.tolist()
    raise TypeError(type(obj).__name__)
def dump(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False,default=ser);f.write('\n')
def case(w):
    q=read(w/'review/extraction_R2.json');m=measurement(w)
    with (w/'native/full_modes.csv').open(newline='') as f:
        rows=csv.DictReader(f);rows=list(rows)
    def refl(mode):
        return 20*np.log10(np.maximum(np.hypot([float(r[f'S({mode},1:1)_real']) for r in rows],[float(r[f'S({mode},1:1)_imag']) for r in rows]),1e-15))
    ff=np.array([float(r['f_GHz']) for r in rows]);db=refl('1:1')
    v=q['shape'].get('central_valley_GHz');edge=None
    if v is not None:
        idx=int(np.argmin(abs(ff-v)));assert abs(ff[idx]-v)<1e-7
        if db[idx]<=-20:
            badleft=np.where(db[:idx]>-20)[0];badright=np.where(db[idx+1:]>-20)[0]
            if len(badleft) and len(badright):
                k=badleft[-1];j=idx+badright[0]+1
                cross=lambda i:ff[i]+(-20-db[i])/(db[i+1]-db[i])*(ff[i+1]-ff[i])
                edge=[float(cross(k)),float(cross(j-1))]
    e2=stage8.edge_from_run(w)
    if edge is None:assert e2 is None
    else:np.testing.assert_allclose(edge,[e2['low_GHz'],e2['high_GHz']],atol=1e-10,rtol=0)
    if m.get('BW20_GHz') is not None:
        assert edge is not None and abs(edge[1]-edge[0]-m['BW20_GHz'])<1e-8
        mask=(ff>=edge[0])&(ff<=edge[1]);assert abs(refl('2:1')[mask].min()-m['S21_min_dB'])<1e-9
    summary=read(w/'SUMMARY.json');sd=read(w/'INPUT.json')['design']
    return dict(case=w.name,measurement=m,edges=edge,full_three_valley_window=m.get('BW20_GHz') is not None,geometry_mm=sd['geometry_mm'],geometry_base_mm=sd.get('base_geometry_mm'),central_state=state(q),prediction=(sd.get('prediction') or {}).get('response_y'),role=sd['data_role'],csv_sha256=sha(w/'native/full_modes.csv'),source=w.relative_to(REPO).as_posix(),mesh=summary['record'].get('mesh_cells'),delta_s=summary['record'].get('delta_s'),Analyze=summary['record'].get('Analyze_requested'))
def gamma(t):
    return max(10**(t['measurement'][p]/20) for p in ('low_peak_dB','high_peak_dB'))
def pair(n,c):
    if c is None or n is None:return None
    return dict(dGamma=gamma(c)-gamma(n),adjusted_borrowed=gamma(c)+.002336,robust_borrowed=gamma(c)+.002336<=.1,edge_shift_MHz=(1000*(np.array(c['edges'])-n['edges'])).tolist() if c['edges'] and n['edges'] else None)
def inter(points):
    if len(points)!=5 or any(v is None for v in points.values()):return None
    lo=max(p[0] for p in points.values());hi=min(p[1] for p in points.values())
    return dict(edges=[lo,hi] if hi>=lo else [],width=max(0.,hi-lo),lower_limiter=max(points,key=lambda k:points[k][0]),upper_limiter=min(points,key=lambda k:points[k][1]))
def science():
    cfg=read(RT/'authorization.json')
    decisions={n:dec(RT,n) for n in s.ORD}
    raw={c:case(H/'results'/c) for c in cfg['case_specs'] if (H/'results'/c/'review/visual_ack.json').is_file()}
    def chosen(n):
        c=decisions[n].get('selected_case');return raw.get(c)
    # Fixed historical anchors: do not promote tuned follow-ups into blind tests.
    old=read(s.H8/'final/RESULTS.json')
    hist={k:case(w) for k,w in {'nominal':s.W4,'C1':s.W4RUNS['C1W'],'C2':s.W4RUNS['C2W'],'C3':s.W4RUNS['C3W'],'dense':s.W4RUNS['dense']}.items()}
    b1h=REPO/'experiments/fold_bandwidth_r12_stage6_r4_20261115/results/S6R10_B1R__T3'
    b1c=REPO/'experiments/fold_bandwidth_r14_stage6_r6_20261116/results/S6R10_C1R__T1'
    b1=case(b1h);bc=case(b1c)
    v5=case(s.H8/'results/S8R16_W5R__T1');c5=case(s.H8/'results/S8R16_C1W5__T1')
    jacs={}
    for n in s.WIDTHS:
        if (H/'appendices'/(n+'.json')).exists():
            histn=history_for(RT,n,cfg);ji=initial(RT,n)
            J,log=seq_j(histn,'folded',ji);jacs[n]=dict(initial=ji,final=J,change_vs_B1=J-s.J0,updates=log)
    gBW=np.array(read(REPO/'experiments/fold_bandwidth_review_r17_20261121/out/S8_RECOMPUTED.json')['BW_gradient_MHz_per_mm_Lm_Lc_Ws'])
    def reduced(t,J):
        dx=np.linalg.solve(np.array(J).T,np.array(s.TARGET)-t['central_state']);return dict(dx=dx,delta_BW_MHz=float(gBW@dx),estimated_BW_GHz=t['measurement']['BW20_GHz']+gBW@dx/1000,basis='local B1 BW gradient times three-target Jacobian correction; not HFSS')
    widths={'B1R':dict(nominal=b1,C1=bc,C1_ref=b1,delta=pair(b1,bc),normalized=reduced(b1,s.J0),width=2.35),'W4R':dict(nominal=hist['nominal'],C1=hist['C1'],C1_ref=hist['nominal'],delta=pair(hist['nominal'],hist['C1']),normalized=reduced(hist['nominal'],jacs['W5R']['final']),width=2.65)}
    for n,c,wm in [('W5R','DC1',2.8),('W6R','C1W6',2.95),('W7R','C1W7',3.10)]:
        nom=chosen(n) if decisions[n].get('passed') else None
        co=chosen(c);ref=nom
        if n=='W5R' and co is None:co,ref=c5,v5
        widths[n]=dict(nominal=nom,C1=co,C1_ref=ref,delta=pair(ref,co),normalized=None,width=wm)
    slopes=[]
    for a,b in zip(list(widths),list(widths)[1:]):
        wa,wb=widths[a],widths[b]
        if wa['nominal'] and wb['nominal']:
            def ww(w):return w['normalized']['estimated_BW_GHz'] if w['normalized'] else w['nominal']['measurement']['BW20_GHz']
            slopes.append(dict(pair=[a,b],gain_GHz=ww(wb)-ww(wa),slope_GHz_per_mm=(ww(wb)-ww(wa))/(wb['width']-wa['width']),converted=bool(wa['normalized'] or wb['normalized'])))
    selection=read(H/'appendices/9D.json') if (H/'appendices/9D.json').is_file() else None
    winner=selection['selected'] if selection else 'W4R'
    five=hist if winner=='W4R' else dict(nominal=chosen(winner),C1=widths[winner]['C1'],C2=chosen('DC2'),C3=chosen('DC3'),dense=chosen('Ddense'))
    whole=inter({k:(t['edges'] if t else None) for k,t in five.items()})
    own_mesh=None;own_corner=None
    if five['dense'] and five['nominal']:
        own_mesh=max(0.,gamma(five['dense'])-gamma(five['nominal']))
        if five['C1']:own_corner=gamma(five['C1'])+own_mesh
    Q={k:None for k in ['Q36','Q37','Q38','Q39','Q40','Q41']};detail={};bt=raw.get('S9R17_W5R__T4')
    if bt and bt['central_state'] is not None:
        y=bt['central_state'];m=bt['measurement'];peaks=[m['low_peak_dB'],m['high_peak_dB']]
        olderr=max(abs(y[0]-6.74)/.01,abs(y[1])/.2,max(abs(p-s.TARGET[2]) for p in peaks)/.1)
        detail['Q36_R8_error']=olderr;Q['Q36']=bool(olderr<3 and 6.72<=y[0]<=6.76 and abs(y[1])<=.35 and min(peaks)>=-23 and max(peaks)<=-22.6)
    w5,w6,w7=(widths[k]['nominal'] for k in s.WIDTHS)
    Q['Q37']=bool(w5 and 6.54<=w5['measurement']['BW20_GHz']<=6.62) if bt else None
    def bw(t):return t['measurement']['BW20_GHz']
    t6=raw.get('S9R17_W6R__T1');t7=raw.get('S9R17_W7R__T1')
    if t6:
        y=t6['central_state'];Q['Q38']=bool(y is not None and 6.71<=y[0]<=6.77 and abs(y[2]-s.TARGET[2])<=.25 and w6 and w5 and .08<=bw(w6)-bw(w5)<=.22)
    cp=widths['W6R']['delta']
    if cp:
        a=cp['edge_shift_MHz']
        Q['Q39']=bool(a and .018<=cp['dGamma']<=.024 and cp['robust_borrowed'] and max(abs(np.asarray(a)-[-64.7,211.5]))<=15)
    residual=None
    if winner!='W4R' and selection:
        pred=selection['selected_edges'];residual={k:(1000*(np.array(t['edges'])-pred[k])).tolist() for k,t in five.items() if t and t['edges']}
        if whole and all(k in residual for k in ('C2','C3','dense')):
            dr=(whole['width']-selection['candidates'][winner]['width_GHz'])*1000;detail['Q40_width_residual_MHz']=dr
            Q['Q40']=bool(max(abs(v) for k in ('C2','C3','dense') for v in residual[k])<=20 and abs(dr)<=30)
    if t7:Q['Q41']=bool(w7 and w6 and .05<=bw(w7)-bw(w6)<=.22)
    return dict(plan_commit=s.COMMIT,freeze_commit='a28c28b7ddcf28ee753071d01921c1b74700c888',target=s.TARGET,margin=s.M,decisions=decisions,raw=raw,widths=widths,jacobians=jacs,J0=s.J0,slopes=slopes,selection=selection,winner=winner,five=five,intersection=whole,own_nonnegative_mesh_dGamma=own_mesh,C1_plus_own_bias=own_corner,W4R_five_reference=hist,W4R_intersection=inter({k:t['edges'] for k,t in hist.items()}),Q=Q,score_detail=detail,transfer_residual_MHz=residual,limits='five simulated main components, no connector, no manufacturing yield certificate')
if __name__=='__main__':dump(OUT/'RESULTS.json',science())
