"""Offline subprocess smoke: no messages, solver, or production configuration."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import completion_hook as hook
import continuation_guard as guard


def main():
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with tempfile.TemporaryDirectory(prefix='hook smoke 中文 ') as temp:
        folder = Path(temp)
        config_path = folder / 'config.json'
        hook.init_config(config_path, 'offline-synthetic-only')
        config = hook.load_config(config_path)
        run = folder / 'first run'
        run.mkdir()
        hook.write_json(run / 'result.json', {'synthetic': True})
        event = hook.create_event(run, 'completed', 'Offline subprocess smoke',
                                  ['result.json'], config=config, verified_success=True)
        original = event.read_bytes()
        guard.arm(event, config_path, grace_seconds=0, dry_run=True)
        alert = run / 'continuation_guard' / 'dry_run_alert.json'
        deadline = time.monotonic() + 20
        while not alert.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        assert alert.exists(), 'Background dry-run did not finish'
        assert hook.read_json(alert)['sent'] is False
        duplicate = asyncio.run(guard.watch(event, config_path, grace_seconds=0, dry_run=True))
        assert duplicate['duplicate_guard_suppressed']
        # Exercise actual CLI serialization of the hash-bound receiver ACK.
        subprocess.run([sys.executable, str(ROOT / 'completion_hook.py'),
                        '--config', str(config_path), 'ack',
                        '--event', str(event), '--conclusion', 'Synthetic artifact checked'],
                       check=True, capture_output=True, creationflags=flags)
        assert guard.inspect(event)['resolved']
        assert not guard.inspect(event, True)['resolved']
        next_run = folder / 'next run'
        next_run.mkdir()
        spec = next_run / 'input.json'
        hook.write_json(spec, {'run_dir': str(next_run)})
        # Base executable avoids Windows venv launcher indirection. Dummy only.
        worker = subprocess.Popen([getattr(sys, '_base_executable', sys.executable),
                                   '-c', 'import time; time.sleep(30)', '--spec', str(spec)],
                                  creationflags=flags)
        try:
            guard.record_next(event, spec, worker.pid)
            assert guard.inspect(event, True)['reason'] == 'next_worker_running'
        finally:
            worker.terminate()
            worker.wait(timeout=10)
        assert guard.inspect(event, True)['reason'] == 'next_worker_exited_without_terminal_event'
        hook.write_json(next_run / 'error.json', {'synthetic': True, 'reason': 'test failure'})
        hook.create_event(next_run, 'failed', 'Synthetic failure terminal', ['error.json'], config=config)
        assert guard.inspect(event, True)['reason'] == 'next_worker_has_verified_terminal_event'
        assert event.read_bytes() == original
        # Allow the completed dry-run child to release its log handles on Windows.
        time.sleep(.5)
    print(json.dumps({'offline_subprocess_smoke': 'passed', 'messages_sent': 0,
                      'solver_started': False, 'unicode_space_paths': True}))


if __name__ == '__main__':
    main()
