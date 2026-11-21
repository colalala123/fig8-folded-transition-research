"""R16 scientific policy; no native API. Frequencies GHz, lengths mm, amplitudes dB unless specified."""
import math,copy
import numpy as np
from common_stage2 import HERE,REPO,Path,read,sha
from tuning import state,coordinate,inverse,J0
from presubmit import presubmit
import cad_ir,chain
from geometry_gate import check_ir
H7=REPO/'experiments/fold_bandwidth_r15_stage7_r7_20261116'
ROOT7=Path('F:/2026-1/circuit/test/output/fig8_r15_stage7_r7_20261116')
PLAN='docs/PLAN_20261116_FOLD_BANDWIDTH_R16.md'
PREFIX='S8R16_'
SLOTS={'C2W':1,'C3W':1,'W5R':3,'C1W5':1,'W6R':3,'C1W6':1}
ORDER=list(SLOTS)
W4=H7/'results/S7R15_W4R__T2'
ANCHORS={'W4R':(W4,[3.311,9.651]),'dense':(H7/'results/S7R15_W4Rdense__T1',[3.318,9.672]),'C1W':(H7/'results/S7R15_C1W__T1',[3.247,9.863])}
def margin(h0=.813,tol=.038):
    if not math.isfinite(h0) or not math.isfinite(tol) or not 0<tol<h0:raise ValueError('invalid h')
    corner=.023270-.020355+.020355*tol/.038
    req=.1-corner-.002336-.001070
    if not 0<req<.1:raise ValueError('invalid Gamma budget')
    return dict(h0_mm=h0,tol_h_mm=tol,delta_corner=corner,mesh_W4R=.002336,tune=.001070,Gamma_req=req,P_req_dB=20*math.log10(req))
def edges(f,s,v,threshold=-20.):
    f=np.asarray(f,float);s=np.asarray(s,float)
    if f.ndim!=1 or f.shape!=s.shape or len(f)<3 or not np.isfinite(f).all() or not np.isfinite(s).all() or not np.all(np.diff(f)>0):raise ValueError('invalid native trace')
    if v is None or not np.isfinite(v) or not f[0]<=v<=f[-1]:return None
    i=int(np.argmin(abs(f-v)))
    if abs(f[i]-v)>1e-7 or s[i]>threshold:return None
    l=r=i
    while l>0 and s[l-1]<=threshold:l-=1
    while r+1<len(s) and s[r+1]<=threshold:r+=1
    if l==0 or r+1==len(s):return None # no extrapolation from censored edges
    def crossing(j):return float(f[j]+(threshold-s[j])*(f[j+1]-f[j])/(s[j+1]-s[j]))
    lo,hi=crossing(l-1),crossing(r)
    return dict(low_GHz=lo,high_GHz=hi,width_GHz=hi-lo,rule='connected S11<=-20 component containing central valley; linear in dB, no envelope')
def edge_from_run(run):
    q=read(run/'review/extraction_R2.json')
    with np.load(run/'native/full_modes.npz',allow_pickle=False) as z:return edges(z['f_GHz'],20*np.log10(np.maximum(abs(z['S'][:,0,0]),1e-15)),q['shape'].get('central_valley_GHz'))
def replay():
    out={}
    for k,(d,ref) in ANCHORS.items():
        e=edge_from_run(d);err=[1000*(e[key]-v) for key,v in zip(('low_GHz','high_GHz'),ref)]
        if max(map(abs,err))>1:raise ValueError('R16 edge replay >1 MHz '+k)
        out[k]=dict(edges=e,plan_GHz=ref,error_MHz=err,native_sha256=sha(d/'native/full_modes.npz'))
    return out
def intersect(items):
    if len(items)!=5 or any(x is None for x in items):return None
    lo=max(x['low_GHz'] for x in items);hi=min(x['high_GHz'] for x in items)
    return dict(low_GHz=lo if hi>=lo else None,high_GHz=hi if hi>=lo else None,width_GHz=max(0.,hi-lo),empty=hi<lo,scope='intersection_of_five_simulated_main_windows_only')
def corners(n,m):
    key={'C2W':(-.01,3.60,1),'C3W':(-.01,3.50,1),'C1W5':(.01,3.50,-1),'C1W6':(.01,3.50,-1)}
    e,er,k=key[n];return dict(e=e,er=er,h=round(m['h0_mm']+k*m['tol_h_mm'],9))
