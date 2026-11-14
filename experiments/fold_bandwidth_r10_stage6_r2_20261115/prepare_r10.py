"""R10 immutable preparation and finite proposals; no native application import."""
import argparse,copy,shutil
from common_stage2 import *
import cad_ir,offline_r10 as off
from tuning import *
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_r2_20261115')
OLD=REPO/'experiments/fold_bandwidth_r9_stage5_20261114'
OLDROOT=Path('F:/2026-1/circuit/test/output/fig8_r9_stage5_20261114')
INITIAL=[f'P{i}' for i in range(1,15)]+['N0']
ORDER=INITIAL+['P1dense','P2dense','C1','B1R','B1Rdense','C1R','W3','W4']

def carry_totals(geometries,requests):
    expected={f'S6R10_P{i}__T1' for i in range(1,9)}
    if len(geometries)!=8 or {r['logical_case'] for r in geometries}!=expected:raise RuntimeError('prior logical geometry identities mismatch')
    if len(requests)!=87 or {r['logical_case'] for r in requests}!=expected:raise RuntimeError('prior request identities/cost mismatch')
    if any(sum(r['logical_case']==c for r in requests)>14 for c in expected):raise RuntimeError('prior per-geometry cap violated')
    return 181,1720,19

def decorate(d,kind='CONTROL',dense=False):
    d=copy.deepcopy(d);g=d['geometry_mm']
    ir=d.get('cad_ir') or cad_ir.build(g,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed')
    d.update(cad_ir=ir,topology='folded',material_role='archived_lossy',board_half_x_mm=15.,kind=kind,
        family='B1' if d['design'] in INITIAL+['P1dense','P2dense','C1','B1R','B1Rdense','C1R'] else d['design'],dense_confirmation=dense)
    d.setdefault('tuning',None)
    return d

def histories(root,p,cfg):
    out=off.histories('S5R9_W3') if p=='S6R10_W3' else []
    for c,s in cfg['case_specs'].items():
        if s['parent_id']!=p:continue
        w=case_dir(root,c,cfg);a=w/'review/visual_ack.json'
        if a.exists():
            ack=read(a)
            if not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png') or ack['extraction_sha256']!=sha(w/'review/extraction_R2.json'):raise RuntimeError('real-view ACK mismatch')
            out.append(dict(case=c,q=read(w/'review/extraction_R2.json'),tuning=read(w/'input/freeze.json')['design'].get('tuning')))
    return out

def spec(root,p,cfg):
    if p in cfg['designs']:return cfg['designs'][p]
    n=p.removeprefix('S6R10_')
    if n in ('P1dense','P2dense'):
        gate=read(root/'decisions/6A_PRIMARY.json')
        if not gate['conditional_dense_required']:raise RuntimeError('dense P1/P2 not needed')
        d=copy.deepcopy(cfg['designs']['S6R10_'+n[:2]])
        d.update(id=p,design=n,data_role='same_perturbation_dense_mesh_control')
        return decorate(d,dense=True)
    if n in ('C1','B1R'):return read(HERE/'freeze_6B/R10_2.json')['designs'][p]
    if n in ('B1Rdense','C1R'):
        d=read(root/'decisions/S6R10_B1R_FINAL.json')
        if not d['passed']:raise RuntimeError('B1R not tuned')
        original=read(case_dir(root,d['selected_case'],cfg)/'input/freeze.json')['design']
        s=copy.deepcopy(original);s.update(id=p,design=n,kind='CONTROL',tuning=None,data_role='B1R_dense_confirmation' if n.endswith('dense') else 'B1R_measured_worst_corner')
        if n=='C1R':
            gate=read(HERE/'freeze_6B/R10_2.json');changes=gate['corner_changes'];ir=cad_ir.build(original['geometry_mm'],**changes,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed')
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
        pred['cad_ir']=cad_ir.build(sg['geometry_mm'],port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed')
        previous=sha(case_dir(root,p+f'__T{i-1}',cfg)/'review/extraction_R2.json')
    if not pred['screen']['can_submit']:return dict(needs_solve=False,reason='geometry_conflict_skip_no_replacement')
    for n in ('input','native','evidence'):(w/n).mkdir(parents=True)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,logical_case=logical,numerical_retry=retry,design=pred,
        nominal_a_mm=pred['nominal_a_mm'],expected_boxes=pred['cad_ir']['expected_slot_boxes'],
        source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),
        resume=False,inherited_Analyze=0,previous_extraction_sha256=previous,solver_started=False)
    if p=='S6R10_P9' and i==1 and not retry:
        old=Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_r1_20261115/runs/S6R10_P9/attempt_001')
        f['zero_Analyze_tool_recovery']=dict(original_input_sha256=sha(old/'input/freeze.json'),original_failure_sha256=sha(old/'failure.txt'),original_Analyze=0)
    for dest in (w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')):write(dest,f)
    return dict(needs_solve=True,case=c)

def prepare(root):
    import psutil
    prior_h=REPO/'experiments/fold_bandwidth_r10_stage6_r1_20261115'
    prior_r=Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_r1_20261115')
    if root.exists():raise RuntimeError('new runtime exists; never reset')
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native resource occupied')
    closure=read(prior_h/'TECHNICAL_CLOSURE.json')
    if (closure['closed_geometry'],closure['closed_actual_Analyze'],closure['failed_case_Analyze'])!=(8,87,0):raise RuntimeError('prior cost mismatch')
    if not (prior_r/'STOP.json').exists() or (prior_r/'PAUSE.json').exists():raise RuntimeError('original STOP required; user pause forbids continuation')
    if len(list((prior_r/'ledger').glob('geometry_*.json')))!=8 or len(list((prior_r/'ledger').glob('Analyze_*.json')))!=87:raise RuntimeError('prior ledgers changed')
    carry_totals([read(p) for p in (prior_r/'ledger').glob('geometry_*.json')],[read(p) for p in (prior_r/'ledger').glob('Analyze_*.json')])
    if read(prior_r/'STOP.json')['case']!='S6R10_P9__T1' or read(prior_r/'runs/S6R10_P9/attempt_001/RUN_RECORD.json')['Analyze_requested']!=0:raise RuntimeError('not the bounded zero-Analyze P9 tool event')
    preflight=Path('F:/2026-1/circuit/test/output/fig8_r10_preflight_P9_v2_20261115/PASS.json')
    pf=read(preflight)
    if not pf['passed'] or pf['new_Analyze']!=0 or not pf['cleanup']['released']:raise RuntimeError('native no-solve preflight missing')
    if pf['code_sha256']['native_control.py']!=sha(HERE/'native_control.py'):raise RuntimeError('tool code changed since actual preflight')
    h_preflight=Path('F:/2026-1/circuit/test/output/fig8_r10_preflight_P13_v2_20261115/PASS.json')
    hp=read(h_preflight)
    if not hp['passed'] or hp['new_Analyze']!=0 or not hp['cleanup']['released'] or hp['code_sha256']['native_control.py']!=sha(HERE/'native_control.py'):raise RuntimeError('height/port no-solve preflight not passed')
    er_preflight=Path('F:/2026-1/circuit/test/output/fig8_r10_preflight_P11_v2_20261115/PASS.json')
    ep=read(er_preflight)
    if not ep['passed'] or ep['new_Analyze']!=0 or not ep['cleanup']['released'] or ep['code_sha256']['native_control.py']!=sha(HERE/'native_control.py'):raise RuntimeError('dielectric preflight not passed')
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed']:raise RuntimeError('offline tests failed')
    (HERE/'pre_solve').mkdir()
    shutil.copyfile(prior_h/'freeze/R10_1.json',HERE/'freeze/R10_1.json')
    write(HERE/'freeze/TOOL_RECOVERY.json',dict(at=now(),source='R10 authorized same remaining points; local tool compatibility fix, no geometry/criteria/budget expansion',
        prior_geometry=8,prior_Analyze=87,prior_cumulative_geometry=181,prior_cumulative_Analyze=1720,remaining_geometry=19,total_geometry_cap=200,
        first_resumed_case='S6R10_P9__T1',source_freeze_commit='c564af8c7afdd04d383445687d4667df7e353a97',
        original_STOP_preserved=True,preflight=pf,preflight_sha256=sha(preflight),height_preflight=hp,height_preflight_sha256=sha(h_preflight),er_preflight=ep,er_preflight_sha256=sha(er_preflight),no_further_automatic_technical_revision=True))
    cfg=copy.deepcopy(read(prior_r/'authorization.json'))
    cfg.update(at=now(),execution_revision='R10_STAGE6_R2',prior_geometry_total=181,prior_Analyze_total=1720,batch_geometry_limit=19,
        total_geometry_limit=200,inherited_stage6_geometry=8,inherited_stage6_Analyze=87,full_stage6_geometry_limit=27,
        batch_max_Analyze_from_geometry_caps=284,full_stage6_max_Analyze_from_geometry_caps=396,
        inherited_closed_parents=['S6R10_'+f'P{i}' for i in range(1,9)],inherited_case_paths={},inherited_public_result_paths={},
        technical_recovery_policy='R1 STOP and all failures preserved; local BoundaryProps fix passed actual zero-Analyze CAD preflight; resume same frozen P9 onwards. Any further technical failure stops for report, no automatic R3.',
        continuation_basis='Original human R10 scope unchanged; local pre-Analyze tool repair under R4, no additional design/request allowance.')
    for c,sp in list(cfg['case_specs'].items()):
        if sp['parent_id'] in cfg['inherited_closed_parents']:
            if not sp['numerical_retry']:
                cfg['inherited_case_paths'][c]=str(prior_r/cfg['case_paths'][c])
                cfg['inherited_public_result_paths'][c]=(prior_h/'results'/c).relative_to(REPO).as_posix()
            del cfg['case_specs'][c];del cfg['case_paths'][c]
    for rel,h in read(prior_h/'CLOSURE_MANIFEST.json').items():cfg['historical_hashes'][str(prior_h/rel)]=h
    for p in list((prior_r/'ledger').glob('*.json'))+[prior_r/'STOP.json',prior_r/'authorization.json',prior_h/'CLOSURE_MANIFEST.json',preflight,h_preflight,er_preflight]:
        cfg['historical_hashes'][str(p)]=sha(p)
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline') for p in (HERE/folder).glob('*.json')})
    root.mkdir()
    for n in ('ledger','decisions','model_freeze','publications'):(root/n).mkdir()
    write(root/'authorization.json',cfg);shutil.copyfile(prior_r/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    for p in cfg['inherited_closed_parents']:shutil.copyfile(prior_r/'decisions'/(p+'_FINAL.json'),root/'decisions'/(p+'_FINAL.json'))
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:v for k,v in cfg.items() if k not in ('historical_hashes','prior_cases','prior_decisions','designs')})
    for n in INITIAL[8:]+['W3','W4']:print(make_input(root,'S6R10_'+n,4 if n=='W3' else 1))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','attempt','retry']);ap.add_argument('parent',nargs='?');ap.add_argument('ordinal',type=int,nargs='?');a=ap.parse_args()
    print(prepare(ROOT) if a.command=='prepare' else make_input(ROOT,a.parent,a.ordinal,a.command=='retry'))
