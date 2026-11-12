"""文件/进程身份快照；不连接AEDT，不派发。CURRENT是可更新进度，不是冻结输入。"""
import argparse,json
from common_stage2 import *
from controller_stage2 import status
def update(root):
    cfg=read(root/'authorization.json');states=[];finished=[]
    for case in cfg['case_paths']:
        w=case_dir(root,case,cfg)
        if (w/'worker_started.json').exists():states.append(status(root,case))
        if (w/'review/REVIEW_STAGE3.json').exists():finished.append(read(w/'review/REVIEW_STAGE3.json'))
    decisions=[read(p) for p in sorted((root/'decisions').glob('*_FINAL.json'))]
    ng=len(list((root/'ledger').glob('geometry_*.json')));na=len(list((root/'ledger').glob('Analyze_*.json')))
    r=dict(at=now(),batch='3',phase='stopped' if (root/'STOP.json').exists() else 'in_progress',
        batch_geometries=ng,batch_geometry_cap=42,cumulative_geometries=100+ng,total_geometry_cap=187,
        batch_actual_Analyze=na,cumulative_actual_Analyze=904+na,
        reviewed=len(finished),numerical_passed=sum(bool(r['numerical_pass']) for r in finished),
        equal_ripple_final=sum(d['kind']=='EQ' for d in decisions),
        equal_ripple_tuned=sum(d['kind']=='EQ' and bool(d['tuned']) for d in decisions),
        completed_controls=sum(d['kind']!='EQ' for d in decisions),states=states,
        no_hook=True,next_stages_conditional=True,stage4_gate='每家族至少4个调准点及对应无耗对照',
        not_all_completed=True)
    public={**r,'states':[{k:v for k,v in s.items() if k!='last_solver'} for s in states]}
    for base in (root,HERE):
        (base/'CURRENT_STATUS.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (base/'CURRENT_STATUS.md').write_text(
           '# 阶段3进度\n\n阶段3已用 '+str(ng)+'/42 个几何，实际 Analyze '+str(na)+' 次；累计几何 '+str(100+ng)+'/187。\n\n'
           +'已审核 '+str(len(finished))+'，等纹波最终调准 '+str(public['equal_ripple_tuned'])+'。阶段4/5尚未放行。\n\n'
           +'保持14核、1组串行，无hook；每个终态必须实际看图后ACK。运行状态详见同目录JSON。\n',encoding='utf-8')
    print(json.dumps(public,ensure_ascii=False))
    return public
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();update(a.root.resolve())
