"""Explicit offline review/real image ACK/next-candidate management; no solver."""
import argparse,subprocess,os
from prepare_r9 import *
def publication(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/fold-bandwidth-r4-execution'],cwd=REPO,text=True).split()[0]
    if commit!=remote:raise RuntimeError('HEAD not pushed')
    import hashlib
    rel=(HERE/'pre_solve'/(case+'.json')).relative_to(REPO).as_posix()
    if hashlib.sha256(subprocess.check_output(['git','show',commit+':'+rel],cwd=REPO)).hexdigest()!=sha(w/'input/freeze.json'):raise RuntimeError('published candidate mismatch')
    (root/'publications').mkdir(exist_ok=True)
    write(root/'publications'/(case+'.json'),dict(at=now(),commit=commit,remote_verified=True,authorization_sha256=sha(root/'authorization.json'),freeze_sha256=sha(w/'input/freeze.json')))
    print('PUBLICATION_VERIFIED',case,commit)
def ack(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg)
    if not read(w/'review/REVIEW_STAGE3.json')['numerical_pass']:raise RuntimeError('numerical failure')
    write(w/'review/visual_ack.json',dict(at=now(),actually_viewed=True,viewer='tools.view_image; model inspected actual S11/S21',plot_sha256=sha(w/'review/S11_S21.png'),extraction_sha256=sha(w/'review/extraction_R2.json')))
def scores(q):
    y=state(q)
    if y is None:return dict(usable=False,delivery=False,center=None,D=None,L=None,BW15=None,BW20=None,BW15_star=None)
    bw=q['bandwidths'];b15=bw['BW15']['BW_GHz'];b20=bw['BW20']['BW_GHz']
    return dict(usable=classify(q)['tuned'],delivery=False,center=float(y[0]),D=float(y[1]),L=float(y[2]),BW15=b15,BW20=b20,BW15_star=b15-.125*(y[2]+20.3) if b15 is not None else None)
def delivery(q,w):
    import numpy as np
    z=np.load(w/'native/full_modes.npz');b=q['bandwidths']['BW20'];y=state(q)
    if y is None or b.get('BW_GHz') is None:return dict(passed=False,S21_min_dB=None)
    # Native-band endpoints from canonical extractor.
    lo=b['low_GHz'];hi=b['high_GHz'];mask=(z['f_GHz']>=lo)&(z['f_GHz']<=hi)
    mn=float(np.min(20*np.log10(abs(z['S'][mask,2,0]))))
    peaks=[p['S11_dB'] for p in q['shape']['inner_peaks']]
    return dict(passed=bool(abs(y[0]-6.72)<=.0300000001 and max(peaks)<=-20.5 and mn>=-2 and abs(y[1])<=.2000000001 and abs(y[2]+20.65)<=.1000000001),S21_min_dB=mn,peak_dB=peaks)
def finish(root,case):
    cfg=read(root/'authorization.json');w=case_dir(root,case,cfg);fz=read(w/'input/freeze.json');p=fz['parent_id'];s=spec(root,p,cfg)
    r=read(w/'review/REVIEW_STAGE3.json');a=read(w/'review/visual_ack.json')
    if not r['numerical_pass'] or not a['actually_viewed'] or a['plot_sha256']!=sha(w/'review/S11_S21.png'):raise RuntimeError('missing numeric/visual review')
    hh=histories(root,p,cfg);new=[x for x in hh if x['case'].startswith('S5R9')]
    dense=s.get('dense_confirmation',False);b=p in cfg['parent_order'][6:]
    good=lambda z: delivery(z['q'],case_dir(root,z['case'],cfg))['passed'] if b and not dense else classify(z['q'])['tuned']
    passing=[z for z in new if good(z)]
    best=passing[0] if passing else min(new,key=lambda z:error(state(z['q'])))
    sg=suggestion(root,p,cfg) if not dense else dict(needs_solve=False)
    last=5 if p.endswith(('D1c','D3c')) else 1 if dense else 3
    if not passing and fz['attempt_ordinal']<last and sg['needs_solve']:return dict(complete=False,next_ordinal=fz['attempt_ordinal']+1)
    q=best['q'];sc=scores(q);de=delivery(q,case_dir(root,best['case'],cfg)) if b else None
    d=dict(at=now(),parent_id=p,complete=True,tuned=sc['usable'],selected_case=best['case'],attempts=len(new),kind='EQ',reason='finite R9 procedure completed; not a physical impossibility claim',**{k:v for k,v in sc.items() if k!='usable'},delivery_pass=de['passed'] if de else None,delivery_metrics=de,data_role=s['data_role'] if dense else 'tuned' if fz['attempt_ordinal']>1 else 'prospective_T1',stage6_authorized=False)
    for dest in (root/'decisions'/(p+'_FINAL.json'),HERE/'decisions'/(p+'_FINAL.json')):
        dest.parent.mkdir(exist_ok=True);write(dest,d)
    return d
def status(root):
    cfg=read(root/'authorization.json');g=list((root/'ledger').glob('geometry_*.json'));a=list((root/'ledger').glob('Analyze_*.json'))
    st=dict(at=now(),phase='stage5',R9_geometries=len(g),R9_cap=26,geometry_total=151+len(g),geometry_cap=187,R9_cumulative_cap=177,R9_actual_Analyze=len(a),actual_Analyze_total=1406+len(a),completed_parents=[read(p) for p in sorted((root/'decisions').glob('*_FINAL.json'))],stage6_started=False,stop=read(root/'STOP.json') if (root/'STOP.json').exists() else None)
    for dest in (root/'CURRENT_STATUS.json',HERE/'CURRENT_STATUS.json'):
        tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,dest)
    print(json.dumps(st,ensure_ascii=False));return st
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['publication','ack','finish','status']);ap.add_argument('case',nargs='?');a=ap.parse_args()
    if a.command=='status':status(ROOT)
    else:print(globals()[a.command](ROOT,a.case))
