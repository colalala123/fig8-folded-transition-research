"""R7独立目录冻结、后继候选和条件对照；无求解。"""
import copy,json,argparse,sys,shutil
from common_stage2 import *
from tuning import *
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r7_3r_20261113')
OLDROOT=Path('F:/2026-1/circuit/test/output/fig8_r6_stage3_corrected_20261113')
ORDER=[('N04',.6,2,'S3R3_EQ_N04_01__T3'),('N14',1.,3,'S2_E1_N14_a1.0__T1'),
 ('N14',.6,3,'S2_E1_N14_a0.6__T2'),('N04',2.2,3,'S2_E1_N04_a2.2__T2'),
 ('N14',0.,3,'S2_E0_N14__T3'),('N04',0.,3,'S3R3_EQ_N04_00__T3'),
 ('N14',2.6,3,'S2_E1_N14_a2.6__T3'),('N04',2.6,3,'S2_E1_N04_a2.6__T3')]
EXISTING=[('N04',1.,'S2_E1_N04_a1.0__T1'),('N04',1.8,'S1_BASE_N04'),('N14',1.8,'S1_WS_01'),('N14',2.2,'S2_E1_N14_a2.2__T2')]
def parent(f,a):return f'S3R7_{f}_a{a:.1f}'
def source(case):
    if case=='S1_BASE_N04':
        d=REPO/'experiments/fold_bandwidth_r4_20261110/r5_cache_results/S1_BASE_N04'
        return d/'extraction_R2.json',d/'full_modes.npz'
    dirs=['fold_bandwidth_r6_stage3_corrected_20261113','fold_bandwidth_r6_stage3_20261112','fold_bandwidth_r6_stage2_20261111','fold_bandwidth_r6_stage2b_20261112','fold_bandwidth_r6_20261111']
    for folder in dirs:
        d=REPO/'experiments'/folder/'results'/case
        if(d/'review/extraction_R2.json').exists():return d/'review/extraction_R2.json',d/'native/full_modes.npz'
    raise RuntimeError('missing source '+case)
def base_history(spec):return [dict(case=spec['seed'],q=read(source(spec['seed'])[0]))]
def histories(root,p,cfg):
    spec=cfg['designs'][p];hh=base_history(spec)
    for i in range(1,spec['max_Analyze']+1):
        case=p+f'__T{i}';w=case_dir(root,case,cfg)
        if (w/'review/visual_ack.json').exists():
            ack=read(w/'review/visual_ack.json')
            if not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png'):raise RuntimeError('ACK invalid')
            hh.append(dict(case=case,q=read(w/'review/extraction_R2.json'),tuning=read(w/'input/freeze.json')['design']['tuning']))
    return hh
