"""Pure orthogonal CAD union/edge-offset IR; no AEDT import, no guessed etch mapping.

Profiles come from archived actual native B1 boxes. Join edges are removed
before offsetting, so separate touching conductor boxes are NOT etched apart.
All physical XY edges move by signed distance; copper thickness is unchanged.
Port cut-plane clipping and h/port scaling require an explicit policy argument.
"""
import json,math
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def json_value(value):return json.loads(json.dumps(value,allow_nan=False))

def pt(p):return tuple(round(float(v),10) for v in p)
def area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2
def clean(poly):
    p=[pt(z) for z in poly]
    while True:
        q=[b for a,b,c in zip(p[-1:]+p[:-1],p,p[1:]+p[:1]) if abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))>1e-12]
        if len(q)==len(p):break
        p=q
    if area(p)<0:p=list(reversed(p))
    j=min(range(len(p)),key=lambda i:p[i]);return p[j:]+p[:j]
def union_profile(rects):
    # rect=(xmin,ymin,xmax,ymax); all internal seams are removed by grid union.
    rects=[pt(r) for r in rects] # collapse binary-float coincident edges before topology
    xs=sorted(set(v for r in rects for v in (r[0],r[2])));ys=sorted(set(v for r in rects for v in (r[1],r[3])))
    cells=set()
    for i in range(len(xs)-1):
        for j in range(len(ys)-1):
            x=(xs[i]+xs[i+1])/2;y=(ys[j]+ys[j+1])/2
            if any(r[0]<x<r[2] and r[1]<y<r[3] for r in rects):cells.add((i,j))
    edges={}
    for i,j in cells:
        x0,x1=xs[i:i+2];y0,y1=ys[j:j+2]
        for neighbor,a,b in [((i,j-1),(x0,y0),(x1,y0)),((i+1,j),(x1,y0),(x1,y1)),((i,j+1),(x1,y1),(x0,y1)),((i-1,j),(x0,y1),(x0,y0))]:
            if neighbor not in cells:
                if pt(a) in edges:raise ValueError('non-manifold point-touch profile')
                edges[pt(a)]=pt(b)
    start=min(edges);p=[start];z=edges[start]
    while z!=start:
        if z in p or z not in edges:raise ValueError('invalid boundary')
        p.append(z);z=edges[z]
    if len(p)!=len(edges):raise ValueError('multiple boundaries not supported')
    return clean(p)
def contains(poly,x,y):
    inside=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside
def rectangles(poly):
    xs=sorted(set(p[0] for p in poly));ys=sorted(set(p[1] for p in poly));active={};done=[]
    for y0,y1 in zip(ys,ys[1:]):
        cells=[contains(poly,(x0+x1)/2,(y0+y1)/2) for x0,x1 in zip(xs,xs[1:])];runs=[];i=0
        while i<len(cells):
            if not cells[i]:i+=1;continue
            j=i
            while j+1<len(cells) and cells[j+1]:j+=1
            runs.append((xs[i],xs[j+1]));i=j+1
        nxt={}
        for key in runs:
            r=active.pop(key,[key[0],y0,key[1],y1]);r[3]=y1;nxt[key]=r
        done.extend(active.values());active=nxt
    done.extend(active.values());done=sorted([list(map(float,r)) for r in done])
    if abs(sum((r[2]-r[0])*(r[3]-r[1]) for r in done)-area(poly))>1e-8:raise AssertionError('rectangulation area')
    if clean(union_profile(done))!=clean(poly):raise AssertionError('rectangulation boundary')
    return done
def offset(poly,distance,clip_port_faces=False):
    p=clean(poly);ns=[];ds=[];report=[]
    for a,b in zip(p,p[1:]+p[:1]):
        dx=b[0]-a[0];dy=b[1]-a[1]
        if abs(dx)>1e-10 and abs(dy)>1e-10:raise ValueError('not orthogonal')
        n=np.array([-dy,dx])/math.hypot(dx,dy)
        cut=clip_port_faces and abs(a[1]-b[1])<1e-10 and abs(abs(a[1])-25)<1e-10
        ns.append(n);ds.append(0. if cut else float(distance))
        report.append(dict(start=a,end=b,inward_normal=n.tolist(),signed_inward_distance_mm=ds[-1],simulation_cut_face=cut))
    q=[pt(np.array(v)+ns[i-1]*ds[i-1]+ns[i]*ds[i]) for i,v in enumerate(p)]
    for i in range(len(p)):
        for j in (i,(i+1)%len(p)):
            if abs(float((np.array(q[j])-p[j])@ns[i])-ds[i])>1e-8:raise AssertionError('edge offset distance')
    if area(q)<=0:raise ValueError('offset collapses profile')
    return clean(q),report
