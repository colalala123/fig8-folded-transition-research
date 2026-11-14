"""R9 isolated immutable authorization and offline freeze/candidates. No AEDT API."""
import copy,shutil,argparse
from common_stage2 import *
from tuning import *
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r9_stage5_20261114')
OLDROOT=Path('F:/2026-1/circuit/test/output/fig8_r8_stage4_20261114')
OLD=REPO/'experiments/fold_bandwidth_r8_stage4_20261114'
ORDER=['W1','W2','W3','D1c','D3c','S1','B1','B2','B3','B1dense']

def historical(p):
    if p not in ('S5R9_D1c','S5R9_D3c'):return []
    old='S4R8_D1' if p.endswith('D1c') else 'S4R8_D3'
    return [dict(case=old+f'__T{i}',q=read(OLD/'results'/(old+f'__T{i}')/'review/extraction_R2.json'),tuning=None) for i in (1,2,3)]

def histories(root,p,cfg):
    out=historical(p)
    for c,s in cfg['case_specs'].items():
        if s['parent_id']!=p:continue
        w=case_dir(root,c,cfg)
        if (w/'review/visual_ack.json').exists():
            ack=read(w/'review/visual_ack.json')
            if not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png') or ack['extraction_sha256']!=sha(w/'review/extraction_R2.json'):raise RuntimeError('real-view ACK mismatch')
            out.append(dict(case=c,q=read(w/'review/extraction_R2.json'),tuning=read(w/'input/freeze.json')['design'].get('tuning')))
    return out

def spec(root,p,cfg):
    if p in cfg['designs']:return cfg['designs'][p]
    if p.endswith('B1dense'):
        d=read(root/'decisions/S5R9_B1_FINAL.json')
        if not d['delivery_pass']:raise RuntimeError('B1 not delivered; confirmation not released')
        s=copy.deepcopy(read(case_dir(root,d['selected_case'],cfg)/'input/freeze.json')['design'])
        s.update(id=p,design='B1dense',dense_confirmation=True,data_role='same_geometry_dense_mesh_confirmation',max_Analyze=1)
        return s
    return next(c for c in read(HERE/'offline_5B/REGISTRY.json')['designs'] if c['id']==p)

def suggestion(root,p,cfg):
    s=spec(root,p,cfg)
    return propose_history(histories(root,p,cfg),s['nominal_a_mm'],'folded',target=s.get('target_y'),force_sequential=p.endswith(('D1c','D3c')))

