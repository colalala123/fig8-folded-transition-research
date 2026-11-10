"""R5 mesh policy and native stage validation; no AEDT imports."""
import math
import re

LIMITS = {'1a': 4, '1b': 9, '2a': 45, '2b': 66, '3': 42, '4': 8, '5': 12}

class NumericalStop(RuntimeError):
    pass

def history(text):
    rows = [(int(i), int(n), None if d.strip() == 'N/A' else float(d))
            for i,n,d in re.findall(r'^\s*(\d+)\|\s*(\d+)\|\s*([^|\r\n]+)\|', text, re.M)]
    if not rows or [r[0] for r in rows] != list(range(1,len(rows)+1)):
        raise NumericalStop('Missing or non-contiguous adaptive history')
    if any(n <= 0 or (d is None and i != 1) or (d is not None and not (math.isfinite(d) and d >= 0))
           for i,n,d in rows):
        raise NumericalStop('Invalid convergence row')
    return rows

def next_stage(rows):
    if not rows:
        return 'adaptive_00',16,30
    p,n,d = rows[-1]
    if n > 112000:
        raise NumericalStop('Solved Elements exceeds 112000')
    if n >= 100000 and d <= .005:
        return 'final_sweep',p,None
    if p >= 28:
        raise NumericalStop('12 continuation requests used; no more allowed')
    if n > 106000:
        raise NumericalStop('Delta S misses 0.005 above 106000 elements')
    return f'adaptive_{p-15:02d}',p+1,(30 if n < 45000 else 10 if n < 80000 else 5)

def check_transition(before,after,passes,sweep=False):
    if len(after) != passes or after[:len(before)] != before or (sweep and before != after):
        raise NumericalStop('Adaptive history changed or target pass count not met')
    if before and not sweep and (len(after) != len(before)+1 or after[-1][1] <= before[-1][1]):
        raise NumericalStop('Continuation did not add exactly one refined pass')
