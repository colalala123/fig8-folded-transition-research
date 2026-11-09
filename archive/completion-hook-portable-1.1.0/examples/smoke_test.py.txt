"""Synthetic event plumbing test, NOT an HFSS simulation. Offline unless --send."""
import argparse
import asyncio
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from completion_hook import HERE, create_event, deliver, load_config, write_json


async def main(args):
    config = load_config(args.config)
    run = (args.run_dir or HERE/'.local'/('smoke-'+uuid.uuid4().hex)).resolve()
    run.mkdir(parents=True, exist_ok=False)
    write_json(run/'synthetic_result.json', {'test': 'synthetic notification plumbing', 'not_hfss': True, 'verified': True})
    event = create_event(run, 'completed', '合成测试事件，结果文件已生成；这不是HFSS仿真。',
                         ['synthetic_result.json'], config=config, verified_success=True,
                         purpose='Portable installation notification test; not scientific data')
    print('Event: ' + str(event), flush=True)
    if args.send:
        await asyncio.sleep(args.delay_seconds)
        print(await deliver(event, config=config), flush=True)
    else:
        print('OFFLINE: no message sent. Use --send only with explicit user permission.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path)
    p.add_argument('--run-dir', type=Path)
    p.add_argument('--send', action='store_true')
    p.add_argument('--delay-seconds', type=float, default=0)
    a = p.parse_args()
    if not 0 <= a.delay_seconds <= 120:
        p.error('Delay must be 0..120 seconds')
    asyncio.run(main(a))
