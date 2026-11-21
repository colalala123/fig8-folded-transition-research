"""R16 offline evidence extraction and scoring. No RPC, git writes or dispatch."""
from pathlib import Path
import csv,math,sys,json,hashlib
import numpy as np
REPO=Path(__file__).resolve().parents[1]
H=REPO/'experiments/fold_bandwidth_r16_stage8_r8_20261121'
sys.path.insert(0,str(H))
from prepare_r10 import ROOT
from common_stage2 import read,sha,now,case_dir
import stage8,manage
H6=REPO/'experiments/fold_bandwidth_r14_stage6_r6_20261116'
H5=REPO/'experiments/fold_bandwidth_r9_stage5_20261114'
H7=stage8.H7
IND=('low_GHz','high_GHz')

def cleaned(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:cleaned(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [cleaned(v) for v in x]
    return x

def csv_edges(folder,center):
    """Second, independent implementation, from native CSV complex amplitudes."""
    f=[];v=[]
    with (folder/'native/full_modes.csv').open(encoding='utf-8-sig',newline='') as fp:
        for row in csv.DictReader(fp):
            f.append(float(row['f_GHz']))
            amp=math.hypot(float(row['S(1:1,1:1)_real']),float(row['S(1:1,1:1)_imag']))
            v.append(20*math.log10(max(amp,1e-15)))
    f=np.array(f);v=np.array(v)
    assert len(f)==len(np.unique(f)) and np.all(np.diff(f)>0)
    if center is None:return None
    c=np.flatnonzero(np.isclose(f,center,rtol=0,atol=1e-7))
    if len(c)!=1 or v[c[0]]>-20:return None
    crossings=np.flatnonzero((v[:-1]<=-20)!=(v[1:]<=-20))
    lt=crossings[crossings<c[0]];rt=crossings[crossings>=c[0]]
    if not len(lt) or not len(rt):return None
    return [float(f[i]+(-20-v[i])*(f[i+1]-f[i])/(v[i+1]-v[i])) for i in [lt[-1],rt[0]]]

def audit_trace(path):
    row=manage.measurement(path)
    q=read(path/'review/extraction_R2.json')
    e=stage8.edge_from_run(path);s=csv_edges(path,q['shape'].get('central_valley_GHz'))
    assert (e is None)==(s is None),str(path)
    err=None if s is None else max(abs(e[k]-v) for k,v in zip(IND,s))
    assert err is None or err<.000001,(path,err)
    if row.get('BW20_GHz') is not None:assert abs(e['width_GHz']-row['BW20_GHz'])<.000001
    return {**row,'edges20':e,'CSV_minus_NPZ_max_abs_MHz':None if err is None else err*1000,
            'CSV_sha256':sha(path/'native/full_modes.csv'),'geometry_mm':q['geometry_mm'],
            'whole_band_valid':bool(q['bandwidths']['BW20'].get('main_band_valid'))}

def assess(x,**details):return dict(passed=None if x is None else bool(x),details=details)
def inrange(v,a,b):return a-1e-8<=v<=b+1e-8
def gamma(m):
    return None if not m or not m.get('shape_valid') else 10**(max(m['low_peak_dB'],m['high_peak_dB'])/20)
def slope(rows):
    return [dict(from_mm=a['Wm'],to_mm=b['Wm'],GHz_per_mm=(b['BW20_GHz']-a['BW20_GHz'])/(b['Wm']-a['Wm'])) for a,b in zip(rows,rows[1:])]

def summarize():
    cfg=read(ROOT/'authorization.json');fz=read(H/'freeze/R16_R8.json')
    s6=read(H6/'final/RESULTS.json');s7=read(H7/'final/RESULTS.json')
    d={n:read(ROOT/'decisions'/(stage8.PREFIX+n+'_FINAL.json')) for n in stage8.ORDER}
    assert all(x['complete'] for x in d.values())
    nom={'W4R':audit_trace(stage8.W4)}
    five={n:audit_trace(path) for n,(path,_) in stage8.ANCHORS.items()}
    audit={}
    for n,v in d.items():
        m=None
        if v.get('selected_case'):
            p=H/'results'/v['selected_case'];m=audit_trace(p)
            if v.get('measurement',{}).get('BW20_GHz') is not None:
                assert abs(m['BW20_GHz']-v['measurement']['BW20_GHz'])<1e-9
        audit[n]=m
        if n in ('C2W','C3W'):five[n]=m
        if n in ('W5R','W6R'):nom[n]=m
    center=nom['W4R']['edges20']
    def shift(m):
        return [1000*(m['edges20'][k]-center[k]) for k in IND] if m and m.get('edges20') else [None,None]
    delta={k:shift(v) for k,v in five.items()}
    theory={'C1W':[-62,None],**fz['policy']['edge_linear_predictions_MHz']}
    residual={n:dict(measured_MHz=delta[n],predicted_MHz=v,residual_MHz=[None if x is None or y is None else x-y for x,y in zip(delta[n],v)]) for n,v in theory.items()}
    g=stage8.intersect([m.get('edges20') if m else None for m in five.values()])
    if g and not g['empty']:
        g['lower_limiter']=max(five,key=lambda n:five[n]['edges20']['low_GHz'])
        g['upper_limiter']=min(five,key=lambda n:five[n]['edges20']['high_GHz'])
    controls={n:(stage8.corner_test(m,n in ('C2W','C3W','C1W')) if m else None) for n,m in {**{k:v for k,v in five.items() if k in ('C1W','C2W','C3W')},'C1W5':audit['C1W5'],'C1W6':audit['C1W6']}.items()}
    deg={}
    for n,c in [('W5R','C1W5'),('W6R','C1W6')]:
        if gamma(audit[n]) is None or gamma(audit[c]) is None:deg[n]=None
        else:deg[n]=gamma(audit[c])-gamma(audit[n])
    deg={'B1R':s6['confirmation']['corner_minus_nominal_dGamma'],'W4R':s7['confirmation']['corner_minus_nominal_dGamma'],**deg}
    q={};v=five['C2W'];lo,hi=delta['C2W']
    q['Q31']=assess(None if not v or lo is None or not v.get('shape_valid') else bool(inrange(hi,-280,-140) and inrange(lo,20,100) and v.get('BW20_GHz') is not None and inrange(v['BW20_GHz'],5.95,6.20) and max(v['low_peak_dB'],v['high_peak_dB'])<=-20.3),shift_MHz=delta['C2W'],BW20_GHz=(v or {}).get('BW20_GHz'),peaks_dB=[(v or {}).get(k) for k in ('low_peak_dB','high_peak_dB')])
    v=five['C3W'];lo,hi=delta['C3W']
    q['Q32']=assess(None if not v or lo is None else inrange(lo,60,150) and v.get('BW20_GHz') is not None and inrange(v['BW20_GHz'],6.05,6.30),shift_MHz=delta['C3W'],BW20_GHz=(v or {}).get('BW20_GHz'))
    q['Q33']=assess(inrange(g['width_GHz'],5.85,6.15) if g else None,intersection=g)
    q['Q34']=assess(None if d['W5R'].get('missing') or d['W5R'].get('skipped') else bool(d['W5R']['passed'] and nom['W5R'] and inrange(nom['W5R']['BW20_GHz'],6.45,6.70)),tuned=d['W5R']['passed'],selected=d['W5R']['selected_case'],BW20_GHz=(nom['W5R'] or {}).get('BW20_GHz'))
    q['Q35']=assess(None if deg['W5R'] is None or not controls['C1W5'] else inrange(deg['W5R'],.018,.026) and controls['C1W5']['passed'],delta_Gamma=deg['W5R'],corner=controls['C1W5'])
    est={}
    for n,c in [('W5R','C1W5'),('W6R','C1W6')]:
        m=nom[n];cm=audit[c];est[n]=None
        if not g or g['empty'] or not m or not m.get('whole_band_valid'):continue
        a=m['edges20']['low_GHz']+g['low_GHz']-center['low_GHz'];b=m['edges20']['high_GHz']+g['high_GHz']-center['high_GHz']
        if cm and cm.get('edges20'):
            a=max(a,cm['edges20']['low_GHz']);b=min(b,cm['edges20']['high_GHz'])
        est[n]=dict(low_GHz=a if b>=a else None,high_GHz=b if b>=a else None,width_GHz=max(0,b-a),measured=False,method='transfer worst W4R edge shifts, intersect with own C1 component when available; not a tolerance certificate')
    measured_nom=[]
    for label,path in [('W1',H5/'results/S5R9_W1__T2'),('W2',H5/'results/S5R9_W2__T3')]+[(n,H6/'results'/s6['platform'][n]['decision']['selected_case']) for n in ('W3','W4')]:
        m=audit_trace(path);measured_nom.append(dict(design=label,Wm=m['geometry_mm']['Wm'],BW20_GHz=m['BW20_GHz'],mean_dB=(m['low_peak_dB']+m['high_peak_dB'])/2,measured=True))
    old_req=s7['margin']['P_req_dB'];new_req=fz['margin']['P_req_dB'];corrected=nom['W4R']['BW20_GHz']+.170*(new_req-old_req)
    robust=[dict(design='W4R',Wm=2.65,BW20_GHz=corrected,measured=False,raw_BW20_GHz=nom['W4R']['BW20_GHz'],old_req=old_req,new_req=new_req)]
    for n in ('W5R','W6R'):
        if d[n]['passed'] and nom[n]:robust.append(dict(design=n,Wm=nom[n]['geometry_mm']['Wm'],BW20_GHz=nom[n]['BW20_GHz'],measured=True))
    trials=[]
    for c,s in cfg['case_specs'].items():
        w=case_dir(ROOT,c,cfg);pub=H/'results'/c
        if not (w/'RUN_RECORD.json').exists():continue
        f=read(w/'input/freeze.json');r=read(w/'RUN_RECORD.json');v=f['design']
        t=dict(case=c,geometry_mm=v['geometry_mm'],base_geometry_mm=v['base_geometry_mm'],prediction=v.get('prediction'),mesh_cells=r.get('mesh_cells'),delta_s=r.get('delta_s'),Analyze=r['new_Analyze_requested'],numerical_pass=r['numerical_pass'],publication=read(ROOT/'publications'/(c+'.json'))['commit'])
        if (pub/'review/visual_ack.json').exists():
            m=audit_trace(pub);t.update(measurement=m,tuning=read(pub/'review/REVIEW_STAGE3.json')['tuning_status'])
            if (t['prediction'] or {}).get('response_y') and m.get('shape_valid'):
                y=[m['center_GHz'],m['high_peak_dB']-m['low_peak_dB'],(m['low_peak_dB']+m['high_peak_dB'])/2]
                t['response_minus_prediction']=[a-b for a,b in zip(y,t['prediction']['response_y'])]
        ir=json.dumps(v['cad_ir'],sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
        t['native_configuration_fingerprint']=hashlib.sha256(ir).hexdigest()
        t['proposer_history']={k:v['tuning'].get(k) for k in ('base_case','broyden_updates','actual_step','step_scale')} if v.get('tuning') else None
        trials.append(t)
    new_g=len(list((ROOT/'ledger').glob('geometry_*.json')));new_a=len(list((ROOT/'ledger').glob('Analyze_*.json')))
    assert len(trials)==new_g<=10 and sum(t['Analyze'] for t in trials)==new_a<=140
    configurations={}
    for t in trials:configurations.setdefault(t['native_configuration_fingerprint'],[]).append(t['case'])
    duplicates=[v for v in configurations.values() if len(v)>1]
    seen={};duplicate_requests=0
    for t in trials:
        key=t['native_configuration_fingerprint']
        if key in seen:duplicate_requests+=t['Analyze']
        else:seen[key]=t['case']
    recommends=['W4R']
    for n,c in [('W5R','C1W5'),('W6R','C1W6')]:
        if d[n].get('passed') and controls[c] and controls[c]['passed']:recommends.append(n)
    recommend=max(recommends,key=lambda n:nom[n]['BW20_GHz'])
    return cleaned(dict(plan_commit=fz['plan_commit'],freeze_commit='6496790f20fc161251aefe3724cda4bac3c66b1f',margin=fz['margin'],Q31_Q35_verbatim=fz['Q31_Q35_verbatim'],five=five,edge_shift_MHz=delta,guarantee=g,residuals=residual,decisions=d,nominal=nom,corner_measurements=audit,corner=controls,estimated_guarantee=est,dGamma=deg,Q=q,trials=trials,nominal_curve=measured_nom,robust_curve=robust,nominal_slopes=slope(measured_nom),robust_slopes=slope(robust),B1R=s6['nominal'],B1R_confirmation=s6['confirmation'],B1R_dense=s6['dense'],B1R_C1R=s6['C1R'],W4R_confirmation=s7['confirmation'],recommend=recommend,geometry_mm=nom[recommend]['geometry_mm'],budget=dict(new_geometries=new_g,new_Analyze=new_a,cumulative_geometries=200+new_g,cumulative_Analyze=1923+new_a,geometry_cap=212,distinct_simulated_configurations=len(configurations),duplicate_full_configuration_groups=duplicates,extra_Analyze_on_duplicate_inputs=duplicate_requests),limitations=['No new dense mesh, direct frequencies or SMA. Five-way W4R intersection covers only those simulations.', 'No probabilistic manufacturing yield; wider corners use borrowed mesh bias.']))
