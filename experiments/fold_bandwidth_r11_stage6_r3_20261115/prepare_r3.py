"""Immutable R11 authorization/inputs, inherited costs and explicit R3 differences."""
import copy,shutil
from common_stage2 import *
import cad_ir
from geometry_gate import check_ir,check_envelopes
from native_control import expected_objects

PRIOR_H=REPO/'experiments/fold_bandwidth_r10_stage6_r2_20261115'
PRIOR_R=Path('F:/2026-1/circuit/test/output/fig8_r10_stage6_r2_20261115')

def prepare_r3(root):
    from prepare_r10 import make_input,SEVEN
    import psutil
    if root.exists():raise RuntimeError('R3 already prepared; never reset')
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native resources busy')
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed']:raise RuntimeError('tests failed')
    st=read(PRIOR_H/'CURRENT_STATUS.json')
    if (st['geometry_total'],st['actual_Analyze_total'],st['stop']['case'])!=(183,1730,'S6R10_P10__T1'):raise RuntimeError('prior stop/cost mismatch')
    if len(list((PRIOR_R/'ledger').glob('geometry_*.json')))!=2 or len(list((PRIOR_R/'ledger').glob('Analyze_*.json')))!=10:raise RuntimeError('R2 ledger changed')
    if read(PRIOR_R/'runs/S6R10_P10/attempt_001/RUN_RECORD.json')['Analyze_requested']!=1:raise RuntimeError('failed P10 cost changed')
    cfg=copy.deepcopy(read(PRIOR_R/'authorization.json'))
    for folder,manifest in [(PRIOR_H,'STOP_MANIFEST.json'),(REPO/'experiments/fold_bandwidth_r10_stage6_r1_20261115','CLOSURE_MANIFEST.json')]:
        for rel,h in read(folder/manifest).items():
            if sha(folder/rel)!=h:raise RuntimeError('historical closure mismatch '+rel)
            cfg['historical_hashes'][str(folder/rel)]=h
        cfg['historical_hashes'][str(folder/manifest)]=sha(folder/manifest)
    for p in list((PRIOR_R/'ledger').glob('*.json'))+[PRIOR_R/'STOP.json',PRIOR_R/'authorization.json']:
        cfg['historical_hashes'][str(p)]=sha(p)
    closed=['S6R10_'+f'P{i}' for i in range(1,10)]
    paths=copy.deepcopy(cfg['inherited_public_result_paths']);paths['S6R10_P9__T1']=(PRIOR_H/'results/S6R10_P9__T1').relative_to(REPO).as_posix()
    cfg.update(at=now(),execution_revision='R11_STAGE6_R3',plan_commit='b9fb9b7',user_authorization='Human R11 turn: accepts section0 and resumes stage6 only; all seven validation gates before first solve',
        prior_geometry_total=183,prior_Analyze_total=1730,batch_geometry_limit=17,total_geometry_limit=200,
        inherited_stage6_geometry=10,inherited_stage6_Analyze=97,full_stage6_geometry_limit=27,
        inherited_geometry_logicals=['S6R10_P10__T1'],inherited_logical_Analyze={'S6R10_P10__T1':1},
        inherited_closed_parents=closed,inherited_public_result_paths=paths,inherited_case_paths={},
        required_preflight_cases=['S6R10_'+n+'__T1' for n in SEVEN],
        parent_order=closed+['S6R10_'+n for n in SEVEN+['P1dense','P2dense','C1','B1R','B1Rdense','C1R','W3','W4']],
        technical_recovery_policy='R11 authorized R3 only; native validation error or repeated modeling failure stops; never automatic R4.',
        continuation_basis='R11 board outline fixed both etch signs; P9c substitutes overetch margin; W4 at most2',
        batch_max_Analyze_from_geometry_caps=17*14+3*6+13,full_stage6_max_Analyze_from_geometry_caps=396,
        case_paths={},case_specs={})
    cfg['R11_W4_max_attempts']=2
    for n in SEVEN+['P1dense','P2dense','C1','B1R','B1Rdense','C1R','W3','W4']:
        parent='S6R10_'+n
        ordinals=[4] if n=='W3' else range(1,4) if n=='B1R' else range(1,3) if n=='W4' else [1]
        for i in ordinals:
            for retry in ([False,True] if n in SEVEN+['P1dense','P2dense'] else [False]):
                c=parent+f'__T{i}'+('__NR1' if retry else '')
                cfg['case_paths'][c]=f'runs/{parent}/attempt_{i:03d}'+('_numerical_retry_1' if retry else '')
                cfg['case_specs'][c]=dict(parent_id=parent,attempt_ordinal=i,numerical_retry=retry)
    base=cfg['designs']['S6R10_P9'];pc=copy.deepcopy(base);pc.update(id='S6R10_P9c',design='P9c',data_role='R11_corrected_overetch_fixed_milled_board_outline')
    cfg['designs']['S6R10_P9c']=pc
    comparisons={}
    for parent,d in cfg['designs'].items():
        if parent in closed:continue
        ir=d['cad_ir'];old=copy.deepcopy(ir)
        new=cad_ir.json_value(cad_ir.build(ir['base_geometry_mm'],ir['etch_e_mm'],ir['er'],ir['h_mm'],port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'))
        d['cad_ir']=new;d['geometry_mm']=new['geometry_mm'];check_ir(new)
        comparisons[parent]=dict(six_dimensions_unchanged=old['geometry_mm']==new['geometry_mm'],slot_boxes_unchanged=old['expected_slot_boxes']==new['expected_slot_boxes'],
            old_ground=old['rectangles']['ground'],new_ground=new['rectangles']['ground'])
        if not comparisons[parent]['six_dimensions_unchanged'] or not comparisons[parent]['slot_boxes_unchanged']:raise RuntimeError('unapproved scientific geometry change')
    oldp10=read(PRIOR_H/'pre_solve/S6R10_P10__T1.json')['design']['cad_ir']
    rejected=check_envelopes(expected_objects(oldp10))
    if rejected['passed']:raise RuntimeError('old P10 not intercepted')
    plan=(REPO/'docs/PLAN_20261115_FOLD_BANDWIDTH_R11.md').read_text(encoding='utf-8')
    write(HERE/'freeze/R11_R3.json',dict(at=now(),plan_commit='b9fb9b7',authorizes_solver=True,board_policy='all copper board edges x=+-15/y=+-25 fixed on both etch signs; ground=board minus offset slot',
        seven_point_order=SEVEN,comparisons=comparisons,old_P10_gate=rejected,original_P9_role='valid but ground edge inset .01mm; archive only, not overetch margin',
        Q17_Q20_verbatim=plan.split('## 4. 新登记的预测')[1].split('## 5.')[0],
        budget=dict(stage6_used=10,cumulative_used=183,Analyze_used=1730,new_geometry_cap=17,P10_retained_Analyze=1,P10_new_cap=13,W4_max=2,total_cap=200),
        original_R10_1_sha256=sha(HERE/'freeze/R10_1.json'),all_seven_validation_required_before_first_Analyze=True))
    cfg['plan_hashes']['docs/PLAN_20261115_FOLD_BANDWIDTH_R11.md']=sha(REPO/'docs/PLAN_20261115_FOLD_BANDWIDTH_R11.md')
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline') for p in (HERE/folder).glob('*.json')})
    root.mkdir();(HERE/'pre_solve').mkdir()
    for n in ('ledger','decisions','model_freeze','publications','preflights'):(root/n).mkdir()
    write(root/'authorization.json',cfg);shutil.copyfile(PRIOR_R/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    for p in closed:shutil.copyfile(PRIOR_R/'decisions'/(p+'_FINAL.json'),root/'decisions'/(p+'_FINAL.json'))
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:v for k,v in cfg.items() if k not in ('historical_hashes','prior_cases','prior_decisions','designs')})
    for n in SEVEN+['W3','W4']:print(make_input(root,'S6R10_'+n,4 if n=='W3' else 1))
    return dict(prepared=True,solver_started=False,new_Analyze=0)
