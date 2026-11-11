"""2a准备器：只冻结文件，不启动AEDT，不发消息。1b未完整时拒绝建批。"""
import argparse
import copy
import shutil
import subprocess
from common_stage2 import *
import geometry
from presubmit import presubmit
from tuning import propose

REGISTRY=REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json'
BOXES=REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/SLOT_BOXES.json'

def initial_designs():
    designs=[r for r in read(REGISTRY)['designs'] if r['batch']=='2a']
    if len(designs)!=15 or any(r['family']!='N14' for r in designs):
        raise RuntimeError('2a冻结注册表不是N14的15项')
    golden={r['id']:r for r in read(BOXES)}
    for r in designs:
        if golden[r['id']]['geometry_mm']!=r['geometry_mm'] or golden[r['id']]['boxes']!=geometry.slot_boxes(r['geometry_mm'],r['topology']):
            raise RuntimeError('R1冻结槽盒与实际准备模型不一致：'+r['id'])
    return designs

def prepare(previous,dest,analysis):
    if dest.exists():raise RuntimeError('新批目录已存在；不能覆盖')
    if (previous/'STOP.json').exists():raise RuntimeError('前批停止记录有效')
    if read(analysis)['batch1b_outputs_complete'] is not True:raise RuntimeError('1b输出门槛未完成')
    gate=read(previous/'gate_1a.json')
    if gate['passed'] is not True:raise RuntimeError('1a基准未通过')
    consent=read(previous/'sweep_role_confirmation.json')
    if consent.get('policy')!='stage_specific' or not consent.get('human_reply_received'):raise RuntimeError('缺少最终扫频分阶段核验确认')
    prev=read(previous/'authorization.json')
    old_geometry=[read(p) for p in (previous/'ledger').glob('geometry_*.json')]
    if sum(r['batch']=='1b' for r in old_geometry)!=9:raise RuntimeError('1b尚未完成九个独立扰动')
    for i in range(9):
        w=previous/'runs'/f'S1_WS_{i:02d}'
        r=read(w/'review/REVIEW_R6.json')
        if not (w/'done.json').exists() or (w/'failure.txt').exists() or r['numerical_pass'] is not True:
            raise RuntimeError('1b终态或数值不完整')
        if not read(w/'cleanup.json')['released']:raise RuntimeError('前批桌面清理未确认')
    import psutil
    if any((p.info['name'] or '').lower()=='hf3d.exe' for p in psutil.process_iter(['name'])):
        raise RuntimeError('仍有求解在算；2a尚不准备释放')
    designs=initial_designs()
    cfg=dict(at=now(),human_authorized=True,batch='2a',plan_path='docs/PLAN_20261110_FOLD_BANDWIDTH_R6.md',
        plan_commit=subprocess.check_output(['git','rev-parse','origin/claude/fold-bandwidth-plan'],cwd=REPO,text=True).strip(),
        user_authorization='用户明确同意R6及R4后续批次；1b通过后进入2a。最新确认自适应与最终扫频按阶段核验。',
        limits=LIMITS,total_geometry_limit=187,prior_geometry_total=prev['prior_geometry_total']+len(old_geometry),
        prior_Analyze_total=prev['prior_Analyze_total']+len(list((previous/'ledger').glob('Analyze_*.json'))),
        cores=14,tasks=1,serial=True,no_hook=True,aedt_install=prev['aedt_install'],
        stage1_analysis=str(analysis),parent_order=[r['id'] for r in designs],designs={r['id']:r for r in designs},
        case_paths={},case_specs={},plan_hashes={},historical_hashes={},code_hashes={},
        technical_recovery_policy='R6 2.3；本入口只做冷启动。故障先停并保留，缓存恢复需独立版本和逐轮核验，不由本准备器自动重试。',
        batch_geometry_limit=45,per_parent_geometry_limit=3,per_geometry_Analyze_limit=14)
    for r in designs:
        prefix='uniform_control' if r['topology']=='straight_control' else 'runs'
        for i in range(1,4):
            case=r['id']+f'__T{i}'
            cfg['case_paths'][case]=f"{prefix}/{r['id']}/attempt_{i:03d}"
            cfg['case_specs'][case]=dict(parent_id=r['id'],attempt_ordinal=i)
    for p in sorted((REPO/'docs').glob('PLAN_20261110_FOLD_BANDWIDTH*.md')):
        cfg['plan_hashes'][p.relative_to(REPO).as_posix()]=sha(p)
    for p in [previous/'authorization.json',previous/'gate_1a.json',previous/'sweep_role_confirmation.json',analysis,
              *sorted((previous/'ledger').glob('*.json'))]:
        cfg['historical_hashes'][str(p)]=sha(p)
    cfg['code_hashes']={**prev['code_hashes'],**read(previous/'prelaunch_repair_v2.json')['code_hashes']}
    for folder in (HERE,R2):
        for p in sorted(folder.glob('*.py')):cfg['code_hashes'][p.relative_to(REPO).as_posix()]=sha(p)
    cfg['code_hashes'][(HERE/'runtime_header_stage2.txt').relative_to(REPO).as_posix()]=sha(HERE/'runtime_header_stage2.txt')
    for r in designs:
        if not presubmit(r['geometry_mm'],r['screen']['a_mm'],topology=r['topology'])['can_submit']:
            raise RuntimeError('2a初始几何筛选失败：'+r['id'])
    dest.mkdir()
    for name in ('ledger','decisions','model_freeze'):(dest/name).mkdir()
    write(dest/'authorization.json',cfg)
    shutil.copyfile(previous/'sweep_role_confirmation.json',dest/'sweep_role_confirmation.json')
    # 仅准备各设计的第一次；第2/3次必须由真实前次提取形成。
    for parent in cfg['parent_order']:prepare_attempt(dest,parent,1)
    write(dest/'PREPARED.json',dict(at=now(),authorization_sha256=sha(dest/'authorization.json'),
         initial_count=15,solver_started=False,new_Analyze=0))