def check(q,req,s21):
    y=state(q);bw=q['bandwidths']['BW20'].get('BW_GHz')
    if y is None:return dict(tuned=False,error_e=None,reason='not three valleys/two inner peaks')
    mid=req-.1;peaks=[p['S11_dB'] for p in q['shape']['inner_peaks']]
    err=max(abs(float(y[0])-6.74)/.01,abs(float(y[1]))/.2,max(abs(x-mid) for x in peaks)/.1)
    return dict(tuned=bool(err<=1+1e-9 and bw is not None and s21 is not None and s21>=-2.),error_e=err,center_GHz=y[0],peak_window_dB=[req-.2,req],mean_dB=y[2],D_dB=y[1],S21_min_dB=s21,BW20_GHz=bw)
def build(g,n,kind='EQ',e=0.,er=3.55,h=.813,**extra):
    ir=cad_ir.json_value(cad_ir.build(g,e,er,h,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'));a=chain.dimensions(ir['geometry_mm'])['a_mm']
    screen=presubmit(ir['geometry_mm'],a,tuning_changed=False,topology='folded');check_ir(ir)
    return dict(id=PREFIX+n,design=n,geometry_mm=ir['geometry_mm'],base_geometry_mm=g,cad_ir=ir,nominal_a_mm=a,g_mm=.55,topology='folded',material_role='archived_lossy',board_half_x_mm=15.,kind=kind,family=n,dense_confirmation=False,tuning=None,screen=screen,data_role='prospective_tuning_not_independent_blind_test' if kind=='EQ' else 'prespecified_joint_corner_control',**extra)
def t1(n,m):
    step={'W5R':1,'W6R':2}[n];q=read(W4/'review/extraction_R2.json');g=q['geometry_mm']
    ref={**g,'Wm':round(g['Wm']+.15*step,3),'Ws':round(g['Ws']+.069*step,3),'Lm':round(g['Lm']-.029*step,3),'Ls1':round(g['Ls1']+.100*step,3)}
    ref.update(Ls2=round(2*ref['Ws']+.55,3),Ls3=round(ref['Ws']+1.8,3))
    base=state(q);target=np.array([6.74,0.,m['P_req_dB']-.1])
    # The nominal-width secant carries the state, not a fictitious W5/W6 measurement.
    dx=np.linalg.solve(J0.T,target-base);x=coordinate(ref,'folded')
    new=inverse(ref,x+dx,'folded',1.8,.55);new={k:round(v,3) for k,v in new.items()}
    predicted=base+(coordinate(new,'folded')-x)@J0
    proof=dict(reference_geometry_mm=ref,basis='measured W4R T2 + R16 width secant per 0.15mm; transfer B1 measured physical J in [Lm,Lc,Ws] coordinates for ripple correction',reference_state_assumed=base.tolist(),target_y=target.tolist(),J=J0.tolist(),step_dx=dx.tolist(),prediction_y=predicted.tolist(),geometry_mm=new,deviation_from_reference_mm={k:new[k]-ref[k] for k in ('Ws','Lm','Ls1')},explanation='Three-variable inverse corrects both peaks and center, not just slot width. This is an extrapolation, not an independent W5R/W6R Jacobian.')
    return build(new,n,target_y=target.tolist(),prediction=dict(response_y=predicted.tolist(),method=proof['basis'])),proof
def permission(n,decisions):
    if n=='C1W5':
        if not decisions['W5R'].get('selected_case'):return False,'no numerical nominal W5R candidate available'
    if n=='W6R' and decisions['W5R'].get('passed') is not True:return False,'W5R not tuned'
    if n=='C1W6':
        if decisions['W6R'].get('passed') is not True:return False,'W6R not tuned'
        a,b=[decisions[k]['measurement']['BW20_GHz'] for k in ('W5R','W6R')]
        if b-a<.05-1e-12:return False,'gain below 50 MHz'
    return True,'eligible'
def corner_test(m,own):
    if not m or not m.get('shape_valid'):return None
    g=10**(max(m['low_peak_dB'],m['high_peak_dB'])/20);bias=.002336
    return dict(Gamma_corner=g,mesh_bias=bias,mesh_source='own_W4R' if own else 'borrowed_W4R_no_own_dense',adjusted=g+bias,margin=.1-g-bias,passed=g+bias<=.1)
