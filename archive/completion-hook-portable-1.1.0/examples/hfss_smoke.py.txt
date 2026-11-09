"""Optional real WR90 test using a recipient-supplied AEDT MCP server.

Requires compatible build_wr90_waveguide/start_analysis/get_analysis_status tools,
licensed AEDT, and an existing visible gRPC session. Never copies sender assets.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import csv
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import time
import traceback
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from completion_hook import create_event, deliver, desktop_session, load_config, now, write_json


@asynccontextmanager
async def aedt_client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = {**os.environ, 'AEDT_VERSION': args.aedt_version, 'AEDT_WORKER_TIMEOUT': '180'}
    if args.aedt_install_dir:
        env['AEDT_INSTALL_DIR'] = str(args.aedt_install_dir.resolve())
    params = StdioServerParameters(command=str(args.mcp_python), args=[str(args.mcp_server.resolve())],
                                  cwd=str(args.mcp_server.resolve().parent), env=env)
    async with stdio_client(params) as streams:
        async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=240)) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            if not {'build_wr90_waveguide', 'start_analysis', 'get_analysis_status'} <= names:
                raise RuntimeError('Incompatible AEDT MCP. Adapt your local runner; do not assume these tool names exist.')
            yield session


async def call(session, name, args):
    result = await session.call_tool(name, args)
    if result.isError:
        raise RuntimeError(result.model_dump_json())
    payload = result.structuredContent or json.loads(next(c.text for c in result.content if c.type == 'text'))
    if payload.get('success') is False or payload.get('error'):
        raise RuntimeError(str(payload))
    return payload


def solvers():
    import psutil
    return [p.info for p in psutil.process_iter(['pid', 'name', 'cmdline']) if (p.info['name'] or '').lower() == 'hf3d.exe']


def export(folder, project, args):
    import numpy as np
    from ansys.aedt.core import Hfss
    app = Hfss(project=project, design='WR90_TE10', version=args.aedt_version, machine='localhost',
               port=args.port, non_graphical=False, new_desktop=False, close_on_exit=False)
    try:
        messages = list(app.odesktop.GetMessages(app.project_name, app.design_name, 0))
        write_json(folder/'hfss_messages.json', messages)
        if app.are_there_simulations_running or not app.get_setup('Setup1').is_solved or not any('Normal completion' in m for m in messages):
            raise RuntimeError('Missing normal solve completion evidence')
        expressions = ['S(WavePort1:1,WavePort1:1)', 'S(WavePort2:1,WavePort1:1)']
        data = app.post.get_solution_data(expressions=expressions, setup_sweep_name='Setup1 : Sweep8to12GHz', primary_sweep_variable='Freq')
        if not data:
            raise RuntimeError('No S-parameter result')
        f = np.array(data.primary_sweep_values, dtype=float)*{'Hz':1e-9,'kHz':1e-6,'MHz':1e-3,'GHz':1}[data.units_sweeps['Freq']]
        s11, s21 = [np.asarray(data.get_expression_data(e, formula='real')[1], dtype=float)
                    +1j*np.asarray(data.get_expression_data(e, formula='imag')[1], dtype=float) for e in expressions]
        if len(f) != 81 or not np.allclose(f, np.linspace(8,12,81)) or not np.isfinite(np.r_[s11,s21]).all():
            raise RuntimeError('Incomplete or invalid sweep data')
        with (folder/'sparams.csv').open('w', encoding='utf-8', newline='') as out:
            writer = csv.writer(out)
            writer.writerow(['Freq_GHz','S11_real','S11_imag','S21_real','S21_imag'])
            writer.writerows(zip(f,s11.real,s11.imag,s21.real,s21.imag))
        d11 = 20*np.log10(np.maximum(abs(s11),1e-300))
        d21 = 20*np.log10(np.maximum(abs(s21),1e-300))
        metrics = {'points':81, 'max_S11_dB':float(d11.max()), 'S21_dB_range':[float(d21.min()),float(d21.max())],
                   'passed':bool(d11.max() < -20 and abs(d21).max() < .1)}
        write_json(folder/'metrics.json',metrics)
        app.export_convergence('Setup1', output_file=str(folder/'convergence.txt'))
        app.save_project()
        if not metrics['passed']:
            raise RuntimeError('WR90 result sanity check failed')
        return metrics
    finally:
        app.release_desktop(close_projects=False, close_desktop=False)


async def main(args):
    config = load_config(args.config)
    if not args.mcp_server.is_file():
        raise ValueError('Provide your own compatible AEDT MCP server script')
    if solvers():
        raise RuntimeError('Existing HFSS solve detected; no concurrent test started')
    if args.send:
        await desktop_session('probe', config)
    folder = args.run_dir.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    project = 'HookWR90_' + uuid.uuid4().hex[:10]
    state = {'status':'building','project':project,'started_at':now(),'requested_cores':args.cores,'tasks':1,'observed_solvers':[]}
    write_json(folder/'state.json', state)
    status, summary = 'failed', ''
    try:
        async with aedt_client(args) as session:
            state['build'] = await call(session,'build_wr90_waveguide',{'port':args.port,'project_name':project,
                'design_name':'WR90_TE10','output_dir':str(folder),'solve':False,'timeout':180})
            target = {'port':args.port,'project_name':project,'design_name':'WR90_TE10','setup_name':'Setup1','timeout':120}
            state['start_response'] = await call(session,'start_analysis',{**target,'concurrent_tasks':1,'cores_per_task':args.cores,'blocking':False})
            if not state['start_response'].get('started'):
                raise RuntimeError('MCP did not confirm solver start')
            state['status'] = 'solving'
            start = time.monotonic()
            while True:
                await asyncio.sleep(3)
                live = solvers()
                if live and (not state['observed_solvers'] or state['observed_solvers'][-1] != live):
                    state['observed_solvers'].append(live)
                current = await call(session,'get_analysis_status',target)
                state.update(last_status=current, updated_at=now())
                write_json(folder/'state.json',state)
                if not live and not current.get('running'):
                    break
                if time.monotonic()-start > 1200:
                    raise TimeoutError('Monitor timed out; solver may still be running. No kill or automatic rerun.')
        metrics = export(folder,project,args)
        state['actual_core_command_observed'] = any(f'-max_processors {args.cores}' in ' '.join(p['cmdline'] or [])
            and '-numParallelGroups 1' in ' '.join(p['cmdline'] or []) for obs in state['observed_solvers'] for p in obs)
        status = 'completed'
        summary = 'WR90求解和结果校验完成：' + json.dumps(metrics,ensure_ascii=False)
    except Exception as exc:
        write_json(folder/'error.json',{'error':str(exc),'traceback':traceback.format_exc(),'live_solvers':solvers()})
        summary = 'WR90测试任务失败或未完成结果校验；不要当作成功：' + str(exc)
    state.update(status=status,finished_at=now())
    write_json(folder/'state.json',state)
    artifacts = [p.name for p in folder.iterdir() if p.is_file() and p.name in
                 {'state.json','sparams.csv','metrics.json','convergence.txt','error.json','hfss_messages.json'}]
    event = create_event(folder,status,summary,artifacts,config=config,verified_success=status=='completed',
                         purpose='Independent WR90 completion-hook test, not production research data')
    print('Event: '+str(event),flush=True)
    if args.send:
        print(await deliver(event,config=config),flush=True)
    else:
        print('No notification sent; explicit --send was not provided.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--mcp-server',type=Path,required=True)
    p.add_argument('--mcp-python',default=sys.executable)
    p.add_argument('--aedt-version',default='2024.2')
    p.add_argument('--aedt-install-dir',type=Path)
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--cores',type=int,default=16)
    p.add_argument('--send',action='store_true')
    a = p.parse_args()
    if a.cores < 1:
        p.error('--cores must be positive')
    asyncio.run(main(a))
