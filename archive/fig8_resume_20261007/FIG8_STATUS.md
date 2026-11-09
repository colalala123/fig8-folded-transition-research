# Fig8 simulation monitor

Updated: 2026-10-22 01:42:35 +09:00

Final design results: 6 / 24
Design accepted: 4
Design failed: 2
Numerical/mode review required (not final): 14
Active solve: 
HFSS processes: 

Blank status means no current result/state; historical solves may exist. Review-required cases are not completed configurations.

| Case | Status |
|---|---|
| D01G02 | failed |
| D01G05 | review_required |
| D02G02 | accepted |
| D02G05 | review_required |
| D03G02 | review_required |
| D03G05 | accepted |
| D04G02 | review_required |
| D04G05 | accepted |
| D05G02 | review_required |
| D05G05 | review_required |
| D06G02 | review_required |
| D06G05 | review_required |
| D07G02 | review_required |
| D07G05 | review_required |
| D08G02 | accepted |
| D08G05 | review_required |
| D09G02 | review_required |
| D09G05 | review_required |
| D10G02 | review_required |
| D10G05 |  |
| D11G02 |  |
| D11G05 |  |
| D12G02 |  |
| D12G05 | failed |

Acceptance audit (separate from production design acceptance):
D05G02 : completed; D08G05 : completed

Audit report: ../fig8_acceptance_audit_20261021/验收复核报告.md

Original full-matrix status above is retained. New scoped review decisions:
{"retain_failed":2,"candidate_needs_case_specific_direct_check":11,"retain_accepted":4,"needs_sweep_repair":1,"fundamental_response_checked_needs_geometry_tuning":2,"not_run":4}

Precision/time study (isolated, not production design acceptance):
| Trial | Status |
|---|---|
| M_D05G02 | completed |
| M_D08G05 | completed |
| I_D05G02 | completed |
| I_D08G05 | completed |
| F_D05G02 | completed |

Speed study report: ../fig8_speed_study_20261021/精度放宽测试报告.md

100k mesh bracket study (fixed passes; adaptive nonconvergence is recorded, not auto-repaired):
| Trial | Status |
|---|---|
| N112_D05G02 | completed |
| N090_D05G02 | completed |
| N090_D08G05 | completed |
| N112_D08G05 | Reused completed M_D08G05 |

Mesh study progress: ../fig8_mesh100k_20261022/实时进度.md
Mesh study report: ../fig8_mesh100k_20261022/约10万网格测试报告.md
