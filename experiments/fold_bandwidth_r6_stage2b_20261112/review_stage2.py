"""阶段2离线提取、数值复核和图；不求解、不自行ACK或放行下一点。"""
import argparse
import numpy as np
from common_stage2 import *
from tuning import classify,propose
from roles_r6 import evaluate
from extract_run import extract
from analyze_stage1 import metrics_from_extraction

def review(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if not (w/'done.json').exists() or (w/'failure.txt').exists():raise RuntimeError('没有完整终态')
    freeze=read(w/'input/freeze.json');record=read(w/'RUN_RECORD.json');done=read(w/'done.json')
    if freeze['authorization_sha256']!=sha(root/'authorization.json'):raise RuntimeError('授权绑定不符')
    for rel,h in {**cfg['code_hashes'],**freeze['source_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('冻结改变：'+rel)
    if done['native_sha256']!=sha(w/'native/full_modes.npz'):raise RuntimeError('原生曲线哈希不符')
    files=sorted((w/'evidence').glob('*_solver.jsonl'));role_checks={}
    import json
    for p in files:
        label=p.name.removesuffix('_solver.jsonl')
        obs=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
        role_checks[label]=evaluate(obs,label)
    num=bool(record['numerical_pass'] and 100000<=record['mesh_cells']<=112000 and record['delta_s']<=.005
       and len(role_checks)==record['Analyze_requested'] and all(v['passed'] for v in role_checks.values())
       and 'final_sweep' in role_checks and read(w/'evidence/slot_comparison.json')['passed']
       and record['cleanup']['released'])
    # 最后扫频前后全部原生网格历史必须相同，而不只是末行单元数。
    same_history=history((w/'native/pre_final_sweep.txt').read_text(encoding='utf-8-sig'))==history((w/'native/convergence.txt').read_text(encoding='utf-8-sig'))
    num=num and same_history
    data=np.load(w/'native/full_modes.npz',allow_pickle=False);f,S=data['f_GHz'],data['S']
    metadata=read(w/'native/metadata.json')
    if metadata['geometry']!=freeze['design']['geometry_mm']:raise RuntimeError('输出几何不符')
    q=extract(f,S[:,[0,2],0],metadata)
    q.update(full_modal_power_certified=False,input_sha256=sha(w/'native/full_modes.npz'),
             topology=freeze['design']['topology'],data_role=freeze['design']['data_role'])
    status=classify(q)
    next_input=propose(q,freeze['nominal_a_mm'],freeze['design']['topology'])
    out=w/'review';out.mkdir(exist_ok=False)
    write(out/'extraction_R2.json',q)
    summary=dict(at=now(),case=case,parent_id=freeze['parent_id'],attempt_ordinal=freeze['attempt_ordinal'],
       solve_completed=record['solve_completed'],numerical_pass=bool(num),design_pass=q['shape'].get('passed'),
       tuning_status=status,next_suggestion=next_input,metrics=metrics_from_extraction(q),
       mesh_cells=record['mesh_cells'],delta_s=record['delta_s'],passes=record['passes'],
       Analyze_requests=record['Analyze_requested'],native_sha256=done['native_sha256'],
       final_sweep_history_unchanged=same_history,role_checks=role_checks,
       topology=freeze['design']['topology'],data_role=freeze['design']['data_role'],
       result_level='名义插值结果；不是直接频点、全模式功率或制造公差认证')
    write(out/'REVIEW_STAGE2.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,5))
    for v,label in ((S[:,0,0],'S11'),(S[:,2,0],'S21')):
        ax.plot(f,20*np.log10(np.maximum(abs(v),1e-15)),label=label)
    ax.axhline(-20,color='gray',ls='--',lw=.8);ax.axhline(-2,color='gray',ls=':',lw=.8)
    ax.axvspan(3.92,9.52,color='green',alpha=.07)
    ax.set(xlim=(.01,15),ylim=(-60,3),xlabel='Frequency (GHz)',ylabel='Magnitude (dB)',title=case)
    ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(out/'S11_S21.png',dpi=150);plt.close(fig)
    if not num and not (root/'STOP.json').exists():
        write(root/'STOP.json',dict(at=now(),case=case,reason='阶段2数值验收失败；不放宽、不自动调参掩盖。'))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('role_checks','next_suggestion')},ensure_ascii=False,indent=2))
    return summary

def finish_parent(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);r=read(w/'review/REVIEW_STAGE2.json')
    ack=read(w/'review/visual_ack.json')
    if ack.get('actually_viewed') is not True or ack['plot_sha256']!=sha(w/'review/S11_S21.png'):
        raise RuntimeError('缺少真实看图证据；此函数不创建ACK')
    if not r['numerical_pass'] or not r['solve_completed'] or (root/'STOP.json').exists():
        raise RuntimeError('数值/终态未通过，不释放下一设计')
    tune=r['tuning_status'];suggestion=r['next_suggestion']
    if not tune['length_calibrated'] and suggestion['needs_solve'] and r['attempt_ordinal']<3:
        raise RuntimeError('尚有已授权长度调参步骤，不提前结项')
    reason='已调准且R2提取未标记多解' if tune['usable_for_law'] else (
      '长度调准但等效提取多解，保留不纳入定量规律拟合' if tune['length_calibrated'] else
      '三次几何预算内未调准' if r['attempt_ordinal']>=3 else '当前规程不能产生合法下一点：'+suggestion['reason'])
    decision=dict(at=now(),parent_id=r['parent_id'],selected_case=case,complete=True,
       usable_for_law=tune['usable_for_law'],length_calibrated=tune['length_calibrated'],reason=reason,
       review_sha256=sha(w/'review/REVIEW_STAGE2.json'),visual_ack_sha256=sha(w/'review/visual_ack.json'),
       not_physical_impossibility=not tune['usable_for_law'])
    write(root/'decisions'/(r['parent_id']+'_FINAL.json'),decision)
    return decision

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('case');p.add_argument('--finish-parent',action='store_true')
    a=p.parse_args();r=finish_parent(a.root.resolve(),a.case) if a.finish_parent else review(a.root.resolve(),a.case)
    if r.get('numerical_pass') is False:raise SystemExit(2)
