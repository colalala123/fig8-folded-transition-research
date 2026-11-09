"""Call this AFTER your existing solver runner has exported and verified results.

No solver launch here. No process-exit-only success detection.
Create each event once and keep it immutable; retry delivery, not the simulation.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from completion_hook import create_event, deliver, load_config


async def notify_verified_result(run_dir, artifact_paths, summary, *, config_path=None, success=True):
    config = load_config(config_path)
    event = create_event(run_dir, 'completed' if success else 'failed', summary, artifact_paths,
                         config=config, verified_success=success,
                         purpose='Simulation result ready for inspection; do not automatically rerun')
    # Handle notification errors separately from solver errors. A failed message
    # must never cause Analyze to be called again.
    return await deliver(event, config=config)


# Example insertion in an existing async runner, after its own result checks:
# await notify_verified_result(run_dir, ['metrics.json', 'sparams.csv'],
#                              'Solve and export finished; please inspect the data.')
# For errors first save error.json, then use success=False with that artifact.
