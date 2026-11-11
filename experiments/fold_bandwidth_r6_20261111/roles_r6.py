"""按 R6 角色核验，保留 -exedir 后的完整无路径命令。"""
import re

ROLES=('-solve_broadband_adapt','-solve','-port_adapt','-port_solve')
def tail_of_command(args):
    full=' '.join(args or [])
    m=re.search(r"""-exedir\s+(?:'[^']*'|"[^"]*"|\S+)\s*(.*)$""",full,re.S)
    return m.group(1).strip() if m else ''

def classify(tail):
    roles=[r for r in ROLES if re.search(r'(?<!\S)'+re.escape(r)+r'(?=\s|$)',tail)]
    role=roles[0] if len(roles)==1 else 'unknown'
    def option(name):
        ms=re.findall(r'(?<!\S)'+re.escape(name)+r'\s+(\d+)(?=\s|$)',tail)
        return int(ms[0]) if len(ms)==1 else None
    return {'role':role,'max_processors':option('-max_processors'),'numParallelGroups':option('-numParallelGroups')}

def evaluate(records,stage):
    errors=[]
    for i,q in enumerate(records):
        c=classify(q['command_tail'])
        if not q['verified_owned_ancestry'] or not q['isolated_scratch']:
            errors.append(f'{i}:归属或临时目录不正确')
        if c['role']=='unknown':errors.append(f'{i}:未识别的命令角色')
        elif c['role']=='-solve_broadband_adapt':
            if c['max_processors']!=14 or c['numParallelGroups']!=1:errors.append(f'{i}:自适应核数或任务组不符')
        elif c['role']=='-solve':
            if c['max_processors'] is None or not 1<=c['max_processors']<=14 or c['numParallelGroups']!=1:
                errors.append(f'{i}:扫频核数或任务组不符')
    counts={r:sum(classify(q['command_tail'])['role']==r for q in records) for r in (*ROLES,'unknown')}
    required='-solve' if stage=='final_sweep' else '-solve_broadband_adapt'
    if not records or not counts[required]:errors.append('缺少该阶段要求的求解进程:'+required)
    return dict(passed=not errors,errors=errors,roles=counts,
                lower_core_sweep_count=sum(classify(q['command_tail'])['role']=='-solve' and classify(q['command_tail'])['max_processors']!=14 for q in records))
