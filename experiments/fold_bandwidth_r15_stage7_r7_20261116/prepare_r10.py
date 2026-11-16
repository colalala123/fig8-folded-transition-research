"""R15 immutable input construction and finite suggestions; no native API."""
import argparse,copy
from common_stage2 import *
import stage7,cad_ir
from tuning import *
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r15_stage7_r7_20261116')
OLD=REPO/'experiments/fold_bandwidth_r9_stage5_20261114'
INITIAL=[]
ORDER=['W4R','C1W','W4Rdense']

def histories(root,p,cfg):
    seed=stage7.PRIOR_H/'results/S6R10_W4__T1'
    out=[dict(case='S6R10_W4__T1',q=read(seed/'review/extraction_R2.json'),tuning=None)]
    for c,s in cfg['case_specs'].items():
        if s['parent_id']!=p:continue
        w=case_dir(root,c,cfg)
        if (w/'review/visual_ack.json').exists():
            ack=read(w/'review/visual_ack.json')
            if not ack['actually_viewed'] or ack['plot_sha256']!=sha(w/'review/S11_S21.png') or ack['extraction_sha256']!=sha(w/'review/extraction_R2.json'):raise RuntimeError('ACK mismatch')
            out.append(dict(case=c,q=read(w/'review/extraction_R2.json'),tuning=read(w/'input/freeze.json')['design'].get('tuning')))
    return out

def spec(root,p,cfg):
    if p=='S7R15_W4R':return copy.deepcopy(cfg['designs'][p])
    if p not in ('S7R15_C1W','S7R15_W4Rdense'):raise RuntimeError('unregistered parent')
    decision=read(root/'decisions/S7R15_W4R_FINAL.json')
    if not decision['complete']:raise RuntimeError('nominal search incomplete')
    selected=read(case_dir(root,decision['selected_case'],cfg)/'input/freeze.json')['design']
    m=read(HERE/'freeze/R15_R7.json')['margin']
    name=p.removeprefix('S7R15_')
    d=stage7.build_design(selected['geometry_mm'],name,'CONTROL',e=.01 if name=='C1W' else 0.,er=3.50 if name=='C1W' else 3.55,h=m['h0_mm']-m['tol_h_mm'] if name=='C1W' else m['h0_mm'],selected_nominal_case=decision['selected_case'],nominal_tuned=decision['passed'])
    return d

def suggestion(root,p,cfg):
    if p!='S7R15_W4R':raise RuntimeError('no tuning for controls')
    s=spec(root,p,cfg);m=read(HERE/'freeze/R15_R7.json')['margin']
    return propose_history(histories(root,p,cfg),1.8,'folded',target=s['target_y'],peak_window=[m['P_req_dB']-.2,m['P_req_dB']])

def make_input(root,p,i,retry=False):
    cfg=read(root/'authorization.json');c=p+f'__T{i}'
    if retry:raise RuntimeError('R15 no automatic numerical retry')
    w=case_dir(root,c,cfg)
    if any((root/n).exists() for n in ('STOP.json','PAUSE.json')) or w.exists():raise RuntimeError('stopped/paused/existing input')
    if (root/'decisions'/(p+'_FINAL.json')).exists():raise RuntimeError('parent already closed')
    d=spec(root,p,cfg);previous=None
    if p=='S7R15_W4R' and i>1:
        previous_case=case_dir(root,p+f'__T{i-1}',cfg)
        if not (previous_case/'review/visual_ack.json').exists():raise RuntimeError('previous attempt unreviewed')
        sg=suggestion(root,p,cfg)
        if not sg['needs_solve']:return sg
        d=stage7.build_design(sg['geometry_mm'],'W4R',target_y=d['target_y'],prediction=dict(response_y=sg['predicted_y']))
        d.update(tuning=sg,data_role='tuned_not_independent_test');previous=sha(previous_case/'review/extraction_R2.json')
    if not d['screen']['can_submit']:return dict(needs_solve=False,reason='geometry_conflict_no_alternative')
    from geometry_gate import check_ir
    check_ir(d['cad_ir'])
    for n in ('input','native','evidence'):(w/n).mkdir(parents=True)
    f=dict(at=now(),parent_id=p,attempt_ordinal=i,logical_case=c,numerical_retry=False,design=d,
        nominal_a_mm=d['nominal_a_mm'],expected_boxes=d['cad_ir']['expected_slot_boxes'],source_hashes={'hfss/INV01_A14.aedt':sha(REPO/'hfss/INV01_A14.aedt')},authorization_sha256=sha(root/'authorization.json'),resume=False,inherited_Analyze=0,previous_extraction_sha256=previous,solver_started=False)
    for dest in (w/'input/freeze.json',root/'model_freeze'/(c+'.json'),HERE/'pre_solve'/(c+'.json')):write(dest,f)
    return dict(needs_solve=True,case=c)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['attempt']);ap.add_argument('parent');ap.add_argument('ordinal',type=int);a=ap.parse_args();print(make_input(ROOT,a.parent,a.ordinal))
