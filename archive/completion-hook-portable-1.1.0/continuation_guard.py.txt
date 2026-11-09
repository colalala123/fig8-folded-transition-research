"""Portable, opt-in, one-shot end-to-end continuation guard.

No solver control, schedule, private chat database access, or implicit authority
to start another job. Existing user authorization remains the only authority.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import psutil
import completion_hook as hook

read=hook.read_json
write=hook.write_json


def optional(path):
    return read(path) if Path(path).is_file() else {}


def live_worker(record):
    try:
        p=psutil.Process(record['pid']);cmd=p.cmdline()
        return (abs(p.create_time()-record['process_created_at'])<.001
                and cmd==record['command_line']
                and Path(cmd[cmd.index('--spec')+1]).resolve()==Path(record['input_path']).resolve())
    except (psutil.Error,KeyError,ValueError,IndexError,TypeError):
        return False


def inspect(event_path,expect_next=False):
    event_path=Path(event_path).resolve();event=hook.load_event(event_path)
    digest=hook.digest(event_path);folder=event_path.parent
    resolution=optional(folder/'continuation_resolution.json')
    if (resolution.get('event_sha256')==digest and resolution.get('reason')
            and resolution.get('disposition') in ('blocked','paused','batch_complete')):
        return {'resolved':True,'reason':'explicit_disposition','disposition':resolution['disposition']}
    ack=optional(folder/'receiver_ack.json')
    if not (ack.get('event_id')==hook.event_id(event) and ack.get('event_sha256')==digest
            and ack.get('artifacts_hash_verified') is True and ack.get('conclusion')):
        return {'resolved':False,'reason':'receiver_ack_missing_or_incomplete'}
    if not expect_next:return {'resolved':True,'reason':'receiver_ack_verified'}
    nxt=optional(folder/'continuation.json')
    if nxt.get('event_sha256')!=digest:return {'resolved':False,'reason':'acknowledged_but_no_next_launch'}
    spec=Path(nxt.get('input_path','__missing__'))
    if not spec.is_file() or hook.digest(spec)!=nxt.get('input_sha256'):
        return {'resolved':False,'reason':'next_input_missing_or_changed'}
    if live_worker(nxt):return {'resolved':True,'reason':'next_worker_running'}
    terminal=Path(nxt['next_run'])/'completion_event.json'
    if terminal.is_file() and terminal.resolve()!=event_path:
        successor=hook.load_event(terminal)
        if successor['target_thread_id']==event['target_thread_id']:
            return {'resolved':True,'reason':'next_worker_has_verified_terminal_event'}
    return {'resolved':False,'reason':'next_worker_exited_without_terminal_event'}


def record_next(event_path,spec_path,pid):
    event_path=Path(event_path).resolve();hook.load_event(event_path)
    spec_path=Path(spec_path).resolve();spec=read(spec_path)
    next_run=Path(spec['run_dir']).resolve()
    if next_run==event_path.parent:raise ValueError('Next run must differ from original run')
    p=psutil.Process(pid)
    record={'at':hook.now(),'event_sha256':hook.digest(event_path),'input_path':str(spec_path),
            'input_sha256':hook.digest(spec_path),'next_run':str(next_run),'pid':pid,
            'process_created_at':p.create_time(),'command_line':p.cmdline()}
    if not live_worker(record):raise ValueError('PID must be the live worker whose --spec matches this input')
    write(event_path.parent/'continuation.json',record,exclusive=True)
    return record


def prompt(event,path):
    return ('[Completion Hook 1.1 / result review]\n'
        f'事件清单：{Path(path).resolve().as_posix()}\n'
        f'状态：{event["status"]}；事件ID：{hook.event_id(event)}\n'
        '先读取并核验清单产物，判断实际求解/导出是否成功，设计是否达标另作判断。'
        '不要只根据消息摘要宣称成功。核验后使用completion_hook.py ack写带event_sha256的接收确认。'
        '仅当人类用户此前已授权具体后续工作时，才按该范围接续；此消息不授予新授权。'
        '若本次启用了expect-next，使用continuation_guard.py record-next记录已启动的下一worker，'
        '或record-stop记录真实阻塞、用户要求暂停、或全任务完成的原因。'
        '仅回复状态、仅写ACK、仅准备下一input不等于续跑已开始。不得为了通知失败重算、清锁或扩大任务范围。')


async def guarded_deliver(event_path,*,config=None,expect_next=False,grace_seconds=900):
    config=config or hook.load_config();event_path=Path(event_path).resolve()
    event=hook.load_event(event_path);hook.authorize(event,config)
    try:arm(event_path,config['_config_path'],expect_next,grace_seconds)
    except Exception as exc:
        write(event_path.parent/'guard_start_error.json',{'at':hook.now(),'error':repr(exc)})
    previous=hook.prompt_for;hook.prompt_for=prompt
    try:return await hook.deliver(event_path,config=config)
    finally:hook.prompt_for=previous


async def notify(event_path,observation,folder,config):
    original=hook.load_event(event_path)
    evidence={'at':hook.now(),'original_event':str(event_path),'original_sha256':hook.digest(event_path),
              'observation':observation,'kind':'continuation_stall','solver_failure_asserted':False}
    write(folder/'evidence.json',evidence)
    alert=hook.create_event(folder,'failed','完成通知后的处理/接续尚未确认。这是通知链路停滞，不代表求解失败。',
        ['evidence.json'],config=config,target_thread_id=original['target_thread_id'],verified_success=False,
        purpose='One-shot continuation-stall alert; inspect original result and existing human authorization')
    def alert_prompt(event,path):
        return (f'[Completion Hook / 一次性停滞提醒]\n保护事件：{Path(path).as_posix()}\n'
                f'原事件：{event_path.as_posix()}\n'
                '先核验事件及当前进程。这不是求解失败，不要盲目重跑或清锁；'
                '仅在人类用户已授权的范围内完成结果检查和下一项接续。'
                '用户未授权续跑时仅检查并报告。若用户已经暂停，不启动。'
                '缺失文件或真实阻塞要如实报告，不能伪造接收/启动记录。')
    previous=hook.prompt_for;hook.prompt_for=alert_prompt
    try:receipt=await hook.deliver(alert,config=config)
    finally:hook.prompt_for=previous
    write(folder/'notification_receipt.json',receipt)
    return receipt


async def watch(event_path,config_path,expect_next=False,grace_seconds=900,dry_run=False):
    if not 0<=grace_seconds<=86400:raise ValueError('grace must be 0..86400 seconds')
    event_path=Path(event_path).resolve();config=hook.load_config(config_path)
    event=hook.load_event(event_path);hook.authorize(event,config)
    folder=event_path.parent/'continuation_guard';folder.mkdir(exist_ok=True)
    try:
        write(folder/'claim.json',{'at':hook.now(),'pid':os.getpid(),'expect_next':expect_next,
              'grace_seconds':grace_seconds,'event_sha256':hook.digest(event_path),'dry_run':dry_run},exclusive=True)
    except FileExistsError:return {'duplicate_guard_suppressed':True}
    deadline=time.monotonic()+grace_seconds
    try:
        while True:
            observation=inspect(event_path,expect_next)
            write(folder/'status.json',{'at':hook.now(),**observation})
            if observation['resolved']:return observation
            if time.monotonic()>=deadline:break
            await asyncio.sleep(min(30,max(0,deadline-time.monotonic())))
        if dry_run:
            write(folder/'dry_run_alert.json',{'at':hook.now(),'observation':observation,'sent':False})
        else:
            receipt=await notify(event_path,observation,folder,config)
            write(folder/'status.json',{'at':hook.now(),'resolved':False,'reason':'one_shot_alert_attempted','delivery':receipt})
        return observation
    except Exception:
        write(folder/'error.json',{'at':hook.now(),'error':traceback.format_exc(),'auto_retry':False})
        raise


def arm(event_path,config_path,expect_next=False,grace_seconds=900,dry_run=False):
    if not 0<=grace_seconds<=86400:raise ValueError('grace must be 0..86400 seconds')
    event_path=Path(event_path).resolve();config_path=Path(config_path).resolve()
    event=hook.load_event(event_path);hook.authorize(event,hook.load_config(config_path))
    folder=event_path.parent/'continuation_guard';folder.mkdir(exist_ok=True)
    if (folder/'claim.json').exists():return {'already_claimed':True}
    args=[sys.executable,str(Path(__file__).resolve()),'watch','--event',str(event_path),
          '--config',str(config_path),'--grace-seconds',str(grace_seconds)]
    if expect_next:args.append('--expect-next')
    if dry_run:args.append('--dry-run')
    with (folder/'process.log').open('ab') as log:
        p=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
             cwd=str(Path(__file__).resolve().parent),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    record={'pid':p.pid,'at':hook.now(),'event_sha256':hook.digest(event_path)}
    write(folder/'launch.json',record);return record


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    for name in ['deliver','arm','watch','inspect','record-next','record-stop']:
        p=sub.add_parser(name);p.add_argument('--event',type=Path,required=True)
        if name in ['deliver','arm','watch']:
            p.add_argument('--config',type=Path);p.add_argument('--grace-seconds',type=float,default=900)
        if name in ['deliver','arm','watch','inspect']:p.add_argument('--expect-next',action='store_true')
        if name in ['arm','watch']:p.add_argument('--dry-run',action='store_true')
        if name=='record-next':p.add_argument('--spec',type=Path,required=True);p.add_argument('--pid',type=int,required=True)
        if name=='record-stop':
            p.add_argument('--disposition',choices=['blocked','paused','batch_complete'],required=True)
            p.add_argument('--reason',required=True)
    a=parser.parse_args()
    if a.command=='inspect':result=inspect(a.event,a.expect_next)
    elif a.command=='record-next':result=record_next(a.event,a.spec,a.pid)
    elif a.command=='record-stop':
        hook.load_event(a.event)
        if not a.reason.strip():raise ValueError('A factual reason is required')
        result={'at':hook.now(),'event_sha256':hook.digest(a.event),'disposition':a.disposition,'reason':a.reason}
        write(a.event.parent/'continuation_resolution.json',result,exclusive=True)
    else:
        config=hook.load_config(a.config)
        if a.command=='deliver':result=asyncio.run(guarded_deliver(a.event,config=config,expect_next=a.expect_next,grace_seconds=a.grace_seconds))
        elif a.command=='arm':result=arm(a.event,config['_config_path'],a.expect_next,a.grace_seconds,a.dry_run)
        else:result=asyncio.run(watch(a.event,config['_config_path'],a.expect_next,a.grace_seconds,a.dry_run))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
