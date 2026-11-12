"""停止后的独立只读成本/原始数据复核；不启动AEDT或Analyze。输出必须新目录。"""
import json
from datetime import datetime
import numpy as np
from common_stage2 import *
from history_links import prior_dir,decision_path
from roles_r6 import evaluate as evaluate_roles
from extract_run import extract
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r3_20261110'))
from stage3_metrics import tuned
def audit(root):
    import psutil
    cfg=read(root/'authorization.json');old=Path('F:/2026-1/circuit/test/output/fig8_r6_stage3_20261112/batch')
    oc=read(old/'authorization.json')
    out=HERE/'stop_review';out.mkdir(exist_ok=False)
    checks=[];geos=[];calls=[];intervals=[]
    for origin,config in ((old,oc),(root,cfg)):
        gs=[read(p) for p in (origin/'ledger').glob('geometry_*.json')]
        cs=[read(p) for p in (origin/'ledger').glob('Analyze_*.json')]
        geos+=gs;calls+=cs
        for geo in gs:
            case=geo['case'];w=case_dir(origin,case,config);fz=read(w/'input/freeze.json');rec=read(w/'RUN_RECORD.json')
            if not rec['cleanup']['released']:raise AssertionError('桌面未正常释放')
            ws=read(w/'worker_started.json')
            try:
                p=psutil.Process(ws['pid'])
                if abs(p.create_time()-ws['create_time'])<.01:raise AssertionError('原worker仍在')
            except psutil.NoSuchProcess:pass
            intervals.append((ws['at'],rec['finished_at'],case))
            ledger=[c for c in cs if c['case']==case]
            assert len(ledger)==rec['Analyze_requested']<=14
            assert sorted(c['index'] for c in ledger)==list(range(len(ledger)))
            role={}
            for c in ledger:
                stage=c['stage'];path=w/'evidence'/(stage+'_solver.jsonl')
                obs=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
                role[stage]=evaluate_roles(obs,stage)
                assert role[stage]['passed'],case
            affected=case=='S3R3_EQ_N04_01__T2'
            item=dict(case=case,parent_id=geo['parent_id'],software_affected=affected,
                Analyze=len(ledger),solve_completed=rec['solve_completed'],
                numerical_pass=rec['numerical_pass'],cleanup_released=True,charged_stages_roles_pass=True,
                input_sha256=sha(w/'input/freeze.json'),mesh_cells=rec.get('mesh_cells'),delta_s=rec.get('delta_s'))
            if not affected:
                z=np.load(w/'native/full_modes.npz',allow_pickle=False)
                q=extract(z['f_GHz'],z['S'][:,[0,2],0],read(w/'native/metadata.json'))
                saved=read(w/'review/extraction_R2.json')
                diff=max(abs(q['circuit']['parameters'][k]-v) for k,v in saved['circuit']['parameters'].items())
                assert diff<=1e-8
                assert q['shape']==saved['shape']
                assert q['bandwidths']==saved['bandwidths']
                ack=read(w/'review/visual_ack.json')
                assert ack['actually_viewed'] and ack['plot_sha256']==sha(w/'review/S11_S21.png')
                assert ack['extraction_sha256']==sha(w/'review/extraction_R2.json')
                assert sha(w/'native/full_modes.npz')==read(w/'done.json')['native_sha256']
                assert history((w/'native/pre_final_sweep.txt').read_text(encoding='utf-8-sig'))==history((w/'native/convergence.txt').read_text(encoding='utf-8-sig'))
                assert 100000<=rec['mesh_cells']<=112000 and rec['delta_s']<=.005
                item.update(recomputed_parameter_max_abs_difference=diff,R3=tuned(q),actually_viewed=True,
                    curve_sha256=sha(w/'native/full_modes.npz'),history_unchanged=True)
            else:
                assert rec['solve_completed'] is False and rec['numerical_pass'] is None
                assert len(ledger)==1 and ledger[0]['stage']=='adaptive_00'
                assert history((w/'native/adaptive_00.txt').read_text(encoding='utf-8-sig'))[-1][0]==16
                assert (w/'failure.txt').exists() and not(w/'done.json').exists()
                item['not_HFSS_solve_error']='原生16轮正常返回，因已确认程序缺陷阻止下一次API；不能作设计或数值失败结论。'
            checks.append(item)
    assert len(geos)==6 and len(calls)==57
    assert len({g['case'] for g in geos})==6
    assert len({(c['case'],c['index']) for c in calls})==57
    intervals.sort()
    assert all(datetime.fromisoformat(a[1])<=datetime.fromisoformat(b[0]) for a,b in zip(intervals,intervals[1:]))
    unresolved=[];upper={}
    for family in ('N04','N14'):
        design_ids=[p for p in cfg['parent_order'] if cfg['designs'][p]['kind']=='EQ' and cfg['designs'][p]['family']==family]
        failed=[]
        for parent in design_ids:
            try:p=decision_path(root,parent,cfg)
            except KeyError:continue
            if p.exists():
                d=read(p)
                if not d['tuned']:failed.append(parent)
        upper[family]=5-len(failed);unresolved+=failed
    assert upper['N04']==3 and len(unresolved)==2
    native=[dict(pid=p.pid,name=p.info['name']) for p in psutil.process_iter(['name'])
        if (p.info['name'] or '').lower() in ('ansysedt.exe','hf3d.exe')]
    assert not native,'出现其他原生桌面/求解，停止报告不得认作本批已释放以外的资源控制授权'
    for rel,h in cfg['code_hashes'].items():assert sha(REPO/rel)==h,rel
    report=dict(at=now(),passed=True,stop_reason='阶段3进入阶段4的数量条件在原父项次数上限内已不可达',
        stage3_geometry=6,stage3_geometry_cap=42,stage3_actual_Analyze=57,
        cumulative_geometry=106,cumulative_geometry_cap=187,cumulative_actual_Analyze=961,
        full_numerical_pass=5,controlled_software_stop=1,R3_tuned=0,completed_EQ_parents=2,
        unstarted_EQ_parents=8,lossless_solved=0,boundary_solved=0,
        unresolved_parents=unresolved,maximum_remaining_possible_tuned_by_family=upper,
        required_by_family=4,stage4_gate=False,stage4_started=False,stage5_started=False,
        phase3_not_all_simulated=True,not_physical_impossibility=True,native_processes=native,
        original_frozen_code_unchanged=True,source_case_intervals=intervals,rows=checks)
    write(out/'INDEPENDENT_AUDIT.json',report)
    write(out/'STOP.json',read(root/'STOP.json'))
    return report
if __name__=='__main__':print(json.dumps(audit(Path(sys.argv[1])),ensure_ascii=False,indent=2))
