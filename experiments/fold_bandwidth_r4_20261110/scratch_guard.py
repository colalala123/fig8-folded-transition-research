"""Use inside the owning PyAEDT worker, never as a second desktop connection."""
from pathlib import Path

def same_path(a,b):return str(Path(a).resolve()).casefold()==str(Path(b).resolve()).casefold()

def configure_scratch(app,target):
    target=Path(target).resolve()
    if not target.is_dir():raise ValueError('Create case scratch directory first')
    previous=str(app.temp_directory)
    if not app.set_temporary_directory(str(target)):raise RuntimeError('SetTempDirectory failed')
    actual=str(app.temp_directory)
    if not same_path(actual,target):raise RuntimeError('AEDT scratch readback mismatch')
    return dict(previous=previous,requested=str(target),actual=actual,verified=True)

def restore_scratch(app,evidence):
    # Do not overwrite someone else's intervening preference change.
    if not same_path(app.temp_directory,evidence['actual']):
        raise RuntimeError('Scratch preference changed externally; not overwriting')
    if not app.set_temporary_directory(evidence['previous']):raise RuntimeError('Scratch restore failed')
    if not same_path(app.temp_directory,evidence['previous']):raise RuntimeError('Scratch restore readback failed')
    return True
