"""一次性派生新阶段3执行文件；只在目标不存在时创建，绝不修改旧批。"""
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'fold_bandwidth_r6_stage2b_20261112'
def put(name,s):
    p=HERE/name
    if p.exists():raise RuntimeError('不覆盖 '+name)
    p.write_text(s,encoding='utf-8')
put('common_stage2.py',(OLD/'common_stage2.py').read_text(encoding='utf-8'))
s=(OLD/'budget_stage2.py').read_text(encoding='utf-8')
s=s.replace("cfg['batch']!='2b'","cfg['batch']!='3'").replace("<=3:","<=cfg['designs'][parent]['max_Analyze']:")
s=s.replace("if len(geom)>=66:","if len(geom)>=42:").replace("2b几何预算耗尽","阶段3几何预算耗尽")
s=s.replace("for x in geom)>=3:","for x in geom)>=cfg['designs'][parent]['max_Analyze']:")
s=s.replace("batch='2b'","batch='3'")
put('budget_stage2.py',s)
s=(OLD/'controller_stage2.py').read_text(encoding='utf-8')
put('controller_stage2.py',s)
s=(OLD/'worker_stage2.py').read_text(encoding='utf-8')
s=s.replace("geom=apply_geometry(app,g,pred['topology'])","geom=apply_geometry(app,g,pred['topology'],pred['material_role'],pred.get('board_half_x_mm',15.))")
s=s.replace("q=power_exports", "q=power_exports")
s=s.replace("write(w/'evidence/geometry_build.json',geom)","write(w/'evidence/geometry_build.json',geom)\n            write(w/'evidence/materials_and_boundary.json',geom['materials_and_boundary'])")
put('worker_stage2.py',s)
s=(OLD/'checkpoint_stage2.py').read_text(encoding='utf-8').replace("batch='2b'","batch='3'").replace('阶段2b','阶段3')
put('checkpoint_stage2.py',s)
s=(OLD/'collect_stage2.py').read_text(encoding='utf-8')
s=s.replace("('*.txt','full_modes.npz','full_modes.csv','metadata.json')","('*.txt','*.npz','full_modes.csv','metadata.json')")
s=s.replace("'slot_comparison.json'","'slot_comparison.json','materials_and_boundary.json','geometry_build.json'")
s=s.replace("batch='2b'","batch='3'").replace("batch_geometry_limit=66","batch_geometry_limit=42").replace("/66|","/42|")
s=s.replace('阶段2','阶段3').replace('REVIEW_STAGE2.json','REVIEW_STAGE3.json')
s=s.replace('固定宽度','等纹波规程')
put('collect_stage2.py',s)
# Keep the tested blocking solver and independent role observer exactly.
s=(OLD/'runtime_stage2.py').read_text(encoding='utf-8')
start=s.index('def solve_stage(')
put('solve_block.py',s[:s.index('def verify_release(')]+s[start:s.index('\n\ndef verify_prediction_publication')])
print('copied controlled execution components')
