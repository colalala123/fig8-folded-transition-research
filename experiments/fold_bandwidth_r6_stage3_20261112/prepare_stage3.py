"""阶段3离线冻结与逐次输入准备；不连接/启动AEDT。"""
import argparse,copy,subprocess,shutil
from common_stage2 import *
import geometry
from presubmit import presubmit
from tuning import new_prediction,propose,MODEL
REG=REPO/'experiments/fold_bandwidth_r3_20261110/freeze_r3/REGISTRY_R3.json'
AUDIT=REPO/'experiments/fold_bandwidth_r6_stage2b_analysis_20261112/final/INDEPENDENT_AUDIT.json'
GATE=AUDIT.parent/'GATE_TO_STAGE3.json'
PRED=HERE/'freeze/PREDICTIONS.json'
PRIOR=Path('F:/2026-1/circuit/test/output/fig8_r6_2b_20261112')

def rows():
    records=copy.deepcopy(read(REG)['designs'])
    eq=[r for r in records if r['material_role']=='archived_lossy']
    if len(eq)!=10 or len(records)!=20:raise RuntimeError('R3登记不符')
    result=[]
    for r in eq:
        r.update(kind='EQ',board_half_x_mm=15.,data_role='equal_ripple_initial',
                 prediction=new_prediction(r['geometry_mm'],r['topology']))
        r['expected_boxes']=geometry.slot_boxes(r['geometry_mm'],r['topology'])
        if r['expected_boxes']!=r['boxes']:raise RuntimeError('R3槽盒不符')
        result.append(r)
    for r in eq:
        ll=copy.deepcopy(r);ll.update(id=r['id']+'_LOSSLESS',parent=r['id'],
            kind='LOSSLESS',material_role='lossless_control',max_Analyze=1,
            data_role='lossless_control',conditional_on_parent_final_geometry=True)
        result.append(ll)
    orig=read(REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json')['designs']
    for r in orig:
        if r['id'].startswith('S3_BOUNDARY_'):
            r=copy.deepcopy(r);r.update(kind='BOUNDARY',board_half_x_mm=20.,
                material_role='archived_lossy',max_Analyze=1,data_role='boundary_control')
            r['nominal_a_mm']=0. if r['topology']=='straight_control' else 1.8
            source=(REPO/'experiments/fold_bandwidth_r6_stage2_20261111/results/S2_E0_N14__T3/INPUT.json' if r['topology']=='straight_control' else Path('F:/2026-1/circuit/test/output/fig8_fold_bandwidth_r6_20261111/runs/S1_BASE_N14/input/freeze.json'))
            r['geometry_mm']=read(source)['design']['geometry_mm']
            r['prediction']=new_prediction(r['geometry_mm'],r['topology'])
            r['expected_boxes']=geometry.slot_boxes(r['geometry_mm'],r['topology'])
            r['source_final_input_sha256']=sha(source)
            result.append(r)
    if len(result)!=22:raise RuntimeError('对照登记缺失')
    return result

def prepare(dest):
    if (dest/'authorization.json').exists():raise RuntimeError('不覆盖授权')
    if not read(AUDIT)['passed'] or not read(GATE)['may_prepare_stage3']:raise RuntimeError('2b门槛未过')
    pc=read(PRIOR/'authorization.json')
    a=read(AUDIT)
    if a['total_geometry_count']!=100 or a['total_actual_Analyze_count']!=904:raise RuntimeError('前批预算不符')
    for p in (HERE/'preflight').glob('*NATIVE_PREFLIGHT.json'):
        if not read(p)['passed']:raise RuntimeError('原生预检未过')
    if len(list((HERE/'preflight').glob('*NATIVE_PREFLIGHT.json')))!=3:raise RuntimeError('缺少三种原生预检')
    rr=rows()
    PRED.parent.mkdir(exist_ok=True)
    write(PRED,dict(schema='stage3-pre-solve-freeze-v1',designs=rr,source_R3_sha256=sha(REG),
        model_sha256=sha(MODEL),solver_started=False,new_Analyze=0))
    cfg=dict(at=now(),human_authorized=True,batch='3',limits=LIMITS,total_geometry_limit=187,
       batch_geometry_limit=42,per_parent_geometry_limit=3,per_geometry_Analyze_limit=14,
       prior_geometry_total=100,prior_Analyze_total=904,cores=14,tasks=1,serial=True,no_hook=True,
       user_authorization='你继续做阶段3，做完符合条件后做阶段4和阶段5',
       plan_commit=subprocess.check_output(['git','rev-parse','origin/claude/fold-bandwidth-plan'],cwd=REPO,text=True).strip(),
       aedt_install=pc['aedt_install'],prior_batch_audit=str(AUDIT),prior_batch_gate=str(GATE),
       parent_order=[r['id'] for r in rr],designs={r['id']:r for r in rr},
       case_paths={},case_specs={},code_hashes=dict(pc['code_hashes']),plan_hashes=pc['plan_hashes'],
       historical_hashes={str(p):sha(p) for p in [AUDIT,GATE,PRIOR/'BATCH_COMPLETE.json',PRIOR/'authorization.json']},
       frozen_hashes={p.relative_to(REPO).as_posix():sha(p) for p in [PRED,REG,MODEL,*sorted((HERE/'preflight').glob('*NATIVE_PREFLIGHT.json'))]},
       technical_recovery_policy='R6 2.3；故障保留，审核缓存逐轮一致后版本化续算；不自动冷重试。')
    for p in HERE.glob('*.py'):cfg['code_hashes'][p.relative_to(REPO).as_posix()]=sha(p)
    for folder in ('fold_bandwidth_r3_20261110','fold_bandwidth_r2_20261110'):
        for p in (REPO/'experiments'/folder).glob('*.py'):cfg['code_hashes'][p.relative_to(REPO).as_posix()]=sha(p)
    for r in rr:
        for i in range(1,r['max_Analyze']+1):
            case=r['id']+f'__T{i}';prefix='uniform_control' if r['topology']=='straight_control' else 'runs'
            cfg['case_paths'][case]=f"{prefix}/{r['id']}/attempt_{i:03d}"
            cfg['case_specs'][case]=dict(parent_id=r['id'],attempt_ordinal=i)
    for sub in ('ledger','decisions','model_freeze'):(dest/sub).mkdir(parents=True)
    write(dest/'authorization.json',cfg)
    shutil.copyfile(PRIOR/'sweep_role_confirmation.json',dest/'sweep_role_confirmation.json')
    for r in rr:
        if r['kind']=='EQ':attempt(dest,r['id'],1)
    write(dest/'PREPARED.json',dict(at=now(),initial_count=10,conditional_controls=12,new_Analyze=0,requires_publication=True))
    # Public sanitized configuration does not include machine paths.
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:cfg[k] for k in
        ('human_authorized','batch','limits','total_geometry_limit','batch_geometry_limit','prior_geometry_total',
        'prior_Analyze_total','cores','tasks','serial','no_hook','user_authorization','plan_commit','code_hashes','frozen_hashes')})

