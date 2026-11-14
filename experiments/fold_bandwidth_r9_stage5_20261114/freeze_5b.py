"""R9-2 offline once-only refit and deterministic delivery selection; never launch AEDT."""
from prepare_r9 import *
import laws,subprocess
def row_from(q,case,family,group):
    g=q['geometry_mm'];d=chain.dimensions(g);y=state(q);x=coordinate(g,'folded');dx=np.linalg.solve(J0.T,np.array([6.72,0.,-20.3])-y)
    bw=q['bandwidths']['BW15']['BW_GHz']
    return dict(case=case,source='5A solved and reviewed',family=family,group=group,geometry_mm=g,Wm=g['Wm'],a=d['a_mm'],g=d['g_mm'],Lc=d['L_centerline_mm'],y=y.tolist(),target_x=(x+dx).tolist(),local_target_correction=dx.tolist(),balanced_for_bandwidth=True,BW15=bw,BW15_star=bw-.125*(y[2]+20.3),tip_clearance=(g['Ls1']-2*g['Ls3']-max(g['Wm'],1.82))/2)

def build():
    cfg=read(ROOT/'authorization.json')
    if (HERE/'offline_5B').exists():raise RuntimeError('R9-2 already exists')
    ds=[read(ROOT/'decisions'/(p+'_FINAL.json')) for p in cfg['parent_order'][:6]]
    rows=copy.deepcopy(read(HERE/'offline/TRAINING.json')['rows']);added=[];wchoices=[];shapes=[]
    old=read(OLD/'results/S4R8_D8__T2/review/extraction_R2.json')
    from manage import scores
    wchoices.append(dict(case='S4R8_D8__T2',Wm=2.06,BW15_star=scores(old)['BW15_star']))
    for d in ds:
        if not d.get('tuned'):continue
        p=d['parent_id'];c=d['selected_case'];q=read(case_dir(ROOT,c,cfg)/'review/extraction_R2.json');s=spec(ROOT,p,cfg)
        group=s['family']+('_g_ladder' if abs(s['g_mm']-.55)>1e-8 else '_a_ladder')
        rr=row_from(q,c,s['family'],group);rows.append(rr);added.append(c)
        if s['design'].startswith('W'):wchoices.append(dict(case=c,Wm=q['geometry_mm']['Wm'],BW15_star=d['BW15_star']))
        if s['design'] in ('D1c','S1'):shapes.append(dict(case=c,a=s['nominal_a_mm'],g=s['g_mm'],BW15_star=d['BW15_star']))
    for exp,p in [('fold_bandwidth_r6_stage2b_20261112','S2_E2_N04_g1.20'),('fold_bandwidth_r7_3r_20261113','S3R7_N04_a2.6')]:
        base=REPO/'experiments'/exp;d=read(base/'decisions'/(p+'_FINAL.json'))
        if d.get('tuned'):
            q=read(base/'results'/d['selected_case']/'review/extraction_R2.json');dim=chain.dimensions(q['geometry_mm']);shapes.append(dict(case=d['selected_case'],a=dim['a_mm'],g=dim['g_mm'],BW15_star=scores(q)['BW15_star']))
    wm=max(wchoices,key=lambda x:x['BW15_star']);shape=max(shapes,key=lambda x:x['BW15_star']) if shapes else dict(a=2.4,g=.55,case='fallback')
    m=laws.fit(rows);cs=[]
    for name,a,gap in [('B1',1.8,.55),('B2',2.2,.55),('B3',round(shape['a'],3),round(shape['g'],3))]:
        c=laws.candidate(m,name,'Wm'+str(wm['Wm']),wm['Wm'],a,gap,target=np.array([6.72,0.,-20.65]));c.update(kind='EQ',topology='folded',max_Analyze=3,material_role='archived_lossy',board_half_x_mm=15.,target_y=[6.72,0.,-20.65]);cs.append(c)
    write(HERE/'offline_5B/TRAINING.json',dict(rows=rows,new_usable_cases=added,prior_training_sha256=sha(HERE/'offline/TRAINING.json')))
    write(HERE/'offline_5B/LAWS.json',m)
    write(HERE/'offline_5B/REGISTRY.json',dict(at=now(),Wm_star=wm,Wm_candidates=wchoices,B3_shape=shape,B3_candidates=shapes,designs=cs,criterion='research usable highest BW15*; no tuning of widths/shapes in 5B',confirmation_policy='B1 exact selected geometry, >=200k <=240k cells, DeltaS<=0.002, <=20API; no direct points',tolerance_policy='local updated J in Lm,Lc,Ws converted to fixed a/g dimensions Lm,Ls1,Ws; 8 +/-0.02 corners; linear not manufacturing cert'))
    write(HERE/'offline_5B/TEST_RESULTS.json',dict(passed=all(c['screen']['can_submit'] for c in cs),designs_checked=3,caps=[26,177,187]))
    for p in cfg['parent_order'][6:9]:print(attempt(ROOT,p,1))
    (HERE/'R9_2.md').write_text('# R9-2 交付起点冻结\n\n5A后只重拟合这一次。5B结果不回填；不扩大几何或API预算。\n\nWm*='+str(wm)+'\n\nB3分配形状='+str(shape)+'\n\n详细系数、训练身份及三项T1见 offline_5B。冻结推送后才可派发。\n',encoding='utf-8')
def publish():
    if not read(HERE/'offline_5B/TEST_RESULTS.json')['passed']:raise RuntimeError('5B geometry screen failed')
    from manage import publication
    for p in ('B1','B2','B3'):publication(ROOT,'S5R9_'+p+'__T1')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    write(ROOT/'R9_2_PUBLICATION.json',dict(at=now(),commit=commit,hashes={p.relative_to(REPO).as_posix():sha(p) for p in (HERE/'offline_5B').glob('*.json')}))
if __name__=='__main__':
    import sys
    (publish if sys.argv[1]=='publish' else build)()
