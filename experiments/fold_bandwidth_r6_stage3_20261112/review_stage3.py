"""阶段3离线独立审核与图；实际看图ACK必须由执行者看图后另写。"""
import argparse,json
import numpy as np
from common_stage2 import *
from tuning import classify,propose
from roles_r6 import evaluate
from extract_run import extract
from analyze_stage1 import metrics_from_extraction
from power_analysis import lossless_modal_balance

def review(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if not (w/'done.json').exists() or (w/'failure.txt').exists():raise RuntimeError('无完整终态')
    fz=read(w/'input/freeze.json');rec=read(w/'RUN_RECORD.json');done=read(w/'done.json');pred=fz['design']
    if fz['authorization_sha256']!=sha(root/'authorization.json') or done['native_sha256']!=sha(w/'native/full_modes.npz'):raise RuntimeError('证据绑定不符')
    for rel,h in {**cfg['code_hashes'],**fz['source_hashes']}.items():
        if sha(REPO/rel)!=h:raise RuntimeError('代码/来源改变')
    roles={}
    for p in sorted((w/'evidence').glob('*_solver.jsonl')):
        label=p.name.removesuffix('_solver.jsonl')
        roles[label]=evaluate([json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()],label)
    same=history((w/'native/pre_final_sweep.txt').read_text(encoding='utf-8-sig'))==history((w/'native/convergence.txt').read_text(encoding='utf-8-sig'))
    num=bool(rec['numerical_pass'] and 100000<=rec['mesh_cells']<=112000 and rec['delta_s']<=.005 and same and
        len(roles)==rec['Analyze_requested'] and 'final_sweep' in roles and all(r['passed'] for r in roles.values()) and
        read(w/'evidence/slot_comparison.json')['passed'] and rec['cleanup']['released'])
    z=np.load(w/'native/full_modes.npz',allow_pickle=False);fr,S=z['f_GHz'],z['S']
    meta=read(w/'native/metadata.json')
    if meta['geometry']!=pred['geometry_mm']:raise RuntimeError('原生几何不符')
    q=extract(fr,S[:,[0,2],0],meta)
    q.update(full_modal_power_certified=False,input_sha256=sha(w/'native/full_modes.npz'),
        topology=pred['topology'],data_role=pred['data_role'])
    st=classify(q)
    sug=propose(q,fz['nominal_a_mm'],pred['topology']) if pred['kind']=='EQ' else dict(needs_solve=False,reason='control_one_geometry_only')
    out=w/'review';out.mkdir()
    write(out/'extraction_R2.json',q)
    summary=dict(at=now(),case=case,parent_id=fz['parent_id'],attempt_ordinal=fz['attempt_ordinal'],
        kind=pred['kind'],family=pred['family'],solve_completed=rec['solve_completed'],numerical_pass=num,
        design_pass=q['shape'].get('passed'),tuning_status=st,next_suggestion=sug,metrics=metrics_from_extraction(q),
        mesh_cells=rec['mesh_cells'],delta_s=rec['delta_s'],passes=rec['passes'],Analyze_requests=rec['Analyze_requested'],
        native_sha256=done['native_sha256'],final_sweep_history_unchanged=same,role_checks=roles,
        topology=pred['topology'],data_role=pred['data_role'],
        result_level='名义插值；非直接频点/制造/全模式功率认证')
    write(out/'REVIEW_STAGE3.json',summary)
    if pred['material_role']=='lossless_control':
        m=read(w/'evidence/materials_and_boundary.json')
        b=lossless_modal_balance(z,m['lossless_verified'])
        arrays={k:v for k,v in b.items() if isinstance(v,np.ndarray)}
        np.savez_compressed(out/'lossless_modal_balance.npz',**arrays)
        write(out/'POWER_LIMITS.json',{**{k:v for k,v in b.items() if not isinstance(v,np.ndarray)},
            'valid_frequency_count':int(b['valid'].sum()),'total_frequencies':len(fr)})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,5))
    for v,label in ((S[:,0,0],'S11'),(S[:,2,0],'S21')):ax.plot(fr,20*np.log10(np.maximum(abs(v),1e-15)),label=label)
    ax.axhline(-20,color='gray',ls='--',lw=.8);ax.axhline(-2,color='gray',ls=':',lw=.8)
    ax.axvspan(3.92,9.52,color='green',alpha=.07)
    ax.set(xlim=(.01,15),ylim=(-60,3),xlabel='Frequency (GHz)',ylabel='Magnitude (dB)',title=case)
    ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(out/'S11_S21.png',dpi=150);plt.close(fig)
    if not num and not (root/'STOP.json').exists():write(root/'STOP.json',dict(at=now(),case=case,reason='阶段3数值审核失败'))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('role_checks','next_suggestion')},ensure_ascii=False))
    return summary

def finish(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);r=read(w/'review/REVIEW_STAGE3.json')
    ack=read(w/'review/visual_ack.json');q=w/'review/extraction_R2.json'
    if not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png') or ack['extraction_sha256']!=sha(q):raise RuntimeError('实际看图未核验')
    if not r['numerical_pass'] or (root/'STOP.json').exists():raise RuntimeError('数值或停止门槛')
    if r['kind']=='EQ' and not r['tuning_status']['tuned'] and r['next_suggestion']['needs_solve'] and r['attempt_ordinal']<3:raise RuntimeError('仍有授权调参，不提前结项')
    d=dict(at=now(),parent_id=r['parent_id'],selected_case=case,complete=True,
        tuned=r['tuning_status']['tuned'] if r['kind']=='EQ' else None,kind=r['kind'],
        usable_for_law=r['tuning_status']['usable_for_law'] if r['kind']=='EQ' else None,
        review_sha256=sha(w/'review/REVIEW_STAGE3.json'),visual_ack_sha256=sha(w/'review/visual_ack.json'),
        reason='R3调准' if r['tuning_status']['tuned'] else '预算/有限规程内未调准；并非物理不可达')
    write(root/'decisions'/(r['parent_id']+'_FINAL.json'),d)
    return d
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('case');p.add_argument('--finish',action='store_true')
    a=p.parse_args();r=finish(a.root,a.case) if a.finish else review(a.root,a.case)
    if r.get('numerical_pass') is False:raise SystemExit(2)
