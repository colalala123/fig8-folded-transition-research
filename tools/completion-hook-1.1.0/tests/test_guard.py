import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import completion_hook as hook
import continuation_guard as guard


class GuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.config=self.root/'config.json'
        hook.init_config(self.config,'offline-test-only');self.cfg=hook.load_config(self.config)
        self.run=self.root/'run';self.run.mkdir();hook.write_json(self.run/'result.json',{'test':True})
        self.event=hook.create_event(self.run,'completed','Synthetic offline test',['result.json'],config=self.cfg,verified_success=True)

    def ack(self):
        hook.write_json(self.run/'receiver_ack.json',{'event_id':hook.event_id(hook.load_event(self.event)),
           'event_sha256':hook.digest(self.event),'artifacts_hash_verified':True,'conclusion':'Offline fixture checked'})

    def next_record(self):
        nxt=self.root/'next';nxt.mkdir();spec=nxt/'input.json';hook.write_json(spec,{'run_dir':str(nxt)})
        record={'event_sha256':hook.digest(self.event),'input_path':str(spec),'input_sha256':hook.digest(spec),
                'pid':123,'process_created_at':0,'command_line':[],'next_run':str(nxt)}
        hook.write_json(self.run/'continuation.json',record);return nxt,spec

    def test_receipt_not_ack(self):
        hook.write_json(self.run/'notification_receipt.json',{'state':'accepted'})
        self.assertFalse(guard.inspect(self.event)['resolved'])

    def test_ack_default_resolves(self):
        self.ack();self.assertTrue(guard.inspect(self.event)['resolved'])

    def test_ack_not_next(self):
        self.ack();self.assertFalse(guard.inspect(self.event,True)['resolved'])

    def test_live_next(self):
        self.ack();self.next_record()
        with patch.object(guard,'live_worker',return_value=True):self.assertTrue(guard.inspect(self.event,True)['resolved'])

    def test_changed_spec(self):
        self.ack();_,spec=self.next_record();hook.write_json(spec,{'changed':True})
        with patch.object(guard,'live_worker',return_value=True):self.assertFalse(guard.inspect(self.event,True)['resolved'])

    def test_dead_worker_not_progress(self):
        self.ack();self.next_record()
        with patch.object(guard,'live_worker',return_value=False):self.assertFalse(guard.inspect(self.event,True)['resolved'])

    def test_fast_finished_next(self):
        self.ack();nxt,_=self.next_record();hook.write_json(nxt/'result.json',{'test':True})
        hook.create_event(nxt,'completed','Synthetic next',['result.json'],config=self.cfg,verified_success=True)
        with patch.object(guard,'live_worker',return_value=False):self.assertTrue(guard.inspect(self.event,True)['resolved'])

    def test_resolution_bound_to_original(self):
        p=self.run/'continuation_resolution.json'
        hook.write_json(p,{'event_sha256':'stale','disposition':'blocked','reason':'Test fixture'})
        self.assertFalse(guard.inspect(self.event,True)['resolved'])
        r=hook.read_json(p);r['event_sha256']=hook.digest(self.event);hook.write_json(p,r)
        self.assertTrue(guard.inspect(self.event,True)['resolved'])

    def test_failed_event_ack_supported_without_fake_curve_review(self):
        folder=self.root/'failure';folder.mkdir();hook.write_json(folder/'error.json',{'test':'failure'})
        event=hook.create_event(folder,'failed','Synthetic failure',['error.json'],config=self.cfg)
        hook.write_json(folder/'receiver_ack.json',{'event_id':hook.event_id(hook.load_event(event)),
           'event_sha256':hook.digest(event),'artifacts_hash_verified':True,'conclusion':'Failure logs reviewed; no curves available'})
        self.assertTrue(guard.inspect(event)['resolved'])

    async def test_at_most_one_stall_alert(self):
        before=self.event.read_bytes();send=AsyncMock(return_value={'state':'accepted'})
        with patch.object(guard,'notify',send):
            await guard.watch(self.event,self.config,grace_seconds=0)
            await guard.watch(self.event,self.config,grace_seconds=0)
        self.assertEqual(send.await_count,1);self.assertEqual(before,self.event.read_bytes())

    async def test_resolved_does_not_alert(self):
        self.ack()
        with patch.object(guard,'notify',AsyncMock()) as send:await guard.watch(self.event,self.config,grace_seconds=0)
        send.assert_not_awaited()

    async def test_dry_run_never_sends(self):
        with patch.object(guard,'notify',AsyncMock()) as send:await guard.watch(self.event,self.config,grace_seconds=0,dry_run=True)
        send.assert_not_awaited();self.assertTrue((self.run/'continuation_guard/dry_run_alert.json').exists())

    async def test_unknown_send_outcome_not_retried(self):
        send=AsyncMock(side_effect=RuntimeError('unknown outcome'))
        with patch.object(guard,'notify',send):
            with self.assertRaises(RuntimeError):await guard.watch(self.event,self.config,grace_seconds=0)
            await guard.watch(self.event,self.config,grace_seconds=0)
        self.assertEqual(send.await_count,1);self.assertTrue((self.run/'continuation_guard/error.json').exists())

    async def test_guard_failure_does_not_swallow_completion(self):
        with patch.object(guard,'arm',side_effect=RuntimeError('spawn failed')),patch.object(hook,'deliver',AsyncMock(return_value={'state':'accepted'})) as send:
            result=await guard.guarded_deliver(self.event,config=self.cfg)
        self.assertEqual(result['state'],'accepted');send.assert_awaited_once()

    async def test_stall_event_targets_original_thread_and_is_not_solver_failure(self):
        folder=self.run/'alert';folder.mkdir()
        with patch.object(hook,'deliver',AsyncMock(return_value={'state':'accepted'})):
            await guard.notify(self.event,{'resolved':False},folder,self.cfg)
        e=hook.load_event(folder/'completion_event.json');evidence=hook.read_json(folder/'evidence.json')
        self.assertEqual(e['target_thread_id'],'offline-test-only');self.assertFalse(evidence['solver_failure_asserted'])

    def test_record_next_rejects_unrelated_pid(self):
        nxt=self.root/'next';nxt.mkdir();spec=nxt/'input.json';hook.write_json(spec,{'run_dir':str(nxt)})
        with self.assertRaises(ValueError):guard.record_next(self.event,spec,os.getpid())


if __name__=='__main__':unittest.main()
