"""收集阶段4公开结果；只复制原生证据与脱敏摘要，不上传本机配置。"""
import argparse
import json
import shutil
from collections import Counter
from common_stage2 import *

def collect(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if not (w/'done.json').exists() and not (w/'failure.txt').exists():raise RuntimeError('尚无终态')
    record=read(w/'RUN_RECORD.json')
    out=HERE/'results'/case;out.mkdir(parents=True,exist_ok=False)
    for sub,patterns in [('native',('*.txt','*.npz','full_modes.csv','metadata.json')),
        ('review',('*.json','*.png')),('evidence',('*_role_check.json','*_solver.jsonl','*_result.json','slot_comparison.json','materials_and_boundary.json','geometry_build.json'))]:
        for pat in patterns:
            for p in sorted((w/sub).glob(pat)):
                dest=out/sub/p.name;dest.parent.mkdir(exist_ok=True)
                if not dest.exists():shutil.copyfile(p,dest)
    freeze=read(w/'input/freeze.json');review=read(w/'review/REVIEW_STAGE3.json') if (w/'review/REVIEW_STAGE3.json').exists() else None
    obs=[]
    for p in (w/'evidence').glob('*_solver.jsonl'):
        obs.extend(json.loads(x) for x in p.read_text(encoding='utf-8').splitlines())
    summary=dict(at=now(),case=case,parent_id=freeze['parent_id'],attempt_ordinal=freeze['attempt_ordinal'],
         record={k:v for k,v in record.items() if k!='cleanup'},review=review,
         roles=dict(Counter(x['role'] for x in obs)),
         cleanup={k:v for k,v in record['cleanup'].items() if k in ('app_created','released','scratch_restored')},
         geometry_total=cfg['prior_geometry_total']+len(list((root/'ledger').glob('geometry_*.json'))),
         actual_Analyze_total=cfg['prior_Analyze_total']+len(list((root/'ledger').glob('Analyze_*.json'))),
         geometry_limit=187,batch='4',batch_geometry_used=len(list((root/'ledger').glob('geometry_*.json'))),batch_geometry_limit=24,
         technical_failure=(w/'failure.txt').exists())
    write(out/'SUMMARY.json',summary)
    write(out/'INPUT.json',dict(parent_id=freeze['parent_id'],attempt_ordinal=freeze['attempt_ordinal'],
        design=freeze['design'],expected_boxes=freeze['expected_boxes'],source_hashes=freeze['source_hashes'],
        nominal_a_mm=freeze['nominal_a_mm'],authorization_sha256=freeze['authorization_sha256'],
        previous_extraction_sha256=freeze['previous_extraction_sha256']))
    lines=['# '+case+'：阶段4结果','']
    if review and review['numerical_pass']:
        lines+=['本项已完成原生求解与离线提取。长度调准、理论参数提取唯一性与−20 dB设计达标分别报告；不因为设计负例而更改等纹波规程。','']
    else:
        lines+=['本项未完成数值验收；当前批次停止接续，保留本项证据。需要先按R4/R6处理原因，不能隐式重算。','']
    lines+=['|项目|结果|','|---|---|',f"|求解完成|{record['solve_completed']}|",
      f"|数值通过|{record['numerical_pass']}|",f"|网格|{record.get('mesh_cells')}|",
      f"|ΔS|{record.get('delta_s')}|",f"|实际Analyze请求|{record['Analyze_requested']}|",
      f"|本批几何|{summary['batch_geometry_used']}/24|",f"|累计几何|{summary['geometry_total']}/187|"]
    if review:
        for k,v in review['tuning_status'].items():lines.append(f'|{k}|{v}|')
        lines.append(f"|设计名义通过|{review['design_pass']}|")
    lines+=['','这是名义插值数据，不是直接频点或制造公差认证。直槽对照单独存放，不与旧均匀数据合并；调参后的数据不是独立前瞻测试。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    print(json.dumps({k:v for k,v in summary.items() if k not in ('review','record')},ensure_ascii=False,indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('case');a=p.parse_args();collect(a.root.resolve(),a.case)
