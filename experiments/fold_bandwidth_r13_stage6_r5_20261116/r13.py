"""Finite R13 cache-sweep authorization, immutable preparation and labels.

Import is offline. R1-R4 remain read-only. No sweep/adaptive dispatch here.
"""
import argparse,copy,math,shutil
import re
from common_stage2 import *
import prepare_r10 as prep,cad_ir
from recovery_r5 import cache_files

PRIOR_H=REPO/'experiments/fold_bandwidth_r12_stage6_r4_20261115'
PRIOR_R=Path('F:/2026-1/circuit/test/output/fig8_r12_stage6_r4_20261115')
SOURCE=PRIOR_R/'runs/S6R10_B1Rdense/attempt_001'
CACHE_CASE='S6R10_B1Rdense__T1'
PLAN='docs/PLAN_20261115_FOLD_BANDWIDTH_R13.md'
RESIDUAL=.0023507
GAMMA=lambda d:10.**(d/20.)

class CacheUnavailable(RuntimeError):pass

def sweep_section(project,enabled=True):
    from headless_worker_r5 import model_block
    t=model_block(Path(project).read_text(encoding='utf-8')).group()
    t=re.search(r"\$begin 'Setup19'.*?\$end 'Setup19'",t,re.S).group()
    t=re.search(r"\$begin 'Sweep1'.*?\$end 'Sweep1'",t,re.S).group()
    return re.sub(r'(?m)^(\s*IsEnabled=)(?:true|false)\s*$',lambda m:m[1]+str(enabled).lower(),t)

def verify_history(rows,cfg):
    expected=[tuple(x) for x in cfg['cache_history']]
    if rows!=expected or len(rows)!=27 or rows[-1]!=(27,247756,RESIDUAL):
        raise RuntimeError('R13 retained 27-row history changed; result invalid, no retry')
    return True

def verify_sweep_roles(obs):
    from roles_r6 import evaluate,classify
    r=evaluate(obs,'final_sweep')
    if not r['passed'] or any(classify(x['command_tail'])['role'] not in ('-solve','-port_solve') for x in obs):
        raise RuntimeError('R13 sweep-only role integrity failed; adaptive role forbidden')
    return r

def verify_cache_input(root,f,cfg):
    stop=read(PRIOR_R/'STOP.json')
    eligible=(cfg['execution_revision']=='R13_STAGE6_R5' and cfg['human_authorized'] and
        cfg['plan_commit']=='0c55fdc' and sha(REPO/PLAN)==cfg['plan_hashes'][PLAN] and
        cfg['cache_stop_sha256']==sha(PRIOR_R/'STOP.json') and stop['case']==CACHE_CASE and
        stop['record']['Analyze_requested']==12 and stop['record']['numerical_pass'] is False and
        f['resume'] is True and f['inherited_Analyze']==12 and f['logical_case']==CACHE_CASE and
        f['cache_source_manifest_sha256']==sha(HERE/'freeze/CACHE_MANIFEST.json') and
        f['design']==read(SOURCE/'input/freeze.json')['design'])
    if not eligible:raise RuntimeError('Only the explicitly authorized R12 STOP may enter sweep-only')
    verify_history([tuple(x) for x in cfg['cache_history']],cfg)
    return True

def audit_cache_files(w,cfg):
    if any(w.rglob('*.lock')):raise CacheUnavailable('Retained cache has a lock; do not delete it')
    if cache_files(w)!=read(HERE/'freeze/CACHE_MANIFEST.json'):raise CacheUnavailable('Retained cached project/results bytes differ')
    return True

def charge_sweep(root,case,label,record,freeze,cfg):
    verify_cache_input(root,freeze,cfg)
    ledger=root/'ledger'
    if label!='final_sweep' or record['Analyze_requested']!=12 or list(ledger.glob('Analyze_'+case+'_*.json')):
        raise RuntimeError('R13 exactly one final sweep; no duplicate/adaptive/retry')
    if (SOURCE/'RUN_RECORD.json').is_file() and read(SOURCE/'RUN_RECORD.json')['Analyze_requested']!=12:
        raise RuntimeError('Historical request count changed')
    write(ledger/f'Analyze_{case}_12.json',dict(at=now(),case=case,logical_case=CACHE_CASE,parent_id='S6R10_B1Rdense',
        batch='6',index=12,stage='final_sweep',cores=14,tasks=1,dense_confirmation=True,
        retained_Analyze=12,physical_geometry_Analyze_after=13,new_geometry_charged=False,
        source_STOP_sha256=cfg['cache_stop_sha256']))
    record['Analyze_requested']=13

