# R2 离线交付入口

依据：`docs/PLAN_20261110_FOLD_BANDWIDTH_R2.md` 第 3 节。
基点：`claude/fold-bandwidth-plan@5ad28a8`。
分支：`codex/fold-bandwidth-r2-offline`。

先读 [REPORT.md](REPORT.md) 和 [STATUS_R2.json](STATUS_R2.json)。
**没有仿真、没有 hook。推送后停止审核；旧批保持暂停。**

| 项目 | 代码 | 证据 |
|---|---|---|
| R2-1 主通带判断 | `chain.py` / `extract_run.py` | `replay_r2/fold_table_r2.csv`、`REVIEWER_COMPARISON.json` |
| R2-2 不同参数解判据 | `extract_run.py:basin_audit` | `replay_r2/EXTRACTED_80.json`、`REPLAY_CHECK.json` |
| R2-3 每次提交前筛选 | `presubmit.py:presubmit` | `evidence_r2/PRESUBMIT_EXAMPLE.json`、`PRESUBMIT_INITIAL_79.json` |
| R2-4 浮点可移植性 | `portability.py` / `test_r2.py` | `evidence_r2/REGISTRY_PORTABILITY.json`、`validation_r2/` |

## 离线重放命令

在仓库根目录，使用已有 requirements 和阶段 0 的 jsonschema 依赖：

```sh
python experiments/fold_bandwidth_r2_20261110/test_r2.py
python experiments/fold_bandwidth_phase0_20261110/test_phase0.py
python tests/test_research.py
python tools/verify_archive.py
```

重新生成必须写入新目录，不能覆盖已交付证据：

```sh
python experiments/fold_bandwidth_r2_20261110/extract_run.py --archive-replay --out scratch/r2-replay
python experiments/fold_bandwidth_r2_20261110/build_evidence.py --out scratch/r2-evidence
python experiments/fold_bandwidth_r2_20261110/verify_r2.py --out scratch/r2-validation
```

实测依赖版本和真实日志见 `validation_r2/VALIDATION_R2.json`。
登记表、阶段 1 判据直接读取未修改的 R1 文件，不重新冻结登记表。
可移植性测试会在临时目录里用独立 Python 进程调用 R1 的**离线**生成器，比较后清理临时目录；不是调用 HFSS 或旧队列。

## R2 单次提取接口

继续使用 R1 的全模式 NPZ + metadata 协议：频率 `f_GHz`、复数 `S[n,4,4]`、布尔 `propagating[n,4]`；模式顺序必须声明为 `[1:1,1:2,2:1,2:2]`，矩阵约定 `output,input`，归一化为 `power_waves`。格式细节见 R1 README。本次未改变功率口径，不伪造归档里缺失的模式。

```sh
python experiments/fold_bandwidth_r2_20261110/extract_run.py --input scratch/run.npz --metadata scratch/run.json --out scratch/extracted-r2.json
```

输出版本为 `R2-extracted-run-v1`，每条包含 `bandwidth_definition` 和 `uniqueness_definition`。

- BW15/BW20/BW_joint：选包含**该曲线中央谷**的连通段，必须同时包含两个内峰频率；否则宽度为空。其他连通段放入 `secondary_components`，不否定主通带。
- 外包络、原始区间、扫频截断标记仍保存；截断结果不进入拟合。
- 仅 S21 带宽不是 R2 第 2.1 节的修改对象，仍按含 6.72 GHz 的传输段定义。
- 5 个独立起点，加 1 个使用第一次拟合结果的精修起点；后者不计作独立起点。`starts` 保留初值、来源、成本、参数、收敛和 `basin_id`。
- 只有相对最优解任一参数偏差 **>1%**，且成本 **≤1.05×最优成本**，才标记提取不唯一。参数组 ID 用按成本排序的代表点作描述性分组；最终判据始终直接比较每个解与最优解，不依赖分组的传递性。

`analyze_stage1.py` 继续读取原 `STAGE1_CRITERIA.json`。用 `metrics_from_extraction()` 转换 R2 提取结果时，会拒绝 R1 版本，防止 BW20 混用。若直接提供 metrics envelope，则调用方仍须保证所有数据来自同版提取器，不能把旧 BW20 数字伪装成 R2。

## 每次求解前的几何函数

```python
from presubmit import presubmit
gate = presubmit(geometry, nominal_a=3.0, tuning_changed=True,
                 topology='folded', board_half_x=15.0)
```

- 每次传入**当次**尺寸，不能沿用登记时或上一尝试的通过结果。
- `can_submit` 只表示本函数的几何筛选通过；`solver_authorized` 始终 false。没有派发/Analyze 接口。
- 只有 `tuning_changed=True` 且失败原因仅为折臂端头净距时，才沿 0.001 mm 网格减小 a，取最大能通过的值。
- 不改变 Wm、Ws、Lm、Ls1、Ls2；只更新 `Ls3=Ws+actual_a`。记录名义 a、实际 a、筛选前后、调整原因和最大性检查；`additional_attempts=0`。
- 非正间隔、基板边界不足、直槽失败等不能用减小折臂解决的问题拒绝放行。没有正的可行折臂时同样拒绝。
- 真实运行器还须核验用户授权、新批预算、原生 CAD 坐标、串行资源等。本离线函数没有被接到任何活动队列，不会恢复旧批。

## 完整性

`MANIFEST_R2.json` 记录新文件及输入/依赖哈希；R1、旧冻结、原模型和原计划未改动。
`fold_table_legacy_compatible.csv` 仅用于历史字段核对，生产分析使用 `fold_table_r2.csv` / `EXTRACTED_80.json`。