def boxrect(b):return [b[0],b[1],b[3],b[4]]
def source_profiles(g):
    src=json.loads((HERE/'offline/SOURCE_NATIVE_B1.json').read_text(encoding='utf-8'))
    obj={n:dict(v,bounding_box=list(v['bounding_box'])) for n,v in src['objects'].items()}
    for n in ('Substrate_3','Substrate_18'):
        b=obj[n]['bounding_box'];b[0]=-g['Wm']/2;b[3]=g['Wm']/2
        b[1],b[4]=(0.,g['Lm']) if n=='Substrate_3' else (-g['Lm'],0.)
    # Slot operands are built in the already-verified native convention, then
    # their UNION boundary, not individual operands, is offset.
    import sys
    sys.path.insert(0,str(HERE.parents[1]/'experiments/fold_bandwidth_r2_20261110'))
    import geometry
    boxes=geometry.slot_boxes(g)
    rr=[]
    for r in boxes:
        if '_top_' not in r['name']:continue
        v=r['parameters_mm'];rr.append([v['XPosition'],v['YPosition'],v['XPosition']+v['XSize'],v['YPosition']+v['YSize']])
    return dict(top=union_profile([boxrect(obj[n]['bounding_box']) for n in ('Substrate_3','Substrate_4')]),bottom=union_profile([boxrect(obj[n]['bounding_box']) for n in ('Substrate_18','Substrate_5')]),slot=union_profile(rr),ground=union_profile([boxrect(obj['Substrate_7']['bounding_box'])])),src
def build(g,e=0.,er=3.55,h=.813,*,port_policy,h_port_policy,board_policy="fixed_milled_outline"):
    if board_policy not in ("fixed_milled_outline","legacy_offset_ground"):raise ValueError("unknown board policy")
    if port_policy not in ('clip_cut_faces','offset_cut_faces'):raise ValueError('explicit port cut policy required')
    if h_port_policy not in ('height_8h_width_fixed','scale_entire_cross_section'):raise ValueError('explicit thickness/port rule required')
    p,src=source_profiles(g);profiles={};proof={}
    for k,v in p.items():
        fixed_ground=k=='ground' and board_policy=='fixed_milled_outline'
        profiles[k],proof[k]=offset(v,0. if fixed_ground else -e if k=='slot' else e,clip_port_faces=port_policy=='clip_cut_faces' and k!='slot')
        for ed in proof[k]:ed['fixed_milled_board_edge']=fixed_ground
    rect={k:rectangles(v) for k,v in profiles.items()}
    bounds=lambda v:[min(x[0] for x in v),min(x[1] for x in v),max(x[0] for x in v),max(x[1] for x in v)]
    sv=bounds(profiles['slot']);ws=round(2*sv[3],10);ls1=sv[2]-sv[0];ls2=ws/2-sv[1];tip=min(x[0] for x in profiles['slot'] if x[0]>1e-9);ls3=sv[2]-tip
    top=rect['top'];stub=max(top,key=lambda r:r[2]-r[0]);feed=min(top,key=lambda r:r[2]-r[0])
    actual=dict(Wm=stub[2]-stub[0],Ws=ws,Lm=stub[3]-stub[1],Ls1=ls1,Ls2=ls2,Ls3=ls3)
    actual={k:round(v,10) for k,v in actual.items()}
    expected=[]
    for side,z in [('top',-.01),('bottom',-.045)]:
        for i,r in enumerate(rect['slot']):expected.append(dict(name=f'StructureBSlot_{side}_r{i:02d}',parameters_mm=dict(XPosition=r[0],YPosition=r[1],ZPosition=z,XSize=r[2]-r[0],YSize=r[3]-r[1],ZSize=.055)))
    if abs(e)<1e-12:
        import geometry
        expected=geometry.slot_boxes(g) # keep B1's exact native Boolean partition for ordinary perturbations
    width=15.04 if h_port_policy=='height_8h_width_fixed' else 15.04*h/.813
    return dict(board_policy=board_policy,base_geometry_mm=g,geometry_mm=actual,etch_e_mm=e,er=er,h_mm=h,tand=.0027,copper_mm=.035,port_policy=port_policy,h_port_policy=h_port_policy,port_width_mm=width,port_height_mm=8*h,profiles=profiles,source_profiles=p,rectangles=rect,edge_distance_proof=proof,expected_slot_boxes=expected,feed_width_mm=feed[2]-feed[0],stub_shoulder_y_mm=stub[1],stub_open_end_y_mm=stub[3],canonical_six_dimensions_sufficient=abs(e)<1e-12,source_sha256=src['source_sha256'])
