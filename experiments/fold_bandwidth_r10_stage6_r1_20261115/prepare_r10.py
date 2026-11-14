"""R10 immutable preparation and finite proposals; no native application import."""
import argparse,copy,shutil
from common_stage2 import *
import cad_ir,offline_r10 as off
from tuning import *
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_r1_20261115')
OLD=REPO/'experiments/fold_bandwidth_r9_stage5_20261114'
OLDROOT=Path('F:/2026-1/circuit/test/output/fig8_r9_stage5_20261114')
INITIAL=[f'P{i}' for i in range(1,15)]+['N0']
ORDER=INITIAL+['P1dense','P2dense','C1','B1R','B1Rdense','C1R','W3','W4']

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
    cfg=read(root/'authorization.json');s=spec(root,p,cfg);logical=p+f'__T{i}';c=logical+('__NR1' if retry else '');w=case_dir(root,c,cfg)
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
    for dest in (w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')):write(dest,f)
    return dict(needs_solve=True,case=c)

def prepare(root):
    import psutil
    if root.exists():raise RuntimeError('runtime already exists')
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native active')
    d=off.generate('clip_cut_faces','height_8h_width_fixed')
    d.pop('authorizes_solver',None)
    d.update(status='R10_1_FORMAL_FREEZE',authorizes_solver_only_after_tests_and_pushed_publication=True)
    d['policies'].update(human_confirmation_received=True,human_answers=['采用，保持端口截断面不动（推荐）','采用：高度8h，横向宽不变（推荐）'])
    if (read(OLD/'COMPLETE_STAGE5.json')['total_geometry'],read(OLD/'COMPLETE_STAGE5.json')['total_actual_Analyze'])!=(173,1633):raise RuntimeError('prior totals mismatch')
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed']:raise RuntimeError('offline release tests not passed')
    (HERE/'freeze').mkdir(exist_ok=True);(HERE/'pre_solve').mkdir()
    write(HERE/'freeze/R10_1.json',d)
    cfg=copy.deepcopy(read(OLDROOT/'authorization.json'))
    cfg.update(at=now(),execution_revision='R10_STAGE6',batch='6',prior_geometry_total=173,prior_Analyze_total=1633,
        batch_geometry_limit=27,total_geometry_limit=200,parent_order=['S6R10_'+p for p in ORDER],designs={},case_paths={},case_specs={},
        dense_per_geometry_Analyze_limit=20,batch_max_Analyze_from_geometry_caps=396,
        user_authorization='用户明确同意R10第0节；补充明确确认蚀刻固定端口截断面，高度8h且横宽15.04mm。6A→R10-2→6B→6C后停止，不进7。',
        plan_commit='4be2f26d56a7fb52da271a6392a0069b2a7ef79a',
        technical_recovery_policy='技术失败停止；6A数值失败可同参数独立重试一次，原始事件和缓存保持；每物理几何两次尝试合计不超14/20Analyze；不足则缺失，不扩额度。')
    cfg.pop('R9_cumulative_geometry_cap',None)
    for c in d['stage6A']:cfg['designs'][c['id']]=decorate(c)
    cfg['designs']['S6R10_W3']=decorate(d['W3_T4'],'EQ');cfg['designs']['S6R10_W4']=decorate(d['W4_T1'],'EQ')
    for p in cfg['parent_order']:
        indices=[4] if p.endswith('_W3') else [1,2,3] if p.endswith(('_W4','_B1R')) else [1]
        for i in indices:
            c=p+f'__T{i}';cfg['case_paths'][c]=f'runs/{p}/attempt_{i:03d}';cfg['case_specs'][c]=dict(parent_id=p,attempt_ordinal=i,numerical_retry=False)
            if p.removeprefix('S6R10_') in INITIAL+['P1dense','P2dense']:
                cfg['case_paths'][c+'__NR1']=f'runs/{p}/attempt_{i:03d}_numerical_retry_1';cfg['case_specs'][c+'__NR1']=dict(parent_id=p,attempt_ordinal=i,numerical_retry=True)
    cfg['plan_hashes']['docs/PLAN_20261110_FOLD_BANDWIDTH_R10.md']=sha(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R10.md')
    for p in (OLDROOT/'STOP.json',OLDROOT/'authorization.json',OLD/'FINAL_MANIFEST.json'):cfg['historical_hashes'][str(p)]=sha(p)
    for p in (OLDROOT/'ledger').glob('*.json'):cfg['historical_hashes'][str(p)]=sha(p)
    cfg['frozen_hashes'].update(d['source_sha256'])
    cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline') for p in (HERE/folder).glob('*.json')})
    for rel,h in read(OLD/'FINAL_MANIFEST.json')['files'].items():cfg['historical_hashes'][str(OLD/rel)]=h
    for previous in (REPO/'experiments/fold_bandwidth_r10_stage6_20261114/PRELAUNCH_CLOSED.json',Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_20261114/STOP.json'),Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_20261114/authorization.json')):
        cfg['historical_hashes'][str(previous)]=sha(previous)
    cfg['supersedes_zero_dispatch_revision']='fa8f784ddec92a50844b79b82c1d5d471125fc9a'
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    root.mkdir(parents=True)
    for n in ('ledger','decisions','model_freeze','publications'):(root/n).mkdir()
    write(root/'authorization.json',cfg);shutil.copyfile(OLDROOT/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:v for k,v in cfg.items() if k not in ('historical_hashes','prior_cases','prior_decisions','designs')})
    for p in INITIAL+['W3','W4']:print(make_input(root,'S6R10_'+p,4 if p=='W3' else 1))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','attempt','retry']);ap.add_argument('parent',nargs='?');ap.add_argument('ordinal',type=int,nargs='?');a=ap.parse_args()
    print(prepare(ROOT) if a.command=='prepare' else make_input(ROOT,a.parent,a.ordinal,a.command=='retry'))
