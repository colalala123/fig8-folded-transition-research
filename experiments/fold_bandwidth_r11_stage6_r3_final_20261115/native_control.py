"""R10 fresh-copy CAD/material construction; never calls Analyze.

Authoritative etch input is the union-boundary IR, not six guessed parameters.
Live acceptance is mandatory before a solver release. This module is not a
standalone launcher and importing it does not import/attach to AEDT.
"""
import copy,importlib.util,math
from collections.abc import Mapping
from pathlib import Path
import numpy as np
import cad_ir
H=Path(__file__).resolve().parent;REPO=H.parents[1]
TOL=1e-7

def bounds(r,z0,z1):return [r[0],r[1],min(z0,z1),r[2],r[3],max(z0,z1)]

def port_rectangle_props(ir,sign):
    # Actual AEDT2024R2 OO property inventory for Axis=Y: XSize/ZSize,
    # not CreateRectangle command-input labels Width/Height.
    return {'Position/X':-ir['port_width_mm']/2,'XSize':ir['port_width_mm'],'ZSize':sign*ir['port_height_mm']}

def plain_value(value):
    # BoundaryProps carries an owner/gRPC proxy in attributes. Never deepcopy
    # its object graph: recursively copy property VALUES, not object state.
    if isinstance(value,Mapping):return {k:plain_value(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain_value(v) for v in value]
    if value is None or isinstance(value,(str,bool,int,float)):return value
    raise TypeError('Non-plain native boundary property: '+type(value).__name__)

def saved_ports(project,design_name='Wideband vertical transition'):
    from ansys.aedt.core.internal.load_aedt_file import load_keyword_in_aedt_file
    data=load_keyword_in_aedt_file(project,'BoundarySetup',design_name=design_name)
    b=data['BoundarySetup']['Boundaries']
    return {n:plain_value(v) for n,v in b.items() if isinstance(v,Mapping) and v.get('BoundType')=='Wave Port'}
def expected_objects(ir):
    h=ir['h_mm'];w=ir['port_width_mm'];ph=ir['port_height_mm']
    top=sorted(ir['rectangles']['top'],key=lambda r:r[2]-r[0])
    bottom=sorted(ir['rectangles']['bottom'],key=lambda r:r[2]-r[0])
    if len(top)!=2 or len(bottom)!=2 or len(ir['rectangles']['ground'])!=1:raise ValueError('unexpected conductor topology')
    ground=ir['rectangles']['ground'][0]
    return {'Substrate_1':[-15.,-25.,.035,15.,25.,.035+h],
        'Substrate_2':[-15.,-25.,-.035-h,15.,25.,-.035],
        'air_box':[-15.,-25.,-11.,15.,25.,11.],
        'Substrate_3':bounds(top[1],.035+h,.070+h),
        'Substrate_4':bounds(top[0],.035+h,.070+h),
        'Substrate_18':bounds(bottom[1],-.035-h,-.070-h),
        'Substrate_5':bounds(bottom[0],-.035-h,-.070-h),
        'Substrate_7':bounds(ground,0.,.035),'Substrate_9':bounds(ground,-.035,0.),
        'Rectangle1':[-w/2,-25.,0.,w/2,-25.,ph],
        'Rectangle2':[-w/2,25.,-ph,w/2,25.,0.]}

def snapshot(app):
    return {o.name:dict(material=o.material_name,solve_inside=bool(o.solve_inside),
        bounding_box=[float(v) for v in o.bounding_box]) for o in app.modeler.objects.values()}

def validate_source_strip_profiles(ir,objects):
    for names,key in [(('Substrate_3','Substrate_4'),'top'),(('Substrate_18','Substrate_5'),'bottom')]:
        rr=[cad_ir.boxrect(objects[n]['bounding_box']) for n in names]
        if cad_ir.json_value(cad_ir.union_profile(rr))!=cad_ir.json_value(ir['source_profiles'][key]):raise RuntimeError('native source union mismatch '+key)

def close(a,b):return bool(np.allclose(a,b,atol=TOL,rtol=0))
def on_segment(p,a,b):
    return abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))<TOL and min(a[0],b[0])-TOL<=p[0]<=max(a[0],b[0])+TOL and min(a[1],b[1])-TOL<=p[1]<=max(a[1],b[1])+TOL

