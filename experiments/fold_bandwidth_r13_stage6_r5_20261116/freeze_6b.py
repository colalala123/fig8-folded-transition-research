"""R10-2 measured margin freeze before C1. Pure offline, exclusive writes."""
import argparse,subprocess,hashlib
from manage import *

def prepare(root):
    raise RuntimeError('R12 margin and B1R T1 are frozen by r12.offline before R4 publication; old C1 preparation is cancelled')
    cfg=read(root/'authorization.json');a=analyze6a(root);b=next(r for r in read(OLD/'final/SELECTED.json') if r['parent']=='S5R9_B1');changes={}
    initial={x['design']:x for x in cfg['designs'].values()}
    changes['e']=initial[a['C1_worst_sides']['etch']]['cad_ir']['etch_e_mm']
    changes['er']=initial[a['C1_worst_sides']['er']]['cad_ir']['er']
    changes['h']=initial[a['C1_worst_sides']['h']]['cad_ir']['h_mm']
    ir=cad_ir.build(b['geometry_mm'],**changes,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed')
    c=dict(id='S6R10_C1',design='C1',geometry_mm=ir['geometry_mm'],base_geometry_mm=b['geometry_mm'],cad_ir=ir,
        nominal_a_mm=chain.dimensions(ir['geometry_mm'])['a_mm'],data_role='measured_realistic_joint_corner_no_tuning',
        prediction=dict(status='无联合角点J预测，逐侧直测RSS只是余量规则'),screen=presubmit(ir['geometry_mm'],chain.dimensions(ir['geometry_mm'])['a_mm'],tuning_changed=False))
    designs={'S6R10_C1':decorate(c)};req=a['P_req_dB']
    if a['stage6B_decision']=='try_B1R_max_three':
        m=read(HERE/'freeze/R10_1.json')['parameter_model'];br=off.candidate(m,2.35,1.8,.55,target=[6.72,0.,req-.1],name='B1R')
        br['prediction']['limitation']='T1 uses frozen refit and J to shift mean target; measured side tolerances, not J, determine M.'
        designs['S6R10_B1R']=decorate(br,'EQ')
    out=dict(at=now(),analysis=a,corner_changes=changes,designs=designs,peak_window_dB=[req-.2,req],
        source_decision_hashes={p.name:sha(p) for p in (root/'decisions').glob('*_FINAL.json')},
        own_dense_bias_policy='max(0, dense-low minus nominal-low, dense-high minus nominal-high)',
        stage7_authorized=False)
    (HERE/'freeze_6B').mkdir();write(HERE/'freeze_6B/R10_2.json',out)
    print(make_input(root,'S6R10_C1',1))
    if 'S6R10_B1R' in designs:print(make_input(root,'S6R10_B1R',1))
    return out

def publish(root):
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip();remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/fold-bandwidth-r4-execution'],cwd=REPO,text=True).split()[0]
    if commit!=remote:raise RuntimeError('R10-2 not pushed')
    hashes={(HERE/'freeze_6B/R10_2.json').relative_to(REPO).as_posix():sha(HERE/'freeze_6B/R10_2.json')}
    for rel,h in hashes.items():
        if hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=REPO)).hexdigest()!=h:raise RuntimeError('R10-2 published blob mismatch')
    d=dict(at=now(),commit=commit,remote_verified=True,hashes=hashes);write(root/'R10_2_PUBLICATION.json',d);return d

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','publish']);a=ap.parse_args();print(globals()[a.command](ROOT))
