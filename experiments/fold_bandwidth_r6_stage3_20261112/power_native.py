"""原生后处理；无Analyze调用，保留Generalized与Power两套数据。"""
import numpy as np
MODES=['1:1','1:2','2:1','2:2']
def export_modes(app,path):
    expr=[f'S({a},{b})' for a in MODES for b in MODES]+[f'{k}({a})' for k in ['Zo','Gamma'] for a in MODES]
    d=app.post.get_solution_data(expressions=expr,setup_sweep_name='Setup19 : Sweep1',domain='Sweep',report_category='Modal Solution Data')
    if not d:raise RuntimeError('没有原生全模结果')
    scale={'GHz':1.,'MHz':.001,'kHz':1e-6,'Hz':1e-9}[d.units_sweeps['Freq']]
    f=np.asarray(d.primary_sweep_values,float)*scale
    cols=[]
    for ex in expr:
        _,re=d.get_expression_data(ex,formula='real');_,im=d.get_expression_data(ex,formula='imag')
        cols.append(np.asarray(re,float)+1j*np.asarray(im,float))
    z=np.asarray(cols).T
    if z.shape!=(1500,24) or not np.isfinite(z).all() or not np.allclose(f,np.arange(1,1501)/100,rtol=0,atol=1e-9):
        raise ValueError('原生模式数据无效')
    np.savez_compressed(path,f_GHz=f,S=z[:,:16].reshape(-1,4,4),Zo=z[:,16:20],Gamma=z[:,20:24])
    return dict(f_GHz=f,S=z[:,:16].reshape(-1,4,4),Zo=z[:,16:20],Gamma=z[:,20:24])
def settings(app):
    d=app.design_properties
    return {k:v for k,v in d.items() if not isinstance(v,dict) and
            (k.startswith(('Use ','Allow ','Calculate ','Perform ','Export ')) or k=='EnabledObjects')}
def power_exports(app,w,get_history,write):
    before=get_history(w/'native/power_history_before.txt')
    original=settings(app)
    if original.get('Use Power S') is not False:raise RuntimeError('原始Generalized设置不符')
    success=False
    try:
        if not app.change_design_settings({'Use Power S':True}) or not app.save_project():raise RuntimeError('Power S设置失败')
        observed=settings(app)
        if observed!={**original,'Use Power S':True}:raise RuntimeError('Power S回读或其他设置改变')
        power=export_modes(app,w/'native/power_modes.npz')
        if get_history(w/'native/power_history_after.txt')!=before:raise RuntimeError('功率后处理改变了自适应历史')
        success=True
    finally:
        restored=app.change_design_settings({'Use Power S':False}) and app.save_project()
        if not restored or settings(app)!=original:raise RuntimeError('原设计设置未恢复')
    restored_modes=export_modes(app,w/'native/generalized_restored.npz')
    with np.load(w/'native/full_modes.npz') as z:
        diff=max(float(np.max(abs(z[k]-restored_modes[k]))) for k in z.files)
    if diff>1e-8:raise RuntimeError('Generalized恢复后数据不一致')
    evidence=dict(native_setting_toggle_verified=success,original_settings=original,
       power_settings=observed,restored_settings=settings(app),history_unchanged=True,
       generalized_restore_max_abs_difference=diff,mode_order=MODES,new_Analyze=0,
       power_normalization='HFSS Use Power S native postprocessing; propagation/incident-source certification remains separate')
    write(w/'evidence/power_export.json',evidence)
    return evidence
