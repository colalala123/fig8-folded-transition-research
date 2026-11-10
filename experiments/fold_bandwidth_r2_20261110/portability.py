"""R2 typed recursive comparison. No relaxation of strings, bools or ints."""
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from common import R1, read


def compare_typed(actual, expected, path='$'):
    if type(actual) is not type(expected):
        return [path+':type']
    if isinstance(expected,dict):
        if actual.keys()!=expected.keys():return [path+':keys']
        return [e for k in expected for e in compare_typed(actual[k],expected[k],path+'.'+k)]
    if isinstance(expected,list):
        if len(actual)!=len(expected):return [path+':length']
        return [e for i,(a,b) in enumerate(zip(actual,expected)) for e in compare_typed(a,b,f'{path}[{i}]')]
    if isinstance(expected,float):
        return [] if math.isfinite(actual) and math.isfinite(expected) and math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-12) else [path+':float']
    return [] if actual==expected else [path+':value']


def regenerate_registry():
    # A fresh interpreter avoids accidentally using R2 chain.bands inside the
    # immutable R1 generator. No existing freeze is overwritten. This invokes
    # ONLY the pinned offline prepare_designs.py, never HFSS or a queue runner.
    with tempfile.TemporaryDirectory(prefix='fig8-r2-registry-') as tmp:
        out=Path(tmp)/'freeze'
        subprocess.run([sys.executable,str(R1/'prepare_designs.py'),'--out',str(out)],
                       check=True,capture_output=True,text=True,encoding='utf-8')
        return read(out/'predictions_frozen.json')['designs']