def prepare_attempt(root,parent,ordinal):
    cfg=read(root/'authorization.json')
    if (root/'STOP.json').exists():raise RuntimeError('停止记录有效')
    if parent not in cfg['designs'] or not 1<=ordinal<=3:raise RuntimeError('设计或尝试未授权')
    case=parent+f'__T{ordinal}';w=case_dir(root,case,cfg)
    if w.exists():raise RuntimeError('尝试目录已存在，不覆盖')
    prior=cfg['designs'][parent]
    nominal_a=prior['screen']['a_mm']
    pred=copy.deepcopy(prior);previous_hash=None
    if ordinal>1:
        old=case_dir(root,parent+f'__T{ordinal-1}',cfg)
        r=read(old/'review/REVIEW_STAGE2.json')
        ack=read(old/'review/visual_ack.json')
        if r['numerical_pass'] is not True or ack.get('actually_viewed') is not True or ack['plot_sha256']!=sha(old/'review/S11_S21.png'):
            raise RuntimeError('前次未完成数值核验和真实看图')
        p=old/'review/extraction_R2.json'
        suggestion=propose(read(p),nominal_a,prior['topology'])
        if not suggestion['needs_solve']:raise RuntimeError('没有符合规则的下一次调参')
        pred.update(geometry_mm=suggestion['geometry_mm'],prediction=suggestion['prediction'],
           data_role='tuned_data',parent=parent,initial_prediction_stage='R2_length_update_after_prior_curve',
           tuning=suggestion,prior_curve_sha256=read(old/'done.json')['native_sha256'])
        previous_hash=sha(p)
    for name in ('input','evidence','native'):(w/name).mkdir(parents=True)
    source_hashes={**read(REGISTRY)['source_hashes'],REGISTRY.relative_to(REPO).as_posix():sha(REGISTRY),
          BOXES.relative_to(REPO).as_posix():sha(BOXES),'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')}
    freeze=dict(at=now(),parent_id=parent,attempt_ordinal=ordinal,design=pred,nominal_a_mm=nominal_a,
        expected_boxes=geometry.slot_boxes(pred['geometry_mm'],pred['topology']),source_hashes=source_hashes,
        authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,
        previous_extraction_sha256=previous_hash,prediction_level='冻结理论先验，不是已验证预测',solver_started=False)
    write(w/'input/freeze.json',freeze)
    write(root/'model_freeze'/(case+'.json'),freeze)
    return w

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    q=s.add_parser('prepare');q.add_argument('previous',type=Path);q.add_argument('dest',type=Path);q.add_argument('analysis',type=Path)
    q=s.add_parser('attempt');q.add_argument('root',type=Path);q.add_argument('parent');q.add_argument('ordinal',type=int)
    a=p.parse_args()
    if a.command=='prepare':prepare(a.previous.resolve(),a.dest.resolve(),a.analysis.resolve())
    else:prepare_attempt(a.root.resolve(),a.parent,a.ordinal)
