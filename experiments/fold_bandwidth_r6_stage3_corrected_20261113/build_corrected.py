"""派生独立修正版；旧执行文件、输入和账本不改。"""
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'fold_bandwidth_r6_stage3_20261112'
def put(name,s):
    p=HERE/name
    if p.exists():raise RuntimeError('不覆盖 '+name)
    p.write_text(s,encoding='utf-8')
for name in ('common_stage2.py','controller_stage2.py','worker_stage2.py','native_control.py',
             'power_analysis.py','solve_block.py','collect_stage2.py','review_stage3.py','update_status.py','checkpoint_stage2.py'):
    s=(OLD/name).read_text(encoding='utf-8')
    if name in ('collect_stage2.py','update_status.py','checkpoint_stage2.py'):
        s=s.replace("cfg['prior_geometry_total']+len","cfg['prior_geometry_total']+len")
    put(name,s)
s=(OLD/'tuning.py').read_text(encoding='utf-8')
s=s.replace("    a=geometry.slot_boxes # ensure R2 geometry module is loaded; no native operation\n","")
s=s.replace("    subtract=0 if topology=='straight_control' else 2*arm+2*gap+4*ws",
"""    # Use the canonical R2 geometry identity, never a hand-expanded offset.
    subtract=chain.dimensions({**c,'Ls1':.01},topology)['L_centerline_mm']-.01""")
s=s.replace("    sc=presubmit(c,nominal_a,tuning_changed=True,topology=topology)",
"""    desired_lc=chain.wave_length(ws,FS_TARGET,False)-ds
    achieved_lc=chain.dimensions(c,topology)['L_centerline_mm']
    if abs(desired_lc-achieved_lc)>.000500001:
        raise AssertionError('R2中心线反解不变量失败；不允许派发')
    sc=presubmit(c,nominal_a,tuning_changed=True,topology=topology)""")
s=s.replace("target_mean_dB=-20.3,target_P=targetP,",
"""target_mean_dB=-20.3,target_P=targetP,
       length_identity=dict(desired_centerline_mm=desired_lc,
          rounded_candidate_centerline_mm=achieved_lc,error_mm=achieved_lc-desired_lc,
          after_screen_centerline_mm=chain.dimensions(n,topology)['L_centerline_mm'],
          canonical_source='R2 dimensions(); p-4Ws, with Ls2=2Ws+g and Ls3=a+Ws'),""")
put('tuning.py',s)
s=(OLD/'budget_stage2.py').read_text(encoding='utf-8')
s=s.replace("if len(geom)>=42:","if cfg['stage3_prior_geometry']+len(geom)>=42:")
s=s.replace("if sum(x['parent_id']==parent for x in geom)>=",
            "if cfg['prior_parent_geometry'].get(parent,0)+sum(x['parent_id']==parent for x in geom)>=")
put('budget_stage2.py',s)
s=(OLD/'runtime_stage2.py').read_text(encoding='utf-8')
s=s.replace("if cfg['prior_geometry_total']!=100 or cfg['prior_Analyze_total']!=904:raise RuntimeError('历史预算不符')",
"""audit0=read(cfg['prior_stage3_audit'])
    if cfg['prior_geometry_total']!=audit0['cumulative_geometries'] or cfg['prior_Analyze_total']!=audit0['cumulative_Analyze']:
        raise RuntimeError('历史实际预算不符')
    if cfg['stage3_prior_geometry']!=audit0['stage3_geometries']:raise RuntimeError('阶段3成本覆盖不符')""")
s=s.replace("cfg['batch_geometry_limit']!=42","cfg['batch_geometry_limit']!=42-cfg['stage3_prior_geometry']")
s=s.replace("read(root/'decisions'/(prev+'_FINAL.json'))","read(decision_path(root,prev,cfg))")
s=s.replace("old=case_dir(root,parent+f'__T{i-1}',cfg)",
"""base_case=cfg.get('calibration_overrides',{}).get(case,parent+f'__T{i-1}')
            old=prior_dir(root,base_case,cfg)""")
s=s.replace("read(root/'decisions'/(initial['parent']+'_FINAL.json'))",
            "read(decision_path(root,initial['parent'],cfg))")
s=s.replace("from tuning import propose","from tuning import propose\nfrom history_links import prior_dir,decision_path")
put('runtime_stage2.py',s)
s=(OLD/'test_stage3.py').read_text(encoding='utf-8')
s=s.replace("designs={'p':dict(max_Analyze=3 if kind=='EQ' else 1)},prior_geometry_total=100)",
"designs={'p':dict(max_Analyze=3 if kind=='EQ' else 1)},prior_geometry_total=105,stage3_prior_geometry=5,prior_parent_geometry={})")
put('test_stage3.py',s)
print('corrected executor derived')
