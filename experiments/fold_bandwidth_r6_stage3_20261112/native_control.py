"""阶段3副本建模/材料/边界设置。无求解。"""
import importlib.util,sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
p=REPO/'experiments/fold_bandwidth_r6_stage2b_20261112/native_control.py'
s=importlib.util.spec_from_file_location('stage2_native_readonly',p);base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
def snapshot(app):
    return {o.name:dict(material=o.material_name,solve_inside=bool(o.solve_inside),
            bounding_box=[float(v) for v in o.bounding_box]) for o in app.modeler.objects.values()}
def apply_geometry(app,g,topology,material_role='archived_lossy',board_half_x_mm=15.):
    r=base.apply_geometry(app,g,topology)
    before=snapshot(app)
    if board_half_x_mm not in (15.,20.):raise ValueError('只允许登记边界')
    boundary=[]
    if board_half_x_mm==20.:
        # Native boxes whose original x span is exactly the board width.
        # Ground creation boxes may carry Boolean history; edit original box.
        for name,ob in before.items():
            b=ob['bounding_box']
            if abs(b[0]+15)<1e-7 and abs(b[3]-15)<1e-7:
                child=app.oeditor.GetChildObject(name)
                nodes=list(child.GetChildNames())
                box=next((n for n in nodes if n.startswith('CreateBox:')),None)
                if box is None:raise RuntimeError('边界对象非原生盒 '+name)
                obj=child.GetChildObject(box)
                obj.SetPropValue('Position/X','-20mm');obj.SetPropValue('XSize','40mm')
                boundary.append(name)
        if len(boundary)<5:raise RuntimeError('基板/空气/地层未完整找到')
        app.modeler.refresh()
    mats=[]
    if material_role=='lossless_control':
        for name,ob in before.items():
            mat=ob['material'].lower().strip('"')
            if mat=='copper':
                if not app.assign_material(name,'pec'):raise RuntimeError('PEC分配失败')
                mats.append(dict(object=name,old=mat,new='pec'))
            elif mat not in ('','vacuum','air','pec'):
                new='Fig8Stage3Lossless_'+mat.replace(' ','_')
                if new not in app.materials.material_keys:
                    m=app.materials.duplicate_material(mat,new)
                    if not m:raise RuntimeError('复制介质失败')
                    m.dielectric_loss_tangent=0
                    m.conductivity=0
                    if not m.update():raise RuntimeError('无耗材料更新失败')
                if not app.assign_material(name,new):raise RuntimeError('无耗介质分配失败')
                mats.append(dict(object=name,old=mat,new=new))
        if not mats:raise RuntimeError('无材料变更')
    elif material_role!='archived_lossy':raise ValueError('未知材料口径')
    app.modeler.refresh()
    if not app.save_project():raise RuntimeError('材料/边界保存失败')
    after=snapshot(app)
    if material_role=='lossless_control':
        for x in mats:
            if after[x['object']]['material'].lower()!=x['new'].lower():raise RuntimeError('材料原生回读不符')
        for name in before:
            if before[name]['bounding_box']!=after[name]['bounding_box']:raise RuntimeError('无耗改变几何')
        materials={n:dict(permittivity=str(app.materials[n].permittivity.value),
                          loss_tangent=str(app.materials[n].dielectric_loss_tangent.value),
                          conductivity=str(app.materials[n].conductivity.value))
                   for n in {x['new'] for x in mats} if n!='pec'}
        if any(float(m['loss_tangent'])!=0 or float(m['conductivity'])!=0 for m in materials.values()):raise RuntimeError('介质并非无耗')
    else:materials={}
    r['materials_and_boundary']=dict(material_role=material_role,board_half_x_mm=board_half_x_mm,
        before=before,after=after,changed_materials=mats,dielectric_readback=materials,
        widened_objects=boundary,lossless_verified=material_role=='lossless_control',new_Analyze=0)
    return r
