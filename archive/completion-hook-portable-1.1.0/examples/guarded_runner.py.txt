"""Use ONLY after user-authorized solver completion and artifact verification."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from completion_hook import create_event,load_config
from continuation_guard import guarded_deliver


async def notify(run_dir,artifacts,summary,*,success,config_path=None,expect_next=False):
    config=load_config(config_path)
    event=create_event(run_dir,'completed' if success else 'failed',summary,artifacts,
                       config=config,verified_success=success)
    # expect_next=True only if the human already authorized subsequent work.
    # Handle errors separately; NEVER restart the solver due to notification error.
    return await guarded_deliver(event,config=config,expect_next=expect_next,grace_seconds=900)
