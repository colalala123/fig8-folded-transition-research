"""R10 immutable preparation and finite proposals; no native application import."""
import argparse,copy,shutil
from common_stage2 import *
import cad_ir,offline_r10 as off
from tuning import *
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r12_stage6_r4_20261115')
OLD=REPO/'experiments/fold_bandwidth_r9_stage5_20261114'
OLDROOT=Path('F:/2026-1/circuit/test/output/fig8_r9_stage5_20261114')
INITIAL=[f'P{i}' for i in range(1,9)]+['P9c','P10','P11','P12','P13','P14','N0']
SEVEN=['P10','P9c','P11','P12','P13','P14','N0']
ORDER=INITIAL+['P1dense','P2dense','C1','B1R','B1Rdense','C1R','W3','W4']

def carry_totals(geometries,requests):
    expected={f'S6R10_P{i}__T1' for i in range(1,9)}
    if len(geometries)!=8 or {r['logical_case'] for r in geometries}!=expected:raise RuntimeError('prior logical geometry identities mismatch')
    if len(requests)!=87 or {r['logical_case'] for r in requests}!=expected:raise RuntimeError('prior request identities/cost mismatch')
    if any(sum(r['logical_case']==c for r in requests)>14 for c in expected):raise RuntimeError('prior per-geometry cap violated')
    return 181,1720,19