def attempt(root,p,i):
    cfg=read(root/'authorization.json');s=spec(root,p,cfg);c=p+f'__T{i}';w=case_dir(root,c,cfg)
    if (root/'STOP.json').exists() or (root/'PAUSE.json').exists() or w.exists():raise RuntimeError('stop/pause/existing input')
    pred=copy.deepcopy(s);previous=None
    if i==1:pred['tuning']=None
    else:
        sg=suggestion(root,p,cfg)
        if not sg['needs_solve']:return sg
        pred.update(geometry_mm=sg['geometry_mm'],tuning=sg,screen=sg['screen'],prediction=dict(response_y=sg['predicted_y'],frozen_BW_laws_unchanged=True),data_role='tuned_not_independent_test')
        previous=sha(OLD/'results'/historical(p)[-1]['case']/'review/extraction_R2.json') if i==4 else sha(case_dir(root,p+f'__T{i-1}',cfg)/'review/extraction_R2.json')
    if not pred['screen']['can_submit']:return dict(needs_solve=False,reason='geometry_screen_fail_skip_no_replacement')
    for n in ('input','native','evidence'):(w/n).mkdir(parents=True)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,design=pred,nominal_a_mm=s['nominal_a_mm'],expected_boxes=geometry.slot_boxes(pred['geometry_mm'],'folded'),source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,previous_extraction_sha256=previous,solver_started=False)
    for dest in (w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')):write(dest,f)
    return dict(needs_solve=True,case=c)

def prepare(root):
    import psutil
    if root.exists():raise RuntimeError('runtime exists')
    if any((p.info['name'] or '').lower() in ('hf3d.exe','ansysedt.exe') for p in psutil.process_iter(['name'])):raise RuntimeError('native active')
    prior=read(OLD/'COMPLETE_STAGE4.json')
    if (prior['total_geometry'],prior['total_actual_Analyze'])!=(151,1406):raise RuntimeError('prior budget mismatch')
    cfg=copy.deepcopy(read(OLDROOT/'authorization.json'))
    cfg.update(at=now(),batch='5',execution_revision='R9_STAGE5',prior_geometry_total=151,prior_Analyze_total=1406,batch_geometry_limit=26,total_geometry_limit=187,R9_cumulative_geometry_cap=177,designs={},parent_order=['S5R9_'+p for p in ORDER],case_paths={},case_specs={},prior_parent_geometry={},plan_commit='af6dd1ccfaa425566ae993d9fa2ef44968c60a1b',user_authorization='用户明确同意R9第0节全部变化；R9-1先推送，5A后R9-2先推送，再5B+B1一次密网格+离线公差；5B后停止，不进6。')
    cfg.pop('R8_cumulative_geometry_cap',None)
    cfg['historical_hashes'].update({str(OLDROOT/'STOP.json'):sha(OLDROOT/'STOP.json'),str(OLDROOT/'authorization.json'):sha(OLDROOT/'authorization.json'),str(OLD/'FINAL_MANIFEST.json'):sha(OLD/'FINAL_MANIFEST.json')})
    for p in (OLDROOT/'ledger').glob('*.json'):cfg['historical_hashes'][str(p)]=sha(p)
    cfg['plan_hashes']['docs/PLAN_20261110_FOLD_BANDWIDTH_R9.md']=sha(REPO/'docs/PLAN_20261110_FOLD_BANDWIDTH_R9.md')
    cs=read(HERE/'offline/T1_GEOMETRIES.json')
    for name,oldid in [('D1c','S4R8_D1'),('D3c','S4R8_D3')]:
        c=copy.deepcopy(read(OLD/'pre_solve'/(oldid+'__T1.json'))['design']);c.update(id='S5R9_'+name,design=name,data_role='tuned_not_independent_test');cs.append(c)
    for c in cs:
        p=c['id'];c.update(kind='EQ',topology='folded',max_Analyze=2 if p.endswith(('D1c','D3c')) else 3,material_role='archived_lossy',board_half_x_mm=15.,target_y=[6.72,0.,-20.3]);cfg['designs'][p]=c
    for p in cfg['parent_order']:
        indices=[4,5] if p.endswith(('D1c','D3c')) else [1] if p.endswith('dense') else [1,2,3]
        for i in indices:
            c=p+f'__T{i}';cfg['case_paths'][c]=f'runs/{p}/attempt_{i:03d}';cfg['case_specs'][c]=dict(parent_id=p,attempt_ordinal=i)
    for n in ('freeze','pre_solve'):(HERE/n).mkdir()
    write(HERE/'freeze/REGISTRY.json',dict(order=ORDER,designs=cs,stage5A_cap=16,stage5B_cap=10,conditional_W3='W2 usable and W2 BW15* minus W1 >=0.12GHz; W1 failure skips W2/W3',stage6_authorized=False,archived_width_precision_exception='N04/N14/N08 exact archival Wm; all other dimensions .001 grid',no_hooks=True))
    write(HERE/'freeze/BUDGET.json',dict(prior_geometry=151,prior_Analyze=1406,new_geometry_cap=26,cumulative_cap=177,global_hard_cap=187,ordinary_API_cap=14,dense_API_cap=20,unused_slots_not_transferred=True))
    cfg['frozen_hashes']={p.relative_to(REPO).as_posix():sha(p) for n in ('offline','freeze') for p in sorted((HERE/n).glob('*.json'))}
    cfg['code_hashes'].update({p.relative_to(REPO).as_posix():sha(p) for p in HERE.glob('*.py')})
    root.mkdir(parents=True)
    for n in ('ledger','decisions','model_freeze','publications'):(root/n).mkdir()
    write(root/'authorization.json',cfg);shutil.copyfile(OLDROOT/'sweep_role_confirmation.json',root/'sweep_role_confirmation.json')
    write(HERE/'freeze/AUTHORIZATION_SUMMARY.json',{k:v for k,v in cfg.items() if k not in ('historical_hashes','prior_cases','prior_decisions')})
    for p in cfg['parent_order'][:6]:print(attempt(root,p,4 if p.endswith(('D1c','D3c')) else 1))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','attempt']);ap.add_argument('parent',nargs='?');ap.add_argument('i',type=int,nargs='?');a=ap.parse_args();print(prepare(ROOT) if a.command=='prepare' else attempt(ROOT,a.parent,a.i))
