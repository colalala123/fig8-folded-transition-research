# Fig8首批24配置收尾

更新：2026-10-25T00:40:48+09:00（日本时间）

只处理弯折数据。保留旧验收记录；本表新增结果限定为原生基模S11/S21研究用途，不冒充完整多模网络验收。

状态计数：{"preserved_design_failed": 2, "scoped_accepted": 14, "preserved_accepted": 4, "bounded_design_failed": 3, "unresolved_numerical": 1}

| 配置 | 当前状态 | 下一步/结果 |
|---|---|---|
| D01G02 | preserved_design_failed | preserve |
| D01G05 | scoped_accepted | same_mesh_direct_checked_and_design_passed；临界达标：直接采样峰差0.495173 dB，非充足裕量设计 |
| D02G02 | preserved_accepted | preserve |
| D02G05 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D03G02 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D03G05 | preserved_accepted | preserve |
| D04G02 | bounded_design_failed | bounded_design_not_met_no_full_second_cycle_fits |
| D04G05 | preserved_accepted | preserve |
| D05G02 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D05G05 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D06G02 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D06G05 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D07G02 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D07G05 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D08G02 | preserved_accepted | preserve |
| D08G05 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D09G02 | bounded_design_failed | bounded_design_not_met_and_direct_missing_10p19GHz |
| D09G05 | bounded_design_failed | bounded_design_not_met_no_full_second_cycle_fits |
| D10G02 | scoped_accepted | same_mesh_direct_checked_and_design_passed；临界达标：直接采样峰差0.494268 dB，非充足裕量设计 |
| D10G05 | scoped_accepted | final_geometry_and_same_mesh_direct_checked_design_passed |
| D11G02 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D11G05 | unresolved_numerical | design_supported_but_12GHz_out_of_band_complex_check_failed |
| D12G02 | scoped_accepted | same_mesh_direct_checked_and_design_passed |
| D12G05 | preserved_design_failed | preserve |

## 当前工作项
{
  "stage": "batch_complete",
  "operation_status": "completed",
  "all24_design_accepted": false,
  "case": "D04G02",
  "run_dir": "J:\\f8_finish24_261023\\D04G02\\c01_candidate",
  "counts": {
    "preserved_design_failed": 2,
    "scoped_accepted": 14,
    "preserved_accepted": 4,
    "bounded_design_failed": 3,
    "unresolved_numerical": 1
  },
  "finished_at": "2026-10-24T15:40:48.727215+00:00",
  "closure_path": "${WORKSPACE}\\output\\fig8_finish24_20261023\\batch_closure.json",
  "closure_sha256": "b918a657df93368ed4a84e5cc3b0de8f66629514f54ad6f191c7363541d559d4"
}

## 执行边界
- 每配置/工作项结束由hook通知本对话，再核验结果和推进下一项。
- 4个历史合格及2个历史失败保留，不为了凑网格数重跑。
- 新几何目标10–11万网格；用户已批准11.2万以内的轻微超限并记录；既有缓存核验不重新自适应。
- 不因ΔS标记或高阶通道完整矩阵报警单独触发无限返工；异常定位与基模证据独立记录。
- 24配置收尾完成不等于24个全部设计成功，也不等于跨宽度规律已经验证。
