"""Exclusive offline evidence generation for R2; no solver or message calls."""
import argparse
from pathlib import Path
from common import HERE, R1, read, write, sha
from portability import compare_typed, regenerate_registry
from presubmit import presubmit
from test_r2 import synthetic_stage1
from analyze_stage1 import analyze


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    frozen=read(R1/'freeze_r1/predictions_frozen.json')['designs']
    actual=regenerate_registry();mismatches=compare_typed(actual,frozen)
    write(out/'REGISTRY_PORTABILITY.json',dict(records=len(frozen),mismatches=mismatches,passed=not mismatches,
          float_rtol=1e-9,float_atol=1e-12,other_types_and_structure='exact',
          frozen_registry_sha256=sha(R1/'freeze_r1/predictions_frozen.json'),
          preserved_R1_test_issue='R1 test_11 uses exact float equality; review Linux/Python3.13 difference was 3.8e-15. R1 test file remains unmodified. This run tests the R2 tolerance, not a new Linux execution.'))
    original=next(r for r in frozen if r['id']=='S3_EQ_N04_04')['geometry_mm']
    tuned={**original,'Ls1':original['Ls1']-.02}
    gate=presubmit(tuned,nominal_a=3.,tuning_changed=True)
    write(out/'PRESUBMIT_EXAMPLE.json',dict(label='SYNTHETIC tuning perturbation, not a new design or solve',
          source='S3_EQ_N04_04',original_geometry_mm=original,synthetic_change='Ls1 minus 0.020mm; all else fixed',result=gate))
    write(out/'PRESUBMIT_INITIAL_79.json',[dict(id=r['id'],result=presubmit(r['geometry_mm'],
          r['geometry_mm']['Ls3']-r['geometry_mm']['Ws'] if r['topology']=='folded' else 0.,
          topology=r['topology'],board_half_x=r['boundary_half_x_mm'])) for r in frozen])
    d=synthetic_stage1();write(out/'STAGE1_SYNTHETIC_INPUT.json',d)
    q=analyze(d);q['evidence']='SYNTHETIC NOT HFSS';write(out/'STAGE1_SYNTHETIC_OUTPUT.json',q)
    print('R2 evidence saved',out.name,'maximal adjusted arm',gate['actual_a_mm'])


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)
