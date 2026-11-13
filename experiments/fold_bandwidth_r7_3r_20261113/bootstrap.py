"""Offline versioned copy of validated numerical executor; never alters old code."""
from pathlib import Path
import shutil
H=Path(__file__).resolve().parent
OLD=H.parent/'fold_bandwidth_r6_stage3_corrected_20261113'
for name in ['common_stage2.py','controller_stage2.py','worker_stage2.py','budget_stage2.py','solve_block.py','native_control.py','power_analysis.py','review_stage3.py','collect_stage2.py','checkpoint_stage2.py']:
    if (H/name).exists():raise RuntimeError('refuse overwrite '+name)
    shutil.copyfile(OLD/name,H/name)
