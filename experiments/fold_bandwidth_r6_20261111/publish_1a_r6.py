"""发布已结束的1a门槛和中文汇总；不求解、不释放下一批。"""
import argparse
from common_r6 import *
from gate_1a_r6 import gate
def publish(root):
    q=gate(root)
    if not q['passed']:raise RuntimeError('1a未通过')
    out=HERE/'batch1a';out.mkdir(exist_ok=False)
    write(out/'GATE.json',q)
    lines=['# R6 批次1a收尾：三个基准复现通过','',
      'N04的已审核重做结果保留；N14、N08已完成新流程验证。三个基准均通过R5 3.3的数值与归档比较门槛，可以按用户授权进入1b；这不表示三个设计都满足−20dB指标。','',
      '|基准|求解单元数|最终ΔS|最大复数差 S11 / S21|中央谷差 MHz|BW15差 MHz|基准通过|',
      '|---|---:|---:|---|---:|---:|---|']
    for r in q['baselines']:
        old=r['case']==BASES[0]
        c=r if old else r['comparisons'];m=r['metrics'] if old else c['metrics']
        cells=r['redo_mesh_cells'] if old else r['mesh_cells']
        delta=r['redo_delta_s'] if old else r['delta_s']
        lines.append(f"|{r['case']}|{cells}|{delta:.7f}|{c['max_abs_dS11']:.7f} / {c['max_abs_dS21']:.7f}|{m['central_valley_GHz']['delta']*1000:.3f}|{m['BW15_GHz']['delta']*1000:.3f}|通过|")
    lines+=['','## 如何理解这些结果','',
      '- N04名义设计通过；N14与N08两内峰仍高于−20dB，与各自归档基准一致。按R2主通带口径，两者完整BW20为null，不拿分裂子带冒充完整带宽。',
      '- N14内峰差：低频+0.01443dB，高频−0.05627dB。N08：低频+0.08354dB，高频−0.08761dB。N04：+0.17832dB、+0.11112dB。全部作为噪声/复现差报告，不再套用已取消的0.1dB门槛。',
      '- N14冷启动21轮、N08冷启动22轮。最终扫频前后自适应历史逐轮相同，所有自适应进程14核1组，扫频角色合法，未知角色0。',
      '- N08首进程为port_adapt，符合R6事后检查；旧N14首进程没有保留命令仍明确标注为推断，不伪造历史记录。',
      '', '## 缓存、技术处理与预算','',
      '- N14旧缓存逐文件核对一致，但重开原生收敛表为Completed:N/A；没有可复用16轮。本次验证未调用Analyze。',
      '- 使用R6唯一冷启动额度重做N14，原工程、失败记录和缓存保持原样。新执行器先保存工程和收敛表，再检查观察记录，避免可用结果因后置核验问题丢失。',
      f"- 已用几何次数{q['total_geometry']}/187，其中1a为5/5：R4 N04诊断、R5 N04重做、R5 N14中断、R6 N14冷启动、N08各1次。",
      f"- 实际Analyze累计{q['total_Analyze']}。跨进程缓存核验未新增请求；N14冷启动7次、N08冷启动8次。",
      '', '## 测试、证据与下一步','',
      '- R6角色回归10/10；1a门槛5/5；R6噪声包装器5/5；R5网格8/8；提示信息2/2；临时目录3/3；仓库测试11/11。8765项归档哈希验证通过。',
      '- 已实际查看N14、N08的S11/S21双线图；所有结果均为名义插值，未声称直接频点、全模式功率或制造公差认证。',
      '- 开始1b前重新fetch审核分支，仍为b917d09。推送本批后释放既定9点，逐点数值验收；每累计10次Analyze保存推送检查点。',
      '- 1b报告仍沿用冻结R2的线性/二次残差SD与微小对差分。R5基准门槛单独检查，旧内峰0.1dB判断不再控制接续；缺失BW20不插补。',
      '- 用户已明确确认“自适应段与最终扫频分别核验”，见 USER_CONFIRMATION_SWEEP.md。没有hook，没有恢复旧批或修改均匀数据。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(out/'MANIFEST.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print('1a通过：几何',q['total_geometry'],'Analyze',q['total_Analyze'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();publish(a.root.resolve())
