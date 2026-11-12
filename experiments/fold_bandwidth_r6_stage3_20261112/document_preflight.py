"""收集无求解预检证据，设置传输通过和物理合理性失败分别记录。"""
import shutil
import numpy as np
from common_stage2 import *
from power_analysis import power_s_sanity
ROOT=Path('F:/2026-1/circuit/test/output/fig8_r6_stage3_20261112')
out=HERE/'preflight';out.mkdir(exist_ok=False)
for name,label in [('native_preflight_straight','straight'),('native_preflight_lossless_v2','lossless'),('native_preflight_boundary','boundary')]:
    src=ROOT/name
    q=read(src/'NATIVE_PREFLIGHT.json');c=read(src/'cleanup.json')
    if not q['passed'] or not c['released']:raise RuntimeError('原生预检未通过/未释放')
    shutil.copyfile(src/'NATIVE_PREFLIGHT.json',out/(label+'_NATIVE_PREFLIGHT.json'))
z=np.load(ROOT/'power_probe/native/power_modes.npz',allow_pickle=False)
p=power_s_sanity(z)
f=z['f_GHz'];i=int(np.argmin(abs(f-6.72)))
p.update(new_Analyze=0,probe_setting_transport_passed=True,
    physical_sanity_passed=False,source_probe_not_overwritten=True,
    column_sum_at_6p72GHz_input_mode1=float(np.sum(abs(z['S'][i,:,0])**2)),
    generalized_restore_max_abs_difference=read(ROOT/'power_probe/evidence/power_export.json')['generalized_restore_max_abs_difference'],
    disposition='异常Power S不用于辐射推论；不重算旧数据。无耗控制使用严格传播模判别，结论保留截断/边界/数值限制。')
write(out/'POWER_SANITY.json',p)
write(ROOT/'power_probe/PHYSICAL_SANITY_FAILED.json',p)
(out/'POWER_METHOD.md').write_text("""# 功率口径与原生预检
原生设置开关/恢复成功，但Power S数据未通过必要的无源功率合理性检查。两者不能混同。此预检0次Analyze，没有改动旧源工程。

HFSS传播模按1W时均功率归一化，依据：
- https://ansyshelp.ansys.com/public/views/secured/electronics/v242/en/subsystems/hfss/Content/HFSS/PeakVersusRMSPhasors.htm
- https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Content/Modeler/DesignSettingsforHFSS.htm

无耗对照在PEC/介质tanδ及电导率为0、模阻抗近实数且传播常数近纯虚数时，保守标记传播模。近纯虚阻抗且近实传播常数标记截止模。其余频点未知，不参与功率余量定量结论。
只统计被明确判为传播的已声明模式。负余量不强行裁为0，而标不可用。未证明所有可能传播模都已包含；不因此宣布“纯辐射功率已精确分离”。有耗数据不使用本判别。
无耗预检初次被没有材料的端口片阻止，修正为跳过空材料片后在独立v2副本通过；旧失败副本保留，没有提交Analyze。
""",encoding='utf-8')
print(p)
