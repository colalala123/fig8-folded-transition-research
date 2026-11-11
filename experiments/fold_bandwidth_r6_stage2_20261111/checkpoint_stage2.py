"""2a每十次实际Analyze的只读进度快照，不操作AEDT或派发。"""
import argparse
from common_stage2 import *

def snapshot(root,threshold):
    cfg=read(root/'authorization.json')
    completed=[];states=[]
    for case in cfg['case_paths']:
        w=case_dir(root,case,cfg)
        role=list((w/'evidence').glob('*_role_check.json'))
        for p in role:
            q=read(p)
            if q['passed']:
                stage=p.name.removesuffix('_role_check.json')
                completed.append(dict(case=case,stage=stage,role_check_sha256=sha(p),
                    native_result=read(w/'evidence'/(stage+'_result.json'))))
        if (w/'worker_started.json').exists():
            states.append(dict(case=case,done=(w/'done.json').exists(),failure=(w/'failure.txt').exists(),
                   passed_roles=len([p for p in role if read(p)['passed']])))
    n=cfg['prior_Analyze_total']+len(completed)
    if threshold%10 or threshold<=cfg['prior_Analyze_total'] or n<threshold:raise RuntimeError('尚未到达本批新的十次检查点')
    out=HERE/'checkpoints'/f'Analyze_{threshold:03d}';out.mkdir(parents=True,exist_ok=False)
    report=dict(at=now(),threshold=threshold,prior_closed_Analyze_requests=cfg['prior_Analyze_total'],
        this_batch_validated_completed=len(completed),cumulative_checkpoint_count=n,
        requested_total=cfg['prior_Analyze_total']+len(list((root/'ledger').glob('Analyze_*.json'))),
        geometry_total=cfg['prior_geometry_total']+len(list((root/'ledger').glob('geometry_*.json'))),
        geometry_limits=LIMITS,batch='2a',states=states,completed_this_batch=completed,
        note='历史累计为前批实际请求数；本批完成数只计原生结果及角色核验已闭合的阶段。请求数可能包含在算的下一段，不把Python启动当成HFSS完成。')
    write(out/'SNAPSHOT.json',report)
    lines=['# 阶段2a进度检查点','',
       f"累计检查点计数 {n}，累计实际请求 {report['requested_total']}；几何 {report['geometry_total']}/187。本文件只记录已观察证据，不放行下一点。",'',
       '当前各项状态及全部已闭合阶段见 SNAPSHOT.json。正常求解不发hook、不启动定时聊天。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print({k:v for k,v in report.items() if k not in ('states','completed_this_batch')})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('threshold',type=int);a=p.parse_args();snapshot(a.root.resolve(),a.threshold)
