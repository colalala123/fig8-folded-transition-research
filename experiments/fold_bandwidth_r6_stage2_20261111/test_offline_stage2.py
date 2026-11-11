"""阶段2尚未释放；使用构造提取结果和原生API替身测试，不启动HFSS。"""
import copy
import json
import unittest
import tuning
import native_control
from pathlib import Path
import geometry

P=tuning.REPO/'experiments/fold_bandwidth_r1_20261110/freeze_r1/predictions_frozen.json'
REG=json.loads(P.read_text(encoding='utf-8'))
BASE=next(x for x in REG['designs'] if x['id']=='S2_E1_N14_a1.0')['geometry_mm']

def fake_q():
    return dict(geometry_mm=BASE.copy(),shape=dict(shape_valid=True,central_valley_GHz=6.8,peak_difference_dB=.6,passed=False),
        circuit=dict(extraction_nonunique=False,parameters=dict(fm_GHz=6.7,fs_GHz=6.65)))
class Modeler:
    def __init__(self):self.subtractions=[]
    def delete(self,names):return True
    def refresh(self):pass
    def get_object_from_name(self,name):return name
    def subtract(self,ground,cut,keep_originals):self.subtractions.append((ground,cut));return True
class Editor:
    def __init__(self):self.boxes=[]
    def GetChildObject(self,name):return self
    def SetPropValue(self,k,v):pass
    def CreateBox(self,args,attributes):
        def pairs(v):return {v[i].removesuffix(':='):v[i+1] for i in range(1,len(v),2)}
        a,b=pairs(args),pairs(attributes)
        if b['Name'].startswith('StructureBSlot_'):
            self.boxes.append(dict(name=b['Name'],parameters_mm={k:float(a[k][:-2]) for k in ('XPosition','YPosition','ZPosition','XSize','YSize','ZSize')}))
class App:
    def __init__(self):self.oeditor=Editor();self.modeler=Modeler()
    def save_project(self):return True
class Offline(unittest.TestCase):
    def test_non20dB_can_be_length_calibrated(self):
        q=fake_q();q['shape'].update(central_valley_GHz=6.72,peak_difference_dB=.4)
        self.assertTrue(tuning.classify(q)['length_calibrated'])
        self.assertFalse(tuning.propose(q,1.)['needs_solve'])
    def test_targets_and_widths_fixed(self):
        q=fake_q();r=tuning.propose(q,1.)
        self.assertTrue(r['needs_solve'])
        for k in ('Wm','Ws','Ls2','Ls3'):self.assertEqual(r['geometry_mm'][k],q['geometry_mm'][k])
        self.assertGreater(r['geometry_mm']['Lm'],q['geometry_mm']['Lm'])
        self.assertGreater(r['geometry_mm']['Ls1'],q['geometry_mm']['Ls1'])
    def test_ambiguity_never_blindly_tuned(self):
        q=fake_q();q['circuit']['extraction_nonunique']=True
        self.assertFalse(tuning.propose(q,1.)['needs_solve'])
    def test_input_not_mutated(self):
        q=fake_q();original=copy.deepcopy(q);tuning.propose(q,1.);self.assertEqual(q,original)
    def test_straight_native_operands(self):
        row=next(x for x in REG['designs'] if x['id']=='S2_E0_N14')
        app=App();r=native_control.apply_geometry(app,row['geometry_mm'],'straight_control')
        self.assertEqual(r['slot_operand_count'],2);self.assertEqual(len(app.modeler.subtractions),2)
        self.assertTrue(geometry.compare_boxes(geometry.slot_boxes(row['geometry_mm'],'straight_control'),app.oeditor.boxes)['passed'])
    def test_invalid_straight_dimensions(self):
        with self.assertRaises(ValueError):native_control.apply_geometry(App(),BASE,'straight_control')
    def test_all_planned_stage2_initial_geometry_screens(self):
        for r in REG['designs']:
            if r['batch']=='2a':
                g=r['geometry_mm'];a=g['Ls3']-g['Ws'] if r['topology']=='folded' else 0
                self.assertTrue(tuning.presubmit(g,a,topology=r['topology'])['can_submit'],r['id'])
if __name__=='__main__':unittest.main()
