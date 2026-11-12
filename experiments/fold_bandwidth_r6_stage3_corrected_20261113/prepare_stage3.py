"""修正版离线准备。原批STOP/输入不动，计入原批全部真实成本。"""
import argparse,copy,subprocess,shutil
from collections import Counter
from common_stage2 import *
from tuning import propose,MODEL,new_prediction
from history_links import prior_dir,decision_path
import geometry
OLD=REPO/'experiments/fold_bandwidth_r6_stage3_20261112'
OROOT=Path('F:/2026-1/circuit/test/output/fig8_r6_stage3_20261112/batch')
REG=REPO/'experiments/fold_bandwidth_r3_20261110/freeze_r3/REGISTRY_R3.json'
def rows():
    return list(copy.deepcopy(read(OROOT/'authorization.json')['designs']).values())
def prepare(dest):
    import psutil
    if dest.exists():raise RuntimeError('新修正版目录已存在')
    if any((p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('旧求解/桌面尚在')
    oc=read(OROOT/'authorization.json');stop=read(OROOT/'STOP.json')
    if stop.get('defect')!='folded_centerline_offset_4Ws_instead_of_2Ws':raise RuntimeError('不是指定程序缺陷接续')
    geo=[read(p) for p in sorted((OROOT/'ledger').glob('geometry_*.json'))]
    calls=list((OROOT/'ledger').glob('Analyze_*.json'))
    if len(geo)!=5 or len(calls)!=47:raise RuntimeError('原批成本不符；不得猜测')
    facts=[];prior_cases={};history={}
    for item in geo:
        case=item['case'];w=case_dir(OROOT,case,oc);rr=read(w/'RUN_RECORD.json')
        if not read(w/'cleanup.json')['released']:raise RuntimeError('旧桌面未正常释放')
        started=read(w/'worker_started.json')
        try:
            p=psutil.Process(started['pid'])
            if abs(p.create_time()-started['create_time'])<.01:raise RuntimeError('旧worker仍在')
        except psutil.NoSuchProcess:pass
        actual=len(list((OROOT/'ledger').glob('Analyze_'+case+'_*.json')))
        if rr['Analyze_requested']!=actual:raise RuntimeError('实际请求和记录不符')
        affected=case=='S3R3_EQ_N04_01__T2'
        if affected:
            if actual!=1 or rr['solve_completed'] or not(w/'failure.txt').exists():raise RuntimeError('受影响尝试终态不符')
            if history_from(w/'native/adaptive_00.txt')[-1][0]!=16:raise RuntimeError('未完整保留原生16轮')
        else:
            rv=read(w/'review/REVIEW_STAGE3.json');ack=read(w/'review/visual_ack.json')
            if not rv['numerical_pass'] or not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png'):raise RuntimeError('旧有效点审核缺失')
            if sha(w/'native/full_modes.npz')!=read(w/'done.json')['native_sha256']:raise RuntimeError('旧曲线改变')
        prior_cases[case]=dict(path=str(w),input_sha256=sha(w/'input/freeze.json'))
        for name in ('input/freeze.json','RUN_RECORD.json','cleanup.json','done.json','failure.txt',
                     'review/REVIEW_STAGE3.json','review/visual_ack.json','review/extraction_R2.json','native/full_modes.npz'):
            if(w/name).exists():history[str(w/name)]=sha(w/name)
        facts.append(dict(case=case,parent_id=item['parent_id'],actual_Analyze=actual,
            completed=rr['solve_completed'],numerical_pass=rr['numerical_pass'],software_affected=affected,
            original_input_sha256=sha(w/'input/freeze.json')))
    prior_decisions={}
    for p in (OROOT/'decisions').glob('*_FINAL.json'):
        d=read(p);prior_decisions[d['parent_id']]=dict(path=str(p),sha256=sha(p));history[str(p)]=sha(p)
    if set(prior_decisions)!={'S3R3_EQ_N04_00'}:raise RuntimeError('旧结项范围变化')
    audit=dict(at=now(),ledger_accounted=True,stage3_geometries=5,stage3_actual_Analyze=47,
       cumulative_geometries=105,cumulative_Analyze=951,completed_numerically_valid=4,
       controlled_software_stop=1,all_native_processes_released=True,rows=facts)
    write(HERE/'PRIOR_EXECUTION_AUDIT.json',audit)
    cfg=copy.deepcopy(oc)
    cfg.update(at=now(),prior_geometry_total=105,prior_Analyze_total=951,stage3_prior_geometry=5,
        stage3_prior_Analyze=47,batch_geometry_limit=37,prior_parent_geometry=dict(Counter(x['parent_id'] for x in geo)),
        prior_cases=prior_cases,prior_decisions=prior_decisions,
        calibration_overrides={'S3R3_EQ_N04_01__T3':'S3R3_EQ_N04_01__T1'},
        prior_stage3_audit=str(HERE/'PRIOR_EXECUTION_AUDIT.json'),execution_revision='centerline_fix_v2',
        user_authorization='用户授权阶段3至5及R6 2.3修复后继续；不加几何额度。原批已用5，修正版最多37。',
        case_paths={},case_specs={},code_hashes=copy.deepcopy(oc['code_hashes']),
        historical_hashes={**oc['historical_hashes'],**history,str(OROOT/'STOP.json'):sha(OROOT/'STOP.json')})
    for p in (OROOT/'ledger').glob('*.json'):cfg['historical_hashes'][str(p)]=sha(p)
    for parent in cfg['parent_order']:
        r=cfg['designs'][parent];used=cfg['prior_parent_geometry'].get(parent,0)
        for i in range(used+1,r['max_Analyze']+1):
            case=parent+f'__T{i}';prefix='uniform_control' if r['topology']=='straight_control' else 'runs'
            cfg['case_paths'][case]=f'{prefix}/{parent}/attempt_{i:03d}'
            cfg['case_specs'][case]=dict(parent_id=parent,attempt_ordinal=i)
    (HERE/'freeze').mkdir()
    write(HERE/'freeze/EXECUTOR_REVISION.json',dict(at=now(),revision='centerline_fix_v2',
         base_authorization_sha256=sha(OROOT/'authorization.json'),prior_audit_sha256=sha(HERE/'PRIOR_EXECUTION_AUDIT.json'),
         scope_unchanged=True,extra_geometry=0,stage3_cap=42,prior_geometry=5,remaining_cap=37,
         first_case='S3R3_EQ_N04_01__T3',calibration_basis='S3R3_EQ_N04_01__T1',
         formula='Use R2 dimensions() to invert Ls1; Lc=Ls1+2a+2g+2Ws'))
    cfg['frozen_hashes']={**oc['frozen_hashes'],**{p.relative_to(REPO).as_posix():sha(p)
           for p in [HERE/'PRIOR_EXECUTION_AUDIT.json',HERE/'freeze/EXECUTOR_REVISION.json']}}
    for p in HERE.glob('*.py'):cfg['code_hashes'][p.relative_to(REPO).as_posix()]=sha(p)
    dest.mkdir(parents=True)
    for sub in ('ledger','decisions','model_freeze'):(dest/sub).mkdir()
    write(dest/'authorization.json',cfg)
    shutil.copyfile(OROOT/'sweep_role_confirmation.json',dest/'sweep_role_confirmation.json')
    # Honest conditional skip: no curve, no invented pass or visual ACK.
    old=read(decision_path(dest,'S3R3_EQ_N04_00',cfg))
    write(dest/'decisions/S3R3_EQ_N04_00_LOSSLESS_FINAL.json',dict(at=now(),
        parent_id='S3R3_EQ_N04_00_LOSSLESS',kind='LOSSLESS',complete=True,skipped=True,
        reason='父直槽在原3次预算内未调准，不安排无耗对照',parent_decision_sha256=sha(decision_path(dest,'S3R3_EQ_N04_00',cfg))))
    for parent in cfg['parent_order']:
        r=cfg['designs'][parent]
        if r['kind']=='EQ' and parent not in prior_decisions:
            attempt(dest,parent,cfg['prior_parent_geometry'].get(parent,0)+1)
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:cfg[k] for k in
        ('human_authorized','batch','limits','total_geometry_limit','batch_geometry_limit','prior_geometry_total',
         'prior_Analyze_total','stage3_prior_geometry','stage3_prior_Analyze','prior_parent_geometry','cores','tasks','serial',
         'no_hook','user_authorization','execution_revision','code_hashes','frozen_hashes','calibration_overrides')})
    print('CORRECTED_PREPARED',audit)