def attempt(root,parent,i):
    cfg=read(root/'authorization.json');initial=cfg['designs'][parent]
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists():raise RuntimeError('停止/暂停')
    if not 1<=i<=initial['max_Analyze']:raise RuntimeError('尝试越界')
    case=parent+f'__T{i}';w=case_dir(root,case,cfg)
    if w.exists():raise RuntimeError('不覆盖已有尝试')
    pred=copy.deepcopy(initial);prev_hash=None;binding=None
    if initial['kind']=='EQ' and i>1:
        old=case_dir(root,parent+f'__T{i-1}',cfg);qp=old/'review/extraction_R2.json'
        ack=read(old/'review/visual_ack.json');review=read(old/'review/REVIEW_STAGE3.json')
        if not review['numerical_pass'] or not ack['actually_viewed'] or ack['plot_sha256']!=sha(old/'review/S11_S21.png') or ack['extraction_sha256']!=sha(qp):
            raise RuntimeError('前次未实际看图/数值未过')
        su=propose(read(qp),initial['nominal_a_mm'],initial['topology'])
        if not su['needs_solve']:raise RuntimeError('无合法下一点')
        pred.update(geometry_mm=su['geometry_mm'],prediction=su['prediction'],tuning=su,
                    data_role='tuned_data',screen=su['screen'])
        prev_hash=sha(qp)
    elif initial['kind']!='EQ':
        if initial['kind']=='LOSSLESS':
            dec=read(root/'decisions'/(initial['parent']+'_FINAL.json'))
            if not dec['tuned']:raise RuntimeError('未调准不安排无耗')
            old=case_dir(root,dec['selected_case'],cfg)
            source=old/'input/freeze.json';selected=dec['selected_case']
        elif parent=='S3_BOUNDARY_N14_STRAIGHT':
            source=REPO/'experiments/fold_bandwidth_r6_stage2_20261111/results/S2_E0_N14__T3/INPUT.json'
            selected='S2_E0_N14__T3'
        elif parent=='S3_BOUNDARY_N14_A18':
            source=Path('F:/2026-1/circuit/test/output/fig8_fold_bandwidth_r6_20261111/runs/S1_BASE_N14/input/freeze.json')
            selected='S1_BASE_N14'
        else:raise RuntimeError('未定义边界父项')
        src=read(source);g=src.get('design',{}).get('geometry_mm') or src.get('geometry_mm')
        if g is None:raise RuntimeError('父几何缺失')
        pred.update(geometry_mm=g,prediction=new_prediction(g,pred['topology']))
        binding=dict(source_input=str(source),source_input_sha256=sha(source),selected_case=selected)
    for sub in ('input','evidence','native'):(w/sub).mkdir(parents=True)
    if binding:write(w/'input/parent_binding.json',binding)
    freeze=dict(at=now(),parent_id=parent,attempt_ordinal=i,design=pred,nominal_a_mm=initial['nominal_a_mm'],
        expected_boxes=geometry.slot_boxes(pred['geometry_mm'],pred['topology']),
        source_hashes={REG.relative_to(REPO).as_posix():sha(REG),MODEL.relative_to(REPO).as_posix():sha(MODEL),
            'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},
        authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,
        previous_extraction_sha256=prev_hash,prediction_level='冻结模型预测；非达标保证',solver_started=False)
    write(w/'input/freeze.json',freeze);write(root/'model_freeze'/(case+'.json'),freeze)
    return w

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','attempt']);p.add_argument('root',type=Path)
    p.add_argument('parent',nargs='?');p.add_argument('ordinal',nargs='?',type=int);a=p.parse_args()
    prepare(a.root.resolve()) if a.command=='prepare' else attempt(a.root.resolve(),a.parent,a.ordinal)
