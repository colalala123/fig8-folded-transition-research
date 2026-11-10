"""New-campaign local stdio AEDT MCP diagnostics. No legacy queue imports.

Discovery is passive. Launch requires R4 authorization, no solver process, and
an exclusive marker. This adapter contains NO Analyze call.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import psutil
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,q):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(q,f,ensure_ascii=False,indent=2,default=str)


@asynccontextmanager
async def client(runtime):
    config=read(runtime/'machine.json');root=Path(config['mcp_root'])
    env={**os.environ,'AEDT_VERSION':'2024.2','AEDT_INSTALL_DIR':config['aedt_install'],
         'AEDT_LOG_DIR':str(runtime/'mcp_logs'),'AEDT_WORKER_TIMEOUT':'120','AEDT_LAUNCH_TIMEOUT':'180'}
    (runtime/'mcp_logs').mkdir(exist_ok=True)
    params=StdioServerParameters(command=sys.executable,args=[str(root/'mcp_server.py')],cwd=str(root),env=env)
    with (runtime/'mcp_logs'/('stdio_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.txt')).open('x',encoding='utf-8') as err:
        async with stdio_client(params,errlog=err) as streams:
            async with ClientSession(*streams,read_timeout_seconds=timedelta(seconds=240)) as session:
                await session.initialize();yield session


async def call(session,name,args):
    r=await session.call_tool(name,args)
    if r.isError:raise RuntimeError(r.model_dump_json())
    if r.structuredContent:return r.structuredContent
    return json.loads(next(c.text for c in r.content if c.type=='text'))


async def run(runtime,action):
    auth=read(runtime/'authorization.json')
    if not auth['execution_authorized'] or auth['total_Analyze_limit']!=185:raise RuntimeError('Authorization mismatch')
    if action=='launch' and (runtime/'STOP.json').exists():
        raise RuntimeError('R4 stopped: launch prohibited; health/discover only')
    async with client(runtime) as session:
        if action=='discover':
            tools=await session.list_tools()
            write(runtime/'mcp_tools.json',{t.name:t.inputSchema for t in tools.tools})
            info=await call(session,'list_aedt_sessions',{})
            write(runtime/'session_discovery.json',dict(at=now(),result=info,Analyze=0))
            print('MCP discovery succeeded; tools:',[t.name for t in tools.tools],flush=True)
            print(json.dumps(info,ensure_ascii=False),flush=True)
        elif action=='health':
            owned=read(runtime/'desktop_lifecycle_recovery_process.json')
            p=psutil.Process(owned['pid'])
            expected=datetime.fromisoformat(owned['creation_time_utc'].replace('Z','+00:00')).timestamp()
            if abs(p.create_time()-expected)>0.01:raise RuntimeError('Desktop PID reused')
            if p.name().lower()!='ansysedt.exe' or p.cmdline()[-2:]!=['-grpcsrv',str(owned['port'])]:
                raise RuntimeError('Desktop command mismatch')
            result=await call(session,'check_aedt_connection',dict(port=owned['port'],timeout=60))
            if result.get('pid')!=owned['pid']:raise RuntimeError('MCP target mismatch')
            write(runtime/('health_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json'),
                  dict(at=now(),result=result,process=dict(pid=p.pid,created=p.create_time(),command=p.cmdline()),Analyze=0))
            print(json.dumps(result),flush=True)
        elif action=='launch':
            if any((p.info['name'] or '').lower()=='hf3d.exe' for p in psutil.process_iter(['name'])):raise RuntimeError('Other solve active')
            write(runtime/'desktop_launch_attempt.json',dict(at=now(),Analyze=0))
            try:
                result=await call(session,'launch_aedt',dict(version='2024.2',port=0,install_dir=read(runtime/'machine.json')['aedt_install'],timeout=180))
                write(runtime/'desktop_launch_result.json',dict(at=now(),result=result))
                print(json.dumps(result),flush=True)
            except BaseException as e:
                write(runtime/'desktop_launch_failure.json',dict(at=now(),error=str(e)));raise
        else:raise ValueError(action)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('action',choices=['discover','launch','health'])
    a=ap.parse_args();asyncio.run(run(a.runtime,a.action))