def decorate(d,kind='CONTROL',dense=False):
    d=copy.deepcopy(d);g=d['geometry_mm']
    old=d.get('cad_ir')
    base=old['base_geometry_mm'] if old else d.get('base_geometry_mm',g)
    ir=cad_ir.json_value(cad_ir.build(base,old['etch_e_mm'] if old else 0.,old['er'] if old else 3.55,old['h_mm'] if old else .813,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'))
    if any(abs(g[k]-ir['geometry_mm'][k])>1e-8 for k in g):raise RuntimeError('rebuild changed physical six dimensions')
    d['geometry_mm']=ir['geometry_mm']
    d.update(cad_ir=ir,topology='folded',material_role='archived_lossy',board_half_x_mm=15.,kind=kind,
        family='B1' if d['design'] in INITIAL+['P1dense','P2dense','C1','B1R','B1Rdense','C1R'] else d['design'],dense_confirmation=dense)
    d.setdefault('tuning',None)
    return d

def histories(root,p,cfg):
    out=off.histories('S5R9_W3') if p=='S6R10_W3' else [dict(case='S5R9_B1__T2',q=read(OLD/'results/S5R9_B1__T2/review/extraction_R2.json'),tuning=None)] if p=='S6R10_B1R' else []
    for c,s in cfg['case_specs'].items():
        if s['parent_id']!=p:continue
        w=case_dir(root,c,cfg);a=w/'review/visual_ack.json'
        if a.exists():
            ack=read(a)
            if not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png') or ack['extraction_sha256']!=sha(w/'review/extraction_R2.json'):raise RuntimeError('real-view ACK mismatch')
            out.append(dict(case=c,q=read(w/'review/extraction_R2.json'),tuning=read(w/'input/freeze.json')['design'].get('tuning')))
    return out

def spec(root,p,cfg):
    if p in cfg.get('cancelled_parents',[]):raise RuntimeError('R12 explicitly cancelled parent')
    if p in cfg['designs']:return decorate(cfg['designs'][p],cfg['designs'][p].get('kind','CONTROL'),cfg['designs'][p].get('dense_confirmation',False))
    n=p.removeprefix('S6R10_')
    if n in ('P1dense','P2dense'):
        gate=read(root/'decisions/6A_PRIMARY.json')
        if not gate['conditional_dense_required']:raise RuntimeError('dense P1/P2 not needed')
        d=copy.deepcopy(cfg['designs']['S6R10_'+n[:2]])
        d.update(id=p,design=n,data_role='same_perturbation_dense_mesh_control')
        return decorate(d,dense=True)
    if n in ('C1','B1R'):return decorate(read(HERE/'freeze_6B/R10_2.json')['designs'][p],'EQ' if n=='B1R' else 'CONTROL')
    if n in ('B1Rdense','C1R'):
        d=read(root/'decisions/S6R10_B1R_FINAL.json')
        if not d['passed']:raise RuntimeError('B1R not tuned')
        original=read(case_dir(root,d['selected_case'],cfg)/'input/freeze.json')['design']
        s=copy.deepcopy(original);s.update(id=p,design=n,kind='CONTROL',tuning=None,data_role='B1R_dense_confirmation' if n.endswith('dense') else 'B1R_measured_worst_corner')
        if n=='C1R':
            gate=read(HERE/'freeze_6B/R10_2.json');changes=gate['corner_changes'];ir=cad_ir.json_value(cad_ir.build(original['geometry_mm'],**changes,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'))
            s.update(cad_ir=ir,base_geometry_mm=original['geometry_mm'],geometry_mm=ir['geometry_mm'],nominal_a_mm=chain.dimensions(ir['geometry_mm'])['a_mm'])
        return decorate(s,dense=n.endswith('dense'))
    raise RuntimeError('unknown design '+p)

def suggestion(root,p,cfg):
    s=spec(root,p,cfg);kwargs={}
    if p=='S6R10_B1R':kwargs['peak_window']=read(HERE/'freeze_6B/R10_2.json')['peak_window_dB']
    return propose_history(histories(root,p,cfg),s['nominal_a_mm'],'folded',target=s.get('target_y'),**kwargs)

def make_input(root,p,i,retry=False):
    cfg=read(root/'authorization.json')
    if p in cfg.get('inherited_closed_parents',[]):raise RuntimeError('closed P1-P8 cannot be reopened')
    s=spec(root,p,cfg);logical=p+f'__T{i}';c=logical+('__NR1' if retry else '');w=case_dir(root,c,cfg)
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists() or w.exists():raise RuntimeError('stopped/paused/existing input')
    pred=copy.deepcopy(s);previous=None
    if retry:
        ow=case_dir(root,logical,cfg);ev=read(ow/'NUMERICAL_FAILURE.json')
        if not (ow/'failure.txt').exists() or not ev['same_settings_retry_allowed']:raise RuntimeError('not a numerical retry')
        pred=copy.deepcopy(read(ow/'input/freeze.json')['design']);previous=sha(ow/'failure.txt')
    elif (p=='S6R10_B1R' and i>1) or (p=='S6R10_W4' and i>1):
        sg=suggestion(root,p,cfg)
        if not sg['needs_solve']:return sg
        pred.update(geometry_mm=sg['geometry_mm'],tuning=sg,screen=sg['screen'],prediction=dict(response_y=sg['predicted_y']),data_role='tuned_not_independent_test')
        pred['cad_ir']=cad_ir.json_value(cad_ir.build(sg['geometry_mm'],port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'))
        previous=sha(case_dir(root,p+f'__T{i-1}',cfg)/'review/extraction_R2.json')
    if not pred['screen']['can_submit']:return dict(needs_solve=False,reason='geometry_conflict_skip_no_replacement')
    from geometry_gate import check_ir
    check_ir(pred['cad_ir'])
    for n in ('input','native','evidence'):(w/n).mkdir(parents=True)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,logical_case=logical,numerical_retry=retry,design=pred,
        nominal_a_mm=pred['nominal_a_mm'],expected_boxes=pred['cad_ir']['expected_slot_boxes'],
        source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),
        resume=False,inherited_Analyze=0,previous_extraction_sha256=previous,solver_started=False)
    if p=='S6R10_P10' and i==1 and not retry:
        f['R11_same_geometry_recovery']=dict(original_failure_sha256=sha(Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_r2_20261115/runs/S6R10_P10/attempt_001/failure.txt')),original_Analyze=1,remaining_Analyze_cap=13)
    if False:
        old=Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_r1_20261115/runs/S6R10_P9/attempt_001')
        f['zero_Analyze_tool_recovery']=dict(original_input_sha256=sha(old/'input/freeze.json'),original_failure_sha256=sha(old/'failure.txt'),original_Analyze=0)
    for dest in (w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')):write(dest,f)
    return dict(needs_solve=True,case=c)

def prepare(root):
    from r12 import prepare_r4
    return prepare_r4(root)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','attempt','retry']);ap.add_argument('parent',nargs='?');ap.add_argument('ordinal',type=int,nargs='?');a=ap.parse_args()
    print(prepare(ROOT) if a.command=='prepare' else make_input(ROOT,a.parent,a.ordinal,a.command=='retry'))