def prepare(root):
    import psutil
    if root.exists():raise RuntimeError('runtime exists')
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native active')
    audit=read(REPO/'experiments/fold_bandwidth_r6_stage3_corrected_20261113/stop_review/INDEPENDENT_AUDIT.json')
    if not audit['passed'] or (audit['cumulative_geometry'],audit['cumulative_actual_Analyze'],audit['stage3_geometry'])!=(106,961,6):raise RuntimeError('cost audit mismatch')
    cfg=copy.deepcopy(read(OLDROOT/'authorization.json'))
    cfg.update(execution_revision='R7_3R',prior_geometry_total=106,prior_Analyze_total=961,stage3_prior_geometry=6,stage3_prior_Analyze=57,
      prior_parent_geometry={},batch_geometry_limit=36,case_paths={},case_specs={},designs={},parent_order=[],
      user_authorization='用户明确同意R7第0节：8新设计23槽+10无耗+2边界；3R结束停，不进4。',
      R7_new_geometry_cap=35,prior_stage3_audit=str(REPO/'experiments/fold_bandwidth_r6_stage3_corrected_20261113/stop_review/INDEPENDENT_AUDIT.json'))
    cfg['plan_hashes']['docs/PLAN_20261110_FOLD_BANDWIDTH_R7.md']=sha(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R7.md')
    cfg['historical_hashes'][str(OLDROOT/'STOP.json')]=sha(OLDROOT/'STOP.json')
    auditpath=REPO/'experiments/fold_bandwidth_r6_stage3_corrected_20261113/stop_review/INDEPENDENT_AUDIT.json'
    cfg['historical_hashes'][str(auditpath)]=sha(auditpath)
    for lp in (OLDROOT/'ledger').glob('*.json'):cfg['historical_hashes'][str(lp)]=sha(lp)
    reg=[]
    for family,a,cap,seed in ORDER:
        p=parent(family,a);top='folded' if a else 'straight_control';q=read(source(seed)[0]);sug=propose_history([dict(case=seed,q=q)],a,top)
        if not sug['needs_solve']:raise RuntimeError('no initial candidate '+p)
        r=dict(id=p,kind='EQ',family=family,nominal_a_mm=a,topology=top,max_Analyze=cap,seed=seed,
          material_role='archived_lossy',data_role='prospective_tuning_attempt_not_blind_test',
          geometry_mm=sug['geometry_mm'],tuning=sug,prediction=new_prediction(sug['geometry_mm'],top),screen=sug['screen'])
        cfg['designs'][p]=r;cfg['parent_order'].append(p)
        qp,npz=source(seed)
        for sp in (qp,npz):cfg['historical_hashes'][str(sp)]=sha(sp)
        reg.append(dict(**r,seed_extraction_sha256=sha(qp),expected_boxes=geometry.slot_boxes(r['geometry_mm'],top)))
    existing=[]
    for fam,a,seed in EXISTING:
        qp,npz=source(seed);q=read(qp)
        if not classify(q)['tuned']:raise RuntimeError('existing not usable '+seed)
        existing.append(dict(family=fam,a=a,seed=seed,classification=classify(q),extraction_sha256=sha(qp)))
        for sp in (qp,npz):cfg['historical_hashes'][str(sp)]=sha(sp)
    for fam in ('N04','N14'):
        for a in (0.,.6,1.8,2.2,2.6):
            p=parent(fam,a)+'_LL';cfg['parent_order'].append(p)
            cfg['designs'][p]=dict(id=p,kind='LOSSLESS',family=fam,nominal_a_mm=a,topology='folded' if a else 'straight_control',
                parent=parent(fam,a),max_Analyze=1,material_role='lossless_control',data_role='lossless_control')
    for a in (0.,1.8):
        p=parent('N14',a)+'_WIDE';cfg['parent_order'].append(p)
        cfg['designs'][p]=dict(id=p,kind='BOUNDARY',family='N14',nominal_a_mm=a,topology='folded' if a else 'straight_control',
            parent=parent('N14',a),max_Analyze=1,material_role='archived_lossy',board_half_x_mm=20.,data_role='boundary_control')
    assert sum(r['max_Analyze'] for r in cfg['designs'].values())==35
    for p,r in cfg['designs'].items():
        for i in range(1,r['max_Analyze']+1):
            c=p+f'__T{i}';prefix='uniform_control' if r['topology']=='straight_control' else 'runs'
            cfg['case_paths'][c]=f'{prefix}/{p}/attempt_{i:03d}';cfg['case_specs'][c]=dict(parent_id=p,attempt_ordinal=i)
    (HERE/'freeze').mkdir()
    (HERE/'pre_solve').mkdir()
    plan=(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R7.md').read_text(encoding='utf-8')
    write(HERE/'freeze/REGISTRY.json',dict(designs=reg,existing=existing,slopes=dict(s15=.125,s15_range=[.110,.140],sref=.19,sref_range=[.17,.21]),
       predictions_verbatim=plan.split('### 2.4')[1].split('## 3.')[0],old_R3_registry='superseded_by_R7_preserved_not_scheduled',stage4_enabled=False))
    write(HERE/'freeze/BUDGET.json',dict(prior_geometry=106,prior_Analyze=961,prior_stage3_geometry=6,new_design_slots=23,lossless_slots=10,boundary_slots=2,new_cap=35,stage3_max=41,stage3_hard_cap=42,total_hard_cap=187))
    cfg['frozen_hashes']={p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline') for p in sorted((HERE/folder).glob('*.json'))}
    cfg['code_hashes']={**cfg['code_hashes'],**{p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')}}
    root.mkdir(parents=True)
    for name in ('ledger','decisions','model_freeze'):(root/name).mkdir()
    write(root/'authorization.json',cfg)
    shutil.copyfile(OLDROOT/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:v for k,v in cfg.items() if k not in ('historical_hashes','prior_cases','prior_decisions')})
    for p in cfg['parent_order'][:8]:attempt(root,p,1)
    print('PREPARED_R7',len(reg),'FIRST_GEOMETRIES',root)

def selection(root,p,cfg):
    dp=root/'decisions'/(p+'_FINAL.json')
    if dp.exists():
        d=read(dp)
        if not d['tuned']:return None
        case=d['selected_case'];w=case_dir(root,case,cfg)
        return case,read(w/'review/extraction_R2.json')['geometry_mm'],w/'native/full_modes.npz'
    for e in read(HERE/'freeze/REGISTRY.json')['existing']:
        if p==parent(e['family'],e['a']):
            qp,npz=source(e['seed']);return e['seed'],read(qp)['geometry_mm'],npz
    return None

def attempt(root,p,i):
    cfg=read(root/'authorization.json');initial=cfg['designs'][p];case=p+f'__T{i}'
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists():raise RuntimeError('stop/pause')
    w=case_dir(root,case,cfg)
    if w.exists():raise RuntimeError('refuse overwrite')
    pred=copy.deepcopy(initial);previous=None
    if pred['kind']=='EQ':
        hh=histories(root,p,cfg);sug=propose_history(hh,pred['nominal_a_mm'],pred['topology'])
        if not sug['needs_solve']:return sug
        pred.update(geometry_mm=sug['geometry_mm'],tuning=sug,screen=sug['screen'],prediction=new_prediction(sug['geometry_mm'],pred['topology']))
        previous=sha(source(pred['seed'])[0]) if i==1 else sha(case_dir(root,p+f'__T{i-1}',cfg)/'review/extraction_R2.json')
    else:
        sel=selection(root,pred['parent'],cfg)
        if sel is None:return dict(needs_solve=False,reason='parent_not_usable')
        selected,g,npz=sel;pred.update(geometry_mm=g,prediction=new_prediction(g,pred['topology']),screen=presubmit(g,pred['nominal_a_mm'],topology=pred['topology']))
        pred['binding']=dict(selected_case=selected,native_source=str(npz),native_sha256=sha(npz))
    for sub in ('input','native','evidence'):(w/sub).mkdir(parents=True)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,design=pred,nominal_a_mm=pred['nominal_a_mm'],expected_boxes=geometry.slot_boxes(pred['geometry_mm'],pred['topology']),
        source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,
        previous_extraction_sha256=previous,solver_started=False)
    write(w/'input/freeze.json',f);write(root/'model_freeze'/(case+'.json'),f)
    write(HERE/'pre_solve'/(case+'.json'),f)
    return dict(needs_solve=True,case=case)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','attempt']);p.add_argument('parent',nargs='?');p.add_argument('i',nargs='?',type=int);a=p.parse_args()
    print(prepare(ROOT) if a.command=='prepare' else attempt(ROOT,a.parent,a.i))
