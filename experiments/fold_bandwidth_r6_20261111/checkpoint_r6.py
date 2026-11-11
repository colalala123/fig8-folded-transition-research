"""只读采集已闭合阶段证据；不连接HFSS、不停止求解。"""
import argparse
import shutil
from collections import Counter
from common_r6 import *

def checkpoint(root,threshold):
    cfg=read(root/'authorization.json')
    stages=[];native_paths=[]
    for folder in sorted((root/'runs').iterdir()):
        for check in sorted((folder/'evidence').glob('*_role_check.json')):
            label=check.name.removesuffix('_role_check.json')
            p=folder/'evidence'/(label+'_result.json')
            if not p.exists():continue
            role=read(check)
            if role['passed'] is not True:continue
            native=folder/'native'/('convergence.txt' if label=='final_sweep' else label+'.txt')
            stages.append(dict(case=folder.name,stage=label,result=read(p),roles=role,
                result_sha256=sha(p),role_sha256=sha(check),convergence_sha256=sha(native)))
            native_paths.append((folder.name,label,native))
    completed=cfg['prior_Analyze_total']+len(stages)
    if completed<threshold:raise RuntimeError('尚未到本次检查点')
    out=HERE/f'checkpoints/Analyze_{threshold:03d}'
    out.mkdir(parents=True,exist_ok=False)
    led=[read(p) for p in sorted((root/'ledger').glob('Analyze_*.json'))]
    q=dict(at=now(),threshold=threshold,historical_Analyze=cfg['prior_Analyze_total'],
        validated_completed_total=completed,requested_total=cfg['prior_Analyze_total']+len(led),
        geometry_total=cfg['prior_geometry_total']+len(list((root/'ledger').glob('geometry_*.json'))),
        geometry_limits=cfg['limits'],total_geometry_limit=187,stages=stages,ledger=led,
        current_human_sweep_confirmation=read(root/'sweep_role_confirmation.json'),
        note='读取的是已闭合的收敛表和角色核验。requested_total可能含正在计算的下一段，不等于已完成总数。')
    write(out/'STATUS.json',q)
    for case,label,p in native_paths:
        dest=out/'convergence'/case/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    rows=['# R6 累计 Analyze 检查点','',
      f"截至本快照：累计已记录请求 {q['requested_total']}，其中历史已结束请求及本轮已核验阶段合计 {completed}；几何次数 {q['geometry_total']}/187。本文件只汇报阶段进度，不把在算项目记作完成，也不代表整批通过。",'',
      '|算例|阶段|单元数|ΔS|角色核验|','|---|---|---:|---:|---|']
    rows += [f"|{s['case']}|{s['stage']}|{s['result']['mesh_cells']}|{s['result']['delta_s']}|通过|" for s in stages]
    rows+=['','R6的14核要求按用户确认分阶段核验；全部已通过的自适应进程14核、1组。最终扫频按1组、≤14核且历史不变核验。没有发送hook消息、改变冻结代码或调用新的Analyze。']
    (out/'REPORT.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    print(__import__('json').dumps({k:v for k,v in q.items() if k not in ('stages','ledger')},ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('threshold',type=int)
    a=p.parse_args();checkpoint(a.root.resolve(),a.threshold)
