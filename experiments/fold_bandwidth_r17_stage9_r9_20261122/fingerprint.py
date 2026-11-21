"""Physical input fingerprint (not output/iteration identity). Legacy non-IR collisions held for review."""
import json, hashlib
from common_stage2 import HERE,REPO,read,sha,case_dir,next_stage,dense_next_stage
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def norm(x):
    if isinstance(x,bool):return x
    if isinstance(x,(float,int)):return 0.0 if abs(x)<5e-12 else round(float(x),11)
    if isinstance(x,dict):return {k:norm(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return list(map(norm,x))
    return x
def dims(d):return {k:int(round(float(d['geometry_mm'][k])*1000)) for k in ('Wm','Ws','Lm','Ls1','Ls2','Ls3')}
SWEEP={'name':'Sweep1','type':'Interpolating','enabled_only_after_mesh':True,'GHz':[.01,15.,.01],'InterpTolerance':1.,'EnforcePassivity':False}
def settings(d,mesh_version=None):
    dense=bool(d.get('dense_confirmation'));mesh_version=mesh_version or ('R15_dense' if dense else 'R5_ordinary')
    return dict(mesh=dict(rule=mesh_version,delta_s=.002 if dense else .005,initial=[16,30],minimum_converged_passes=2,use_max_tet_increase=False,revert=False),
                solver=dict(design='HFSS driven modal',setup='Setup19',cores=14,groups=1,modes_per_port=2,material=d.get('material_role','archived_lossy'),topology=d.get('topology','folded'),board_half_x_mm=d.get('board_half_x_mm',15.)),sweep=SWEEP)
def identity(d,mesh_version=None):
    ir=d.get('cad_ir');s=settings(d,mesh_version)
    # Canonical physical CAD, not audit/provenance or submit metadata. Do not round etch profiles to the six dimensions.
    if ir is not None:
        ir={k:v for k,v in ir.items() if k not in ('source_sha256','edge_distance_proof','canonical_six_dimensions_sufficient','base_geometry_mm','source_profiles')}
        ir.setdefault('board_policy','fixed_milled_outline' if not ir.get('etch_e_mm') else 'legacy_outline')
        ir['geometry_mm']=dims(d)
    return digest(norm(dict(geometry_um=dims(d),cad_ir=ir,**s)))
def old_index():
    rows=[]
    for p in sorted((REPO/'experiments').glob('fold_bandwidth_*/results/*/SUMMARY.json')):
        if HERE in p.parents:continue
        summary=read(p)
        if not summary.get('record',{}).get('solve_completed'):continue
        src=p.with_name('INPUT.json');v=read(src);d=v.get('design',v)
        dense=d.get('dense_confirmation');r15='r15_stage7' in str(p) or 'r16_stage8' in str(p)
        rows.append(dict(case=p.parent.name,source=src.relative_to(REPO).as_posix(),sha256=sha(src),signature=identity(d,('pre_R15_dense' if dense and not r15 else None)),geometry_um=dims(d),legacy_no_ir=not bool(d.get('cad_ir')),dense=bool(dense)))
    if not rows:raise RuntimeError('empty historical index')
    return rows
def lookup(d,rows):
    fp=identity(d); hits=[r['case'] for r in rows if r['signature']==fp or (r.get('legacy_no_ir') and r['geometry_um']==dims(d) and bool(d.get('dense_confirmation'))==r['dense'])]
    return dict(signature=fp,duplicates=hits,allowed=not hits,reason='controller_stalled' if hits else 'novel',new_Analyze=0)
def inspect(root,cfg,d):
    rows=list(read(HERE/'freeze/COMPLETED_INPUT_INDEX.json')['rows'])
    for c in cfg['case_specs']:
        w=case_dir(root,c,cfg)
        if (w/'done.json').exists():
            inp=read(w/'input/freeze.json')['design']
            rows.append(dict(case=c,signature=identity(inp)))
    return lookup(d,rows)
