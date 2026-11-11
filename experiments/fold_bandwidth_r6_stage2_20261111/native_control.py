"""阶段2直槽对照构建器。仅对调用者提供的新工程副本生效，不求解。"""
from pathlib import Path
import math
import sys
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'experiments/fold_bandwidth_r4_20261110'))
import native_geometry as base

def apply_geometry(app,g,topology):
    if topology=='folded':
        return base.apply_folded_geometry(app,**{k.lower():v for k,v in g.items()})
    if topology!='straight_control':raise ValueError('未知拓扑')
    if set(g)!=set(('Wm','Ws','Lm','Ls1','Ls2','Ls3')) or g['Ls2']!=0 or g['Ls3']!=0:
        raise ValueError('直槽必须显式设置Ls2=Ls3=0')
    if not all(math.isfinite(g[k]) and g[k]>0 for k in ('Wm','Ws','Lm','Ls1')):raise ValueError('主尺寸无效')
    editor=app.oeditor
    for name in ('Substrate_3','Substrate_18'):
        box=editor.GetChildObject(name).GetChildObject('CreateBox:1')
        box.SetPropValue('XSize',base._mm(g['Wm']))
        box.SetPropValue('Position/X',f"(-{base._mm(g['Wm'])}/2)")
        box.SetPropValue('YSize',base._mm(g['Lm']) if name=='Substrate_3' else '-'+base._mm(g['Lm']))
    if not app.modeler.delete(['Substrate_7','Substrate_9']):raise RuntimeError('无法替换副本中的接地层')
    app.modeler.refresh()
    layers=[]
    for side,name,z,cz in [('top','Substrate_7',0.,-.01),('bottom','Substrate_9',-.035,-.045)]:
        ground=base._create_box_native(app,name,[-15.,-25.,z],[30.,50.,.035],'copper',
             color='(255 128 64)',transparency=.85,solve_inside=False)
        cut_name=f'StructureBSlot_{side}_main'
        cut=base._create_box_native(app,cut_name,[-g['Ls1']/2,-g['Ws']/2,cz],
             [g['Ls1'],g['Ws'],.055],'vacuum',color='(132 132 193)',transparency=.8,solve_inside=True)
        if ground is None or cut is None:raise RuntimeError('直槽副本建模失败')
        if app.modeler.subtract([name],[cut],keep_originals=False) is not True:raise RuntimeError('直槽布尔运算失败')
        layers.append(dict(side=side,ground=name,cut=cut_name))
    app.modeler.refresh()
    if not app.save_project():raise RuntimeError('直槽副本保存失败')
    return dict(topology=topology,geometry_mm=g,layers=layers,slot_operand_count=2,
                saved=True,source='same R4 copper grounds and main slot, no folded connectors or arms')