def native_cache_geometry(app,pred):
    """Read native geometry, material, ports, union vertices; zero edits."""
    import native_control as nc
    ir=pred['cad_ir'];objects=nc.snapshot(app)
    vv={n:[[float(x) for x in app.oeditor.GetVertexPosition(v)] for v in app.oeditor.GetVertexIDsFromObject(n)] for n in ('Substrate_7','Substrate_9')}
    ports=nc.saved_ports(app.project_file,app.design_name);d={}
    for n in ('Substrate_1','Substrate_2'):
        m=app.materials[objects[n]['material']];d[n]=dict(er=float(m.permittivity.value),tand=float(m.dielectric_loss_tangent.value))
    proof=nc.validate_observed(ir,objects,vv,ports,d)
    return dict(cad_ir=ir,native_acceptance=proof,native_ground_vertices=vv,native_ports=ports,
        read_only_no_geometry_edits=True,materials_and_boundary=dict(after=objects,dielectric_readback=d,new_Analyze=0))

def confirmation(nominal,dense,corner,a):
    highest=lambda m:max(m['low_peak_dB'],m['high_peak_dB'])
    gn=GAMMA(highest(nominal));gd=GAMMA(highest(dense)) if dense is not None else None
    gc=GAMMA(highest(corner)) if corner is not None else None
    limit=a['statistical_dense_Gamma_limit']
    own=max(0.,gd-gn) if gd is not None else None
    stat=None if gd is None else ('统计稳健（含网格残差）' if gd+RESIDUAL<=limit else '统计稳健（不含网格残差，边缘）' if gd<=limit else '不满足统计稳健')
    bias=own if gd is not None else .00276
    worst=None if gc is None else gc+bias<=.1
    corner_label=None if gc is None else ('最坏角点稳健' if worst and gd is not None else '最坏角点稳健（借用 B1 的网格偏差，未经本设计确认）' if worst else '最坏角点不满足')
    return dict(statistical_label=stat,Gamma_dense=gd,DeltaS_residual=RESIDUAL,Gamma_stat=limit,
        statistical_with_residual=None if gd is None else gd+RESIDUAL<=limit,
        statistical_without_residual=None if gd is None else gd<=limit,
        statistical_including_residual_dB_limit=20*math.log10(limit-RESIDUAL),
        own_nonnegative_mesh_dGamma=own,corner_bias_used=bias,corner_bias_source='own_B1R' if gd is not None else 'borrowed_B1_unconfirmed',
        Gamma_C1R=gc,corner_Gamma_plus_bias=None if gc is None else gc+bias,
        worst_corner_robust=worst,worst_corner_label=corner_label,
        corner_minus_nominal_dGamma=None if gc is None else gc-gn,
        dense_minus_T3_peak_dB=None if dense is None else {k:dense[k]-nominal[k] for k in ('low_peak_dB','high_peak_dB')},
        dense_minus_T3_peak_dGamma=None if dense is None else {k:GAMMA(dense[k])-GAMMA(nominal[k]) for k in ('low_peak_dB','high_peak_dB')},
        adaptive_converged=False,not_a_manufacturing_yield_or_direct_frequency_certificate=True)

def offline():
    plan=(REPO/PLAN).read_text(encoding='utf-8')
    rows=history((SOURCE/'native/adaptive_11.txt').read_text(encoding='utf-8-sig'))
    if len(rows)!=27 or rows[-1]!=(27,247756,RESIDUAL):raise RuntimeError('wrong stopped history')
    manifests=cache_files(SOURCE)
    write(HERE/'freeze/CACHE_MANIFEST.json',manifests)
    s=read(SOURCE/'evidence/adaptive_11_settings.json');t=read(PRIOR_R/'runs/S6R10_B1R/attempt_003/evidence/final_sweep_settings.json')
    expected={**t['sweep'],'IsEnabled':True}
    if {**s['sweep'],'IsEnabled':True}!=expected:raise RuntimeError('Sweep settings not identical to nominal T3')
    write(HERE/'freeze/R13_R5.json',dict(at=now(),status='R13_R5_PRE_SOLVE_FREEZE',plan_commit='0c55fdc',
        Q25_Q26_verbatim=plan.split('## 4. 新登记的预测')[1].split('## 5. 报告')[0],
        inherited_Q23_Q24=read(HERE/'freeze/R12_R4.json')['Q21_Q24_verbatim'],
        inherited_Q16='W3 可用时 BW15* 在 6.90–6.99 GHz，即 2.35–2.5 mm 段斜率低于 1.1 GHz/mm；≥7.00 为仍不弯，不可用则不可判',
        cache_history=rows,source_STOP_sha256=sha(PRIOR_R/'STOP.json'),source_input_sha256=sha(SOURCE/'input/freeze.json'),
        source_cache_manifest_sha256=sha(HERE/'freeze/CACHE_MANIFEST.json'),
        source_adaptive_settings={**s['setup'],'PercentRefinement':s['percent']},
        nominal_T3_final_sweep=expected,cache_final_sweep=expected,
        nominal_T3_full_sweep_section=sweep_section(PRIOR_R/'runs/S6R10_B1R/attempt_003/model.aedt'),
        retained_cache_full_sweep_section_enabled=sweep_section(SOURCE/'model.aedt'),
        final_sweep_all_saved_properties_policy='Only frozen seven sweep fields are updated; all other native Sweep1 fields retained and separately audited. No adaptive setup update on cache path.',
        budget=dict(prior_geometry=193,prior_Analyze=1846,new_geometry_cap=4,max_cumulative_geometry=197,
            absolute_geometry_cap=200,cache_new_Analyze=1,cache_physical_after=13,ordinary_cap=14),
        h0_mm=.813,tol_h_mm=.038,no_hook=True,no_direct_points=True,no_stage7=True,
        independent_steps_numerical_missing_continue=True,strict_integrity_error_stops=True))

