"""R17 offline policy. J axes: x=[Lm,Lc,Ws] by y=[valley,D,mean]."""
import copy, json, hashlib
import numpy as np
from common_stage2 import HERE,REPO,read,sha,Path
import stage8
from tuning import state,coordinate,inverse,J0,propose_history,seq_j,delivery_error
H8=REPO/'experiments/fold_bandwidth_r16_stage8_r8_20261121'
ROOT8=Path('F:/2026-1/circuit/test/output/fig8_r16_stage8_r8_20261121')
ROOT=ROOT8.with_name('fig8_r17_stage9_r9_20261122')
PLAN='docs/PLAN_20261121_FOLD_BANDWIDTH_R17.md'
COMMIT='1770e5d49b847263369e0518cb6ef718da3f0f32'
PREFIX='S9R17_'
ORD={'W5R':[4,5,6],'W6R':[1,2,3],'C1W6':[1],'W7R':[1,2,3],'C1W7':[1],'DC1':[1],'DC2':[1],'DC3':[1],'Ddense':[1]}
WIDTHS=('W5R','W6R','W7R')
M=stage8.margin(.813,.038);REQ=M['P_req_dB'];TARGET=[6.74,0.,REQ-.1]
T4={'Wm':2.8,'Ws':.630,'Lm':6.526,'Ls1':12.839,'Ls2':1.81,'Ls3':2.43}
W4=stage8.W4
W4RUNS={k:d for k,(d,_) in stage8.ANCHORS.items()}
W4RUNS.update(C2W=H8/'results/S8R16_C2W__T1',C3W=H8/'results/S8R16_C3W__T1')
def archive_hist(w):
    from manage import measurement
    v=read(w/'INPUT.json')['design']
    return dict(case=w.name,q=read(w/'review/extraction_R2.json'),tuning=v.get('tuning'),measurement=measurement(w))
def seed():return [archive_hist(H8/'results'/('S8R16_W5R__T'+str(i))) for i in (1,2,3)]
def check(q,req,s21):
    y=state(q);bw=q['bandwidths']['BW20'].get('BW_GHz')
    if y is None:return dict(tuned=False,error_e=None,reason='invalid shape')
    err=delivery_error(q,[6.74,0,req-.1])
    p=[i['S11_dB'] for i in q['shape']['inner_peaks']]
    passed=(6.73-1e-9<=y[0]<=6.76+1e-9 and abs(y[1])<=.2+1e-9 and min(p)>=req-.2-1e-9 and max(p)<=req+1e-9 and bw is not None and s21 is not None and s21>=-2)
    return dict(tuned=bool(passed),error_e=err,center_GHz=y[0],D_dB=y[1],mean_dB=y[2],S21_min_dB=s21,BW20_GHz=bw)
def build(g,n,kind='EQ',e=0.,er=3.55,h=.813,**kw):
    r=stage8.build({k:round(float(v),3) for k,v in g.items()},n,kind,e,er,h,**kw);r['id']=PREFIX+n
    r['dense_confirmation']=n=='Ddense'
    r['data_role']=('prospective_tuning_attempt_not_blind_test' if n in WIDTHS else 'prospective_edge_shift_transfer_test' if n in ('DC1','DC2','DC3','Ddense') else 'prespecified_joint_corner_after_tuning')
    return r
def width_t1(n,J,prev,qprevious=None,previous_prime=None):
    J=np.array(J,float);q=prev['q'];g=q['geometry_mm']
    def correct(q):return coordinate(q['geometry_mm'],'folded')+np.linalg.solve(J.T,np.array(TARGET)-state(q))
    p=correct(q);older=correct(qprevious) if previous_prime is None else np.array(previous_prime)
    x=2*p-older;ws=round(float(x[2]),3)
    # Compute continuous Ls1 first; round physical dimensions once; fixed a/g.
    xr=coordinate(g,'folded')
    gm=dict(Wm={'W6R':2.95,'W7R':3.10}[n],Ws=ws,Lm=round(float(x[0]),3),Ls1=round(float(g['Ls1']+x[1]-xr[1]-2*(x[2]-xr[2])),3),Ls2=round(2*ws+.55,3),Ls3=round(ws+1.8,3))
    return dict(previous_prime=p.tolist(),older_prime=older.tolist(),raw_extrapolated_x=x.tolist(),geometry_mm=gm,J_initial=J.tolist(),prediction_y=TARGET,source_case=prev['case'])
def edgevec(w):
    d=stage8.edge_from_run(w)
    if d is None:raise ValueError('main window unavailable')
    return np.array([d[k] for k in ('low_GHz','high_GHz')])
def selection(candidates):
    w4=edgevec(W4);delta={k:edgevec(W4RUNS[k])-w4 for k in ('C2W','C3W','dense')}
    out={}
    for name,(nm,corner,corref) in candidates.items():
        base=edgevec(nm);moves={'C1':edgevec(corner)-edgevec(corref),'C2':delta['C2W'],'C3':delta['C3W'],'dense':delta['dense']}
        ed={'nominal':base.tolist(),**{k:(base+v).tolist() for k,v in moves.items()}}
        lo=max(v[0] for v in ed.values());hi=min(v[1] for v in ed.values())
        out[name]=dict(nominal=nm.name,C1=corner.name,C1_reference=corref.name,edges_GHz=ed,band_GHz=[lo,hi],width_GHz=max(0.,hi-lo))
    winner=max(out,key=lambda n:out[n]['width_GHz'])
    return dict(selected=winner,candidates=out,rule='maximum estimated five-window intersection; ties prefer earlier verified width',selected_edges=out[winner]['edges_GHz'])
def corner_pass(m):return stage8.corner_test(m,False)
