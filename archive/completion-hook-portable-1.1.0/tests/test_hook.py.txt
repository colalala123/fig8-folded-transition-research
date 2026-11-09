import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import completion_hook as hook


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root/'local/config.json'
        hook.init_config(self.config_path, 'test-authorized-thread')
        self.config = hook.load_config(self.config_path)
        self.run = self.root/'run 中文 with spaces'
        self.run.mkdir()
        hook.write_json(self.run/'result.json', {'verified': True, 'value': 42})
        self.path = hook.create_event(self.run, 'completed', 'Test only', ['result.json'], config=self.config,
                                      verified_success=True, run_id='unique-test-run')
        self.event = hook.load_event(self.path)
        self.box = hook.Outbox(Path(self.config['state_dir'])/'outbox.sqlite3')

    def test_duplicate_suppressed(self):
        calls = []
        async def sender(e, p):
            calls.append(e)
            return {'threadId': e['target_thread_id']}
        first = asyncio.run(hook.deliver(self.path, config=self.config, sender=sender))
        second = asyncio.run(hook.deliver(self.path, config=self.config, sender=sender))
        self.assertEqual(first['state'], 'accepted')
        self.assertTrue(second['duplicate_suppressed'])
        self.assertEqual(len(calls), 1)

    def test_timeout_uncertain_no_retry(self):
        calls = []
        async def sender(e, p):
            calls.append(e)
            raise TimeoutError('Unknown outcome')
        with self.assertRaises(TimeoutError):
            asyncio.run(hook.deliver(self.path, config=self.config, sender=sender))
        self.assertEqual(asyncio.run(hook.deliver(self.path, config=self.config, sender=sender))['state'], 'delivery_unknown')
        self.assertEqual(len(calls), 1)

    def test_preflight_failure_stays_pending(self):
        async def unavailable(*args):
            raise ConnectionError('Desktop unavailable')
        with patch.object(hook, 'desktop_session', unavailable):
            with self.assertRaises(ConnectionError):
                asyncio.run(hook.deliver(self.path, config=self.config))
        self.assertEqual(self.box.get(hook.event_id(self.event))['state'], 'pending')

    def test_changed_artifact_rejected(self):
        (self.run/'result.json').write_text('tampered')
        with self.assertRaises(ValueError):
            hook.load_event(self.path)

    def test_missing_artifact_rejected(self):
        (self.run/'result.json').unlink()
        with self.assertRaises(ValueError):
            hook.load_event(self.path)

    def test_traversal_rejected(self):
        self.event['artifacts'][0]['path'] = '../outside.json'
        with self.assertRaises(ValueError):
            hook.validate_event(self.event, self.path)

    def test_absolute_artifact_rejected(self):
        self.event['artifacts'][0]['path'] = str(self.run/'result.json')
        with self.assertRaises(ValueError):
            hook.validate_event(self.event, self.path)

    def test_duplicate_artifact_rejected(self):
        self.event['artifacts'].append(self.event['artifacts'][0].copy())
        with self.assertRaises(ValueError):
            hook.validate_event(self.event, self.path)

    def test_unverified_success_rejected(self):
        self.event['verified_success'] = False
        with self.assertRaises(ValueError):
            hook.validate_event(self.event, self.path)

    def test_wrong_boolean_rejected(self):
        self.event['verified_success'] = 'true'
        with self.assertRaises(ValueError):
            hook.validate_event(self.event, self.path)

    def test_running_rejected(self):
        self.event['status'] = 'running'
        with self.assertRaises(ValueError):
            hook.validate_event(self.event, self.path)

    def test_failure_allowed_with_evidence(self):
        self.event.update(status='failed', verified_success=False)
        self.assertEqual(hook.validate_event(self.event, self.path)['status'], 'failed')

    def test_unauthorized_destination_rejected(self):
        self.event['target_thread_id'] = 'not-authorized'
        hook.write_json(self.path, self.event)
        with self.assertRaises(PermissionError):
            asyncio.run(hook.deliver(self.path, config=self.config))

    def test_conflicting_payload_rejected(self):
        self.box.register(self.path, self.event)
        self.event['summary'] = 'different'
        hook.write_json(self.path, self.event)
        with self.assertRaises(ValueError):
            self.box.register(self.path, self.event)

    def test_atomic_claim(self):
        key = self.box.register(self.path, self.event)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.box.claim(key), range(8)))
        self.assertEqual(sum(results), 1)

    def test_crash_sending_not_retried(self):
        key = self.box.register(self.path, self.event)
        self.box.claim(key)
        self.assertEqual(asyncio.run(hook.deliver(self.path, config=self.config))['state'], 'sending')

    def test_immutable_event(self):
        before = hook.digest(self.path)
        with self.assertRaises(FileExistsError):
            hook.create_event(self.run, 'failed', 'Second event', ['result.json'], config=self.config)
        self.assertEqual(hook.digest(self.path), before)

    def test_config_not_overwritten(self):
        with self.assertRaises(FileExistsError):
            hook.init_config(self.config_path, 'another-thread')

    def test_portable_relative_artifacts(self):
        moved = self.root/'moved space 中文'
        shutil.copytree(self.run, moved)
        self.assertEqual(hook.load_event(moved/'completion_event.json'), self.event)

    def test_missing_pipe_diagnostic(self):
        with patch.dict(os.environ, {'CODEX_MCP_NODE_PATH': sys.executable, 'CODEX_THREAD_ID': 'caller'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'pipe'):
                hook.bridge_paths(self.config)

    def test_changed_during_preflight(self):
        async def change(*args):
            (self.run/'result.json').write_text('changed')
        with patch.object(hook, 'desktop_session', change):
            with self.assertRaises(ValueError):
                asyncio.run(hook.deliver(self.path, config=self.config))
        self.assertEqual(self.box.get(hook.event_id(self.event))['state'], 'pending')

    def test_ack_wrong_event_rejected(self):
        hook.write_json(self.run/'receiver_ack.json', {'event_id': 'wrong'})
        with self.assertRaises(ValueError):
            hook.delivery_status(self.path, self.config)

    def fake_result(self, payload, is_error=False):
        return SimpleNamespace(isError=is_error, structuredContent=None,
                               content=[SimpleNamespace(type='text', text=json.dumps(payload))],
                               model_dump=lambda **kwargs: {'test': True})

    def test_receipt_checks_destination(self):
        self.assertEqual(hook.decode_result(self.fake_result({'threadId':'a'}), 'a'), {'test':True})
        with self.assertRaises(RuntimeError):
            hook.decode_result(self.fake_result({'threadId':'b'}), 'a')

    def test_rejected_receipt(self):
        with self.assertRaises(RuntimeError):
            hook.decode_result(self.fake_result({'threadId':'a','success':False}), 'a')


if __name__ == '__main__':
    unittest.main()
