"""按R5/R6验证三个基准；只释放1b输入，不启动任何求解。"""
import argparse
import subprocess
from common_r6 import *

def validate(rows,hypothesis,pending_review=False):
    reasons=[]
    if len(rows)!=3 or {r['case'] for r in rows}!=set(BASES):
        reasons.append('三个基准记录不完整或重复')
    for r in rows:
        if r.get('numerical_pass') is not True or r.get('baseline_pass') is not True:
            reasons.append(r['case']+'：数值或基准门槛未过')
        # design_pass=false is meaningful baseline data, NOT a new baseline gate.
    if hypothesis.get('first_role') not in ('-port_adapt','-port_solve') or hypothesis.get('port_preparation_observed') is not True:
        reasons.append('N08首进程未证实端口准备角色')
    if pending_review:reasons.append('存在N14待核实记录')
    return dict(passed=not reasons,reasons=reasons,design_pass_is_not_baseline_gate=True)

def gate(root,release=False):
    if (root/'STOP.json').exists():raise RuntimeError('当前停止记录有效')
    cfg=read(root/'authorization.json')
    rows=[];proof={}
    for case in BASES:
        if case==BASES[0]:
            p=root/'baseline_ref'/case/'REVIEW_R5.json'
            native=p.parent/'full_modes.npz'
        else:
            p=root/'runs'/case/'review/REVIEW_R6.json'
            native=root/'runs'/case/'native/full_modes.npz'
            if not (root/'runs'/case/'done.json').exists() or (root/'runs'/case/'failure.txt').exists():
                raise RuntimeError(case+'缺少成功导出终态')
            if not read(root/'runs'/case/'cleanup.json')['released']:
                raise RuntimeError(case+'的AEDT尚未确认关闭')
        q=read(p)
        if q['native_sha256']!=sha(native):raise RuntimeError(case+'原生曲线哈希不符')
        rows.append(q);proof[case]=dict(review_sha256=sha(p),native_sha256=sha(native))
    hp=root/'runs'/BASES[2]/'evidence/n14_hypothesis_check.json'
    verdict=validate(rows,read(hp),(root/'N14_NEEDS_REVIEW.json').exists())
    report=dict(**verdict,at=now(),baselines=rows,evidence=proof,
                n08_first_role=read(hp),hypothesis_sha256=sha(hp),
                authority='R6接受N04；N14、N08按R5 3.3比较。旧R1内峰0.1dB门槛不再作为判据。',
                total_geometry=cfg['prior_geometry_total']+len(list((root/'ledger').glob('geometry_*.json'))),
                total_Analyze=cfg['prior_Analyze_total']+len(list((root/'ledger').glob('Analyze_*.json'))))
    if release:
        if not report['passed']:raise RuntimeError('1a门槛未过：'+str(report['reasons']))
        if report['total_geometry']>5:raise RuntimeError('1a预算不符')
        current=subprocess.check_output(['git','rev-parse','origin/claude/fold-bandwidth-plan'],cwd=REPO,text=True).strip()
        if current!=cfg['plan_commit']:raise RuntimeError('计划分支有新提交；须先审核，不能沿用旧授权释放')
        if sha(REPO/cfg['plan_path'])!=cfg['plan_sha256']:raise RuntimeError('计划文本变化')
        for p in ('gate_1a.json','release_1b.json'):
            if (root/p).exists():raise RuntimeError('已有释放记录，不重复生成：'+p)
        write(root/'gate_1a.json',report)
        write(root/'release_1b.json',dict(at=now(),authorization_sha256=sha(root/'authorization.json'),
              gate_1a_sha256=sha(root/'gate_1a.json'),plan_commit=current,
              release_script_sha256=sha(Path(__file__)),batch='1b',geometry_limit=9,
              reason='三个基准通过，依据本聊天明确授权及R6 2.4直接进入1b。'))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--release',action='store_true')
    a=p.parse_args()
    print(__import__('json').dumps(gate(a.root.resolve(),a.release),ensure_ascii=False,indent=2))