def history_from(p):return history(p.read_text(encoding='utf-8-sig'))
def attempt(root,parent,i):
    cfg=read(root/'authorization.json');initial=cfg['designs'][parent]
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists():raise RuntimeError('停止/暂停')
    case=parent+f'__T{i}'
    if case not in cfg['case_paths']:raise RuntimeError('该几何槽已用/未授权')
    w=case_dir(root,case,cfg)
    if w.exists():raise RuntimeError('不覆盖已有尝试')
    pred=copy.deepcopy(initial);previous_hash=None;binding=None
    if initial['kind']=='EQ' and i>1:
        source_case=cfg['calibration_overrides'].get(case,parent+f'__T{i-1}')
        old=prior_dir(root,source_case,cfg);qp=old/'review/extraction_R2.json'
        rv=read(old/'review/REVIEW_STAGE3.json');ack=read(old/'review/visual_ack.json')
        if not rv['numerical_pass'] or not ack['actually_viewed'] or ack['plot_sha256']!=sha(old/'review/S11_S21.png') or ack['extraction_sha256']!=sha(qp):
            raise RuntimeError('有效校准点审核不足')
        sug=propose(read(qp),initial['nominal_a_mm'],initial['topology'])
        if not sug['needs_solve']:raise RuntimeError('没有合法下一步')
        pred.update(geometry_mm=sug['geometry_mm'],prediction=sug['prediction'],tuning=sug,
            data_role='tuned_data',screen=sug['screen'])
        previous_hash=sha(qp)
    elif initial['kind']!='EQ':
        if initial['kind']=='LOSSLESS':
            dec=read(decision_path(root,initial['parent'],cfg))
            if not dec['tuned']:raise RuntimeError('父项未调准')
            old=prior_dir(root,dec['selected_case'],cfg);source=old/'input/freeze.json';selected=dec['selected_case']
        else:
            source=(REPO/'experiments/fold_bandwidth_r6_stage2_20261111/results/S2_E0_N14__T3/INPUT.json' if parent=='S3_BOUNDARY_N14_STRAIGHT' else
                Path('F:/2026-1/circuit/test/output/fig8_fold_bandwidth_r6_20261111/runs/S1_BASE_N14/input/freeze.json'))
            selected='S2_E0_N14__T3' if parent=='S3_BOUNDARY_N14_STRAIGHT' else 'S1_BASE_N14'
        src=read(source);g=src['design']['geometry_mm']
        pred.update(geometry_mm=g,prediction=new_prediction(g,pred['topology']))
        binding=dict(source_input=str(source),source_input_sha256=sha(source),selected_case=selected)
    for sub in ('input','evidence','native'):(w/sub).mkdir(parents=True)
    if binding:write(w/'input/parent_binding.json',binding)
    freeze=dict(at=now(),parent_id=parent,attempt_ordinal=i,design=pred,nominal_a_mm=initial['nominal_a_mm'],
        expected_boxes=geometry.slot_boxes(pred['geometry_mm'],pred['topology']),
        source_hashes={REG.relative_to(REPO).as_posix():sha(REG),MODEL.relative_to(REPO).as_posix():sha(MODEL),
            'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},
        authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,
        previous_extraction_sha256=previous_hash,prediction_level='修复中心线换算；原冻结模型不重拟合',solver_started=False)
    write(w/'input/freeze.json',freeze);write(root/'model_freeze'/(case+'.json'),freeze)
    return w
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','attempt']);p.add_argument('root',type=Path)
    p.add_argument('parent',nargs='?');p.add_argument('ordinal',nargs='?',type=int);a=p.parse_args()
    prepare(a.root.resolve()) if a.command=='prepare' else attempt(a.root.resolve(),a.parent,a.ordinal)
