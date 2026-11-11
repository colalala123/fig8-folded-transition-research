"""终态后归集公开结果及中文报告；不启动仿真。"""
import argparse
from collections import Counter
import shutil
from common_r6 import *

def collect(root,case):
    w=root/'runs'/case
    if not (w/'done.json').exists() and not (w/'failure.txt').exists():raise RuntimeError('尚无终态')
    q=read(w/'RUN_RECORD.json')
    cfg=read(root/'authorization.json')
    out=HERE/'results'/case
    out.mkdir(parents=True,exist_ok=False)
    for sub,patterns in [('native',('*.txt','full_modes.npz','full_modes.csv','metadata.json')),('review',('*.json','*.png')),('evidence',('*_role_check.json','*_solver.jsonl','*_result.json','cache_verified.json','n14_hypothesis_check.json','slot_comparison.json'))]:
        for pat in patterns:
            for p in sorted((w/sub).glob(pat)):
                dest=out/sub/p.name;dest.parent.mkdir(exist_ok=True)
                if dest.exists():continue
                shutil.copyfile(p,dest)
    records=[]
    for p in sorted((w/'evidence').glob('*_solver.jsonl')):
        records.extend(__import__('json').loads(x) for x in p.read_text(encoding='utf-8').splitlines())
    counts=Counter(x['role'] for x in records)
    gate=read(w/'review/REVIEW_R6.json') if (w/'review/REVIEW_R6.json').exists() else None
    clean={k:v for k,v in q['cleanup'].items() if k in ('app_created','released','scratch_restored')}
    summary=dict(at=now(),case=case,record={k:v for k,v in q.items() if k!='cleanup'},cleanup=clean,review=gate,roles=dict(counts),
        all_scratch_verified=all(x['isolated_scratch'] for x in records),unknown_role_count=counts['unknown'],
        geometry_total=cfg['prior_geometry_total']+len(list((root/'ledger').glob('geometry_*.json'))),
        actual_Analyze_total=cfg['prior_Analyze_total']+len(list((root/'ledger').glob('Analyze_*.json'))),
        geometry_limit=187,batch1a_limit=5)
    write(out/'SUMMARY.json',summary)
    write(out/'INPUT.json',read(w/'input/freeze.json')['design'])
    text=['# '+case+'：R6仿真结果','']
    if gate and gate['numerical_pass'] and gate['baseline_pass'] is not False:
        text+=['本项已完成求解、数据导出和验收。后续仍按批次门槛推进，不能将本项通过等同于全部完成。','']
    else:
        text+=['本项尚未通过本阶段验收，后续仿真停止。原始结果和失败记录保留，需要按计划检查原因，不能擅自增加求解次数或放宽判据。','']
    text += ['|项目|结果|','|---|---|',
       f"|求解完整完成|{q['solve_completed']}|",f"|数值通过|{q['numerical_pass']}|",
       f"|最终求解单元数|{q.get('mesh_cells')}|",f"|最终ΔS|{q.get('delta_s')}|",
       f"|本几何Analyze总数|{q['Analyze_requested']}|",
       f"|总几何次数|{summary['geometry_total']}/187|",f"|累计Analyze|{summary['actual_Analyze_total']}|"]
    if gate:
        text += [f"|设计名义通过|{gate['design_pass']}|",f"|R5基准通过|{gate['baseline_pass']}|",
                 f"|BW20（GHz）|{gate['metrics']['BW20_GHz']}|"]
        if gate['comparisons']:
            c=gate['comparisons']
            text+=['','基模复数S11、S21相对归档最大差：'+str(c['max_abs_dS11'])+'、'+str(c['max_abs_dS21'])+'。',
                   '中央谷、带宽与内峰的差见 REVIEW_R6.json；内峰电平差仅报告，不沿用已取消的0.1dB门槛。']
    text+=['','进程角色计数：'+str(dict(counts))+'。','数据为名义插值结果，未声称直接频点认证、全模式功率认证或制造公差认证。',
           '原始R4/R5结果不覆盖、不重新标为独立盲测。']
    (out/'REPORT.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    print(__import__('json').dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('case')
    a=p.parse_args();collect(a.root.resolve(),a.case)