def prepare_r5(root):
    if root.exists():raise RuntimeError('R5 already exists; never reset')
    if not read(HERE/'freeze/OFFLINE_TESTS.json')['passed']:raise RuntimeError('tests missing')
    cfg=copy.deepcopy(read(PRIOR_R/'authorization.json'));st=read(PRIOR_H/'CURRENT_STATUS.json')
    if (st['geometry_total'],st['actual_Analyze_total'])!=(193,1846):raise RuntimeError('prior cost mismatch')
    if len(list((PRIOR_R/'ledger').glob('geometry_*.json')))!=4 or len(list((PRIOR_R/'ledger').glob('Analyze_*.json')))!=39:raise RuntimeError('R4 ledger mismatch')
    for rel,h in read(PRIOR_H/'STOP_MANIFEST.json').items():
        if sha(PRIOR_H/rel)!=h:raise RuntimeError('R4 archive changed '+rel)
        cfg['historical_hashes'][str(PRIOR_H/rel)]=h
    for p in [PRIOR_H/'STOP_MANIFEST.json',PRIOR_R/'STOP.json',PRIOR_R/'authorization.json',SOURCE/'input/freeze.json',SOURCE/'RUN_RECORD.json',SOURCE/'cleanup.json',*list((PRIOR_R/'ledger').glob('*.json'))]:cfg['historical_hashes'][str(p)]=sha(p)
    for d in st['completed_parents']:
        c=d['selected_case']
        if (PRIOR_H/'results'/c).exists():cfg['inherited_public_result_paths'][c]=(PRIOR_H/'results'/c).relative_to(REPO).as_posix()
    cfg.update(at=now(),human_authorized=True,execution_revision='R13_STAGE6_R5',plan_commit='0c55fdc',
        user_authorization='Human accepts R13 section0: finite new R5, one cache-only sweep, C1R and 6C independent on numerical failure; strict integrity stop; then report',
        prior_geometry_total=193,prior_Analyze_total=1846,batch_geometry_limit=4,total_geometry_limit=200,
        inherited_stage6_geometry=20,inherited_stage6_Analyze=213,full_stage6_geometry_limit=27,
        inherited_geometry_logicals=[CACHE_CASE],inherited_logical_Analyze={CACHE_CASE:12},
        inherited_closed_parents=['S6R10_B1R'],case_paths={},case_specs={},required_preflight_cases=[],
        parent_order=['S6R10_B1Rdense','S6R10_C1R','S6R10_W3','S6R10_W4'],
        cache_case=CACHE_CASE,cache_source=str(SOURCE),cache_stop_sha256=sha(PRIOR_R/'STOP.json'),
        cache_history=read(HERE/'freeze/R13_R5.json')['cache_history'],
        technical_recovery_policy='No retries or automatic R6. Numerical missing continues independent steps; CAD/native/role/foreign process/hash/budget errors stop.',
        batch_max_Analyze_from_geometry_caps=57,full_stage6_max_Analyze_from_geometry_caps=270)
    nominal=read(PRIOR_H/'results/S6R10_B1R__T3/INPUT.json')['design']
    dense=read(SOURCE/'input/freeze.json')['design']
    c=copy.deepcopy(nominal);c.update(id='S6R10_C1R',design='C1R',kind='CONTROL',tuning=None,data_role='B1R_measured_worst_corner')
    changes=read(HERE/'freeze_6B/R10_2.json')['corner_changes'];ir=cad_ir.json_value(cad_ir.build(nominal['geometry_mm'],**changes,port_policy='clip_cut_faces',h_port_policy='height_8h_width_fixed'))
    c.update(cad_ir=ir,base_geometry_mm=nominal['geometry_mm'],geometry_mm=ir['geometry_mm'],nominal_a_mm=prep.chain.dimensions(ir['geometry_mm'])['a_mm'])
    from presubmit import presubmit
    c['screen']=presubmit(c['geometry_mm'],c['nominal_a_mm'],tuning_changed=False)
    cfg['designs']['S6R10_C1R']=prep.decorate(c)
    cfg['designs']['S6R10_B1Rdense']=dense
    for n in ('W3','W4'):cfg['designs']['S6R10_'+n]=prep.decorate(cfg['designs']['S6R10_'+n],'EQ')
    for n,ii in [('B1Rdense',[1]),('C1R',[1]),('W3',[4]),('W4',[1,2])]:
        par='S6R10_'+n
        for i in ii:
            case=par+f'__T{i}';cfg['case_paths'][case]=f'runs/{par}/attempt_{i:03d}';cfg['case_specs'][case]=dict(parent_id=par,attempt_ordinal=i,numerical_retry=False)
    cfg['plan_hashes'][PLAN]=sha(REPO/PLAN)
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    cfg['frozen_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for folder in ('freeze','offline','freeze_6B') for p in (HERE/folder).glob('*.json')})
    root.mkdir();(HERE/'pre_solve').mkdir()
    for n in ('ledger','decisions','model_freeze','publications','preflights'):(root/n).mkdir()
    write(root/'authorization.json',cfg);shutil.copyfile(PRIOR_R/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    shutil.copyfile(PRIOR_R/'decisions/S6R10_B1R_FINAL.json',root/'decisions/S6R10_B1R_FINAL.json')
    w=case_dir(root,CACHE_CASE,cfg)
    for n in ('input','native','evidence'):(w/n).mkdir(parents=True)
    f=dict(at=now(),parent_id='S6R10_B1Rdense',attempt_ordinal=1,logical_case=CACHE_CASE,numerical_retry=False,design=dense,
        nominal_a_mm=dense['nominal_a_mm'],expected_boxes=dense['cad_ir']['expected_slot_boxes'],
        source_hashes=read(SOURCE/'input/freeze.json')['source_hashes'],authorization_sha256=sha(root/'authorization.json'),
        resume=True,inherited_Analyze=12,previous_extraction_sha256=None,solver_started=False,
        cache_source_manifest_sha256=sha(HERE/'freeze/CACHE_MANIFEST.json'))
    for dest in (w/'input/freeze.json',root/'model_freeze'/(CACHE_CASE+'.json'),HERE/'pre_solve'/(CACHE_CASE+'.json')):write(dest,f)
    return dict(prepared=True,cache_not_cloned_yet=True)

def clone_cache(root):
    cfg=read(root/'authorization.json');w=case_dir(root,CACHE_CASE,cfg)
    verify_cache_input(root,read(w/'input/freeze.json'),cfg)
    audit_cache_files(SOURCE,cfg)
    if (w/'model.aedt').exists() or (w/'model.aedtresults').exists():raise RuntimeError('cache clone exists; no overwrite')
    shutil.copyfile(SOURCE/'model.aedt',w/'model.aedt');shutil.copytree(SOURCE/'model.aedtresults',w/'model.aedtresults')
    audit_cache_files(w,cfg);audit_cache_files(SOURCE,cfg)
    write(w/'evidence/CACHE_CLONED.json',dict(at=now(),manifest_sha256=sha(HERE/'freeze/CACHE_MANIFEST.json'),byte_identical=True,source_unchanged=True))

def missing(root,case,reason):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if (root/'STOP.json').exists():raise RuntimeError('strict STOP cannot be bypassed')
    if (w/'RUN_RECORD.json').exists() and read(w/'RUN_RECORD.json')['numerical_pass'] is not False:raise RuntimeError('not a numerical missing result')
    p=cfg['case_specs'][case]['parent_id']
    d=dict(at=now(),parent_id=p,complete=True,passed=False,missing=True,selected_case=None,reason=reason,independent_next_step_allowed=True)
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):dest.parent.mkdir(exist_ok=True);write(dest,d)
    return d

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['offline','prepare','clone','missing']);p.add_argument('case',nargs='?');a=p.parse_args()
    print(offline() if a.command=='offline' else prepare_r5(prep.ROOT) if a.command=='prepare' else clone_cache(prep.ROOT) if a.command=='clone' else missing(prep.ROOT,a.case,'R13 one-shot numerical missing; no retry'))