def validate_observed(ir,objects,ground_vertices,ports,dielectric):
    expected=expected_objects(ir)
    if set(objects)!=set(expected):raise RuntimeError('native object inventory changed')
    for n,b in expected.items():
        if not close(objects[n]['bounding_box'],b):raise RuntimeError('native bounding box mismatch '+n)
    for n in ('Substrate_3','Substrate_4','Substrate_5','Substrate_18','Substrate_7','Substrate_9'):
        if objects[n]['material'].lower().strip('"')!='copper' or objects[n]['solve_inside']:raise RuntimeError('copper/material mismatch '+n)
    for n in ('Substrate_1','Substrate_2'):
        d=dielectric[n]
        if not close([d['er'],d['tand']],[ir['er'],.0027]) or not objects[n]['solve_inside']:raise RuntimeError('dielectric mismatch '+n)
    profiles=[ir['profiles'][k] for k in ('ground','slot')]
    for n in ('Substrate_7','Substrate_9'):
        vv=[v[:2] for v in ground_vertices[n]]
        for poly in profiles:
            for p in poly:
                if not any(close(p,v) for v in vv):raise RuntimeError('missing native copper boundary corner '+n+str(p))
        for v in vv:
            if not any(on_segment(v,a,b) for poly in profiles for a,b in zip(poly,poly[1:]+poly[:1])):raise RuntimeError('unexpected native copper boundary vertex '+n+str(v))
    if set(ports)!= {'1','2'}:raise RuntimeError('ports changed')
    for name,p in ports.items():
        if int(p['NumModes'])!=2 or p['DoDeembed']:raise RuntimeError('port modes/deembed changed')
        modes=p['Modes']
        if not modes['Mode1']['UseIntLine'] or modes['Mode2']['UseIntLine']:raise RuntimeError('integration mode changed')
        if any(modes[k]['CharImp']!='Zpi' for k in ('Mode1','Mode2')):raise RuntimeError('port impedance convention changed')
        line=modes['Mode1']['IntLine'];y=-25. if name=='1' else 25.;z=(ir['h_mm']+.07)*(1 if name=='1' else -1)
        if 'Start' in line:
            cv=lambda v:float(str(v).removesuffix('mm'))
            points=[[cv(v) for v in line[k]] for k in ('Start','End')]
        else:
            points=[[float(str(v[k+'Position']).removesuffix('mm')) for k in ('X','Y','Z')] for v in line['GeometryPosition']]
        if not close(points,[[0,y,z],[0,y,0]]):raise RuntimeError('integration line mismatch '+name)
    return dict(passed=True,all_object_bboxes=True,copper_edge_vertices=True,er_tand_h=True,
        port_modes_and_integration=True,slot_operands_need_independent_saved_file_readback=True)

def set_props(editor,name,kind,props):
    obj=editor.GetChildObject(name);nodes=list(obj.GetChildNames())
    matches=[n for n in nodes if n.startswith(kind+':')]
    if len(matches)!=1:raise RuntimeError('ambiguous creation node '+name)
    node=obj.GetChildObject(matches[0]);available=set(node.GetPropNames())
    # Fail before solving rather than guess a version-specific property name.
    if not set(props)<=available:raise RuntimeError('native creation properties missing '+name+': '+str(set(props)-available))
    for k,v in props.items():node.SetPropValue(k,f'{v:.17g}mm')

def apply_case(app,pred):
    ir=pred['cad_ir'];g=ir['base_geometry_mm']
    if ir['port_policy']!='clip_cut_faces':raise RuntimeError('offset cut-face policy has no validated native port implementation')
    rebuilt=cad_ir.build(g,ir['etch_e_mm'],ir['er'],ir['h_mm'],port_policy=ir['port_policy'],h_port_policy=ir['h_port_policy'])
    if cad_ir.json_value(rebuilt)!=ir:raise RuntimeError('frozen CAD IR not reproducible')
    sp=importlib.util.spec_from_file_location('r4_geometry_for_r10',REPO/'experiments/fold_bandwidth_r4_20261110/native_geometry.py')
    base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)
    canonical=base.apply_folded_geometry(app,**{k.lower():v for k,v in g.items()})
    before=snapshot(app)
    # Source edge profiles must describe actual rebuilt CAD, including feed join.
    validate_source_strip_profiles(ir,before)
    editor=app.oeditor;expect=expected_objects(ir)
    if abs(ir['etch_e_mm'])>1e-12:
        # Keep feed/stub IDs and integration attachment objects; joined boundary
        # is offset before decomposition, never etch the touching seam twice.
        for n in ('Substrate_3','Substrate_4','Substrate_5','Substrate_18'):
            b=expect[n]
            set_props(editor,n,'CreateBox',{'Position/X':b[0],'Position/Y':b[1],'XSize':b[3]-b[0],'YSize':b[4]-b[1]})
        if not app.modeler.delete(['Substrate_7','Substrate_9']):raise RuntimeError('new copy ground replacement failed')
        for side,name,z in [('top','Substrate_7',0.),('bottom','Substrate_9',-.035)]:
            b=expect[name]
            base._create_box_native(app,name,[b[0],b[1],z],[b[3]-b[0],b[4]-b[1],.035],'copper',color='(255 128 64)',transparency=.85,solve_inside=False)
            for r in ir['expected_slot_boxes']:
                if '_'+side+'_' not in r['name']:continue
                v=r['parameters_mm'];cut=base._create_box_native(app,r['name'],[v[k] for k in ('XPosition','YPosition','ZPosition')],
                    [v[k] for k in ('XSize','YSize','ZSize')],'vacuum',color='(132 132 193)',transparency=.8,solve_inside=True)
                if cut is None or app.modeler.subtract([name],[cut],keep_originals=False) is not True:raise RuntimeError('etch Boolean failed')
    if abs(ir['h_mm']-.813)>1e-12:
        h=ir['h_mm']
        for n,sz in [('Substrate_1',h),('Substrate_2',-h)]:set_props(editor,n,'CreateBox',{'ZSize':sz})
        for n in ('Substrate_3','Substrate_4','Substrate_5','Substrate_18'):
            set_props(editor,n,'CreateBox',{'Position/Z':(.035+h)*(1 if n in ('Substrate_3','Substrate_4') else -1)})
        for n,sign in [('Rectangle1',1),('Rectangle2',-1)]:
            set_props(editor,n,'CreateRectangle',port_rectangle_props(ir,sign))
    if abs(ir['er']-3.55)>1e-12:
        old=before['Substrate_1']['material'];new='R10Tolerance_er_'+str(ir['er']).replace('.','p')
        if new in app.materials.material_keys:raise RuntimeError('expected fresh project material namespace')
        m=app.materials.duplicate_material(old,new)
        if not m:raise RuntimeError('duplicate material failed')
        m.permittivity=ir['er'];m.dielectric_loss_tangent=.0027
        if not m.update() or not app.assign_material(['Substrate_1','Substrate_2'],new):raise RuntimeError('er material update failed')
    if abs(ir['etch_e_mm'])>1e-12 or abs(ir['h_mm']-.813)>1e-12:
        for boundary in app.boundaries:
            if boundary.name not in ('1','2'):continue
            p=plain_value(boundary.props);y=-25. if boundary.name=='1' else 25.;z=(ir['h_mm']+.07)*(1 if boundary.name=='1' else -1)
            p['Modes']['Mode1']['IntLine']={'Start':['0mm',f'{y}mm',f'{z:.17g}mm'],'End':['0mm',f'{y}mm','0mm']}
            boundary.auto_update=False;boundary.props.clear();boundary.props.update(p)
            if not boundary.update():raise RuntimeError('port integration update failed')
            boundary.auto_update=True
    app.modeler.refresh()
    if not app.save_project():raise RuntimeError('R10 CAD save failed')
    after=snapshot(app);vertices={n:[[float(x) for x in editor.GetVertexPosition(v)] for v in editor.GetVertexIDsFromObject(n)] for n in ('Substrate_7','Substrate_9')}
    # Independent saved-AEDT readback, not the just-edited BoundaryProps cache.
    ports=saved_ports(app.project_file,app.design_name)
    for name,sheet in [('1','Rectangle1'),('2','Rectangle2')]:
        if ports[name]['Objects'] not in ([app.modeler[sheet].id],[sheet]):raise RuntimeError('saved native port sheet assignment mismatch '+name)
    dielectric={}
    for n in ('Substrate_1','Substrate_2'):
        m=app.materials[after[n]['material']];dielectric[n]=dict(er=float(m.permittivity.value),tand=float(m.dielectric_loss_tangent.value))
    proof=validate_observed(ir,after,vertices,ports,dielectric)
    return dict(canonical_build=canonical,cad_ir=ir,native_acceptance=proof,native_ground_vertices=vertices,native_ports=ports,
        materials_and_boundary=dict(before=before,after=after,material_role='R10_tolerance_only_nominal_material_unchanged',
            dielectric_readback=dielectric,board_half_x_mm=15.,new_Analyze=0))
