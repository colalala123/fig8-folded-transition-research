# R1 六项离线交付 — 审核入口

先读 [REPORT.md](REPORT.md)，再读 [STAGE0_STATUS_R1.json](STAGE0_STATUS_R1.json)。
依据为 `docs/PLAN_20261110_FOLD_BANDWIDTH_R1.md` 第 4 节；从
`origin/claude/fold-bandwidth-plan` 的 `c0160d6` 新建分支
`codex/fold-bandwidth-r1-offline`。本目录是新产出，旧冻结、旧模型和旧批次不变。

**没有启动 HFSS、Analyze 或 hook。所有登记和预算均未获求解授权。推送是交付通知。**

| 任务 | 审核入口 |
|---|---|
| R1-1 | `prepare_designs.py`、`freeze_r1/predictions_frozen.json`、`design_list.csv`、`FREEZE_HASHES.json` |
| R1-2 | `chain.py`、`evidence_r1/LENGTH_EQUIVALENCE_80.csv` |
| R1-3 | `extract_run.py`、`replay_r1/REPLAY_CHECK.json`、`EXTRACTED_80.json` |
| R1-4 | `analyze_stage1.py`、`STAGE1_CRITERIA.json`、`evidence_r1/STAGE1_SYNTHETIC_*` |
| R1-5 | `geometry.py`、`freeze_r1/SLOT_BOXES.json`、`slot_boxes.csv`、`evidence_r1/INV01_BOX_COMPARISON.json` |
| R1-6 | `test_r1.py`、`validation_final_r1/`、`STAGE0_STATUS_R1.json`、`MANIFEST_R1.json` |

## 离线复跑

在仓库根目录，使用仓库 requirements 的依赖及阶段 0 的 jsonschema 依赖。
本次实测环境见验证记录（Python 3.12.13、NumPy 2.2.6、SciPy 1.17.1）。

```sh
python experiments/fold_bandwidth_r1_20261110/test_r1.py
python experiments/fold_bandwidth_phase0_20261110/test_phase0.py
python tests/test_research.py
python tools/verify_archive.py
```

重新生成时必须用新目录；不覆盖已提交证据：

```sh
python experiments/fold_bandwidth_r1_20261110/prepare_designs.py --out scratch/r1-freeze-recheck
python experiments/fold_bandwidth_r1_20261110/extract_run.py --archive-replay --out scratch/r1-replay-recheck
python experiments/fold_bandwidth_r1_20261110/build_evidence.py --out scratch/r1-evidence-recheck
python experiments/fold_bandwidth_r1_20261110/verify_r1.py --out scratch/r1-validation-recheck
```

所有输出使用排他创建；存在就报错。`prepare_designs.py` 不派发任务，也不生成/打开 AEDT 工程。

## 单次运行的全模式输入协议

NPZ（`allow_pickle=False`）：

- `f_GHz`：严格递增频率，覆盖 2–11.5 GHz；推荐完整 0.01–15 GHz。
- `S`：复数 `[频率, 出射模式, 入射模式]`，后两维均为 4。
- `propagating`：布尔 `[频率, 模式]`，来自原生模式证据；不能凭幅值猜测。

对应 metadata JSON：

```json
{
  "case": "EXAMPLE_NOT_RUN",
  "geometry": {"Wm": 1.8, "Ws": 0.4, "Lm": 6.6, "Ls1": 12.3, "Ls2": 1.35, "Ls3": 2.2},
  "mode_order": ["1:1", "1:2", "2:1", "2:2"],
  "matrix_convention": "output,input",
  "normalization": "power_waves"
}
```

```sh
python experiments/fold_bandwidth_r1_20261110/extract_run.py --input scratch/run.npz --metadata scratch/run.json --out scratch/extracted.json
```

不提供猜测 HFSS CSV 表头/模式编号的自动转换器。实际导出时必须核验模式索引、功率归一化和传播状态，再组装输入。`S[:,0,0]`、`S[:,2,0]` 是基模反射/传输。

全传播时全模式剩余功率就是 `1-sum(abs(S[:, :, 0])**2)`。有倏逝模式时另存全系数平方余量，物理出射功率只累加传播通道；入射基模不传播的频点记空。两者不冒充同一种功率。归一化未知直接拒绝。负余量不截断，留作数值诊断。只有材料确实无耗时，物理余量才可解释为辐射加数值误差。

归档只有基模 S11/S21，因此 `EXTRACTED_80.json` 中全模式余量为 null。完整算法用明确标为 SYNTHETIC 的数据验收，不制造“新 HFSS 证据”。

## 阶段 1 输入协议

`analyze_stage1.py --input INPUT.json --out NEW_OUTPUT.json` 接受三个数组：
`archive`（三个基准归档）、`baseline`（三个新基准）、`perturbations`（九个宽度阶梯）。
每个 envelope 有 `id`、`geometry_mm`、`metrics`；新运行另需 `mesh_cells`、
`MaxDeltaS`、`sweep_low_GHz`、`sweep_high_GHz`。具体可读合成输入示例。
`metrics_from_extraction()` 可从单次提取记录生成 metrics。基准归档和新运行须采用同版提取器，不能把旧单起点拟合与新多起点拟合混为噪声。

两个内峰分别比较（防止均值抵消）；宽度阶梯的线性残差 SD 用自由度 7，二次用自由度 6。
微扰对的斜率采用固定对称九点全阶梯 OLS；在这个对称设计中线性、二次斜率一致，两个结果都报。
这不是不依赖任何估计的噪声方差：单对差值不会冒充统计 σ。
任一指标样本为空，就不对该指标拟合；不补零、不丢点重拟合。三项报告不混合。
文档没有给噪声/零重复的数值合格阈值，代码也不擅自添加。`offline_ready_for_review` 不是求解授权。

## 冻结与后续边界

- `freeze_r1/` 为先验。2b 必须在 2a 后、阶段 4 必须在阶段 2/3 后重新冻结真正前瞻预测；不能用现在的先验替代。
- 直槽和两次边界对照保持独立拓扑/目录；不使用用户另一套均匀模型数据。
- 两次边界对照分别绑定 `S2_E0_N14` 的最终直槽几何和 `S1_BASE_N14` 的 a=1.8 几何，材料不变，只改基板和空气盒的 x 边界。当前坐标是条件先验。
- 无耗对照也须绑定父项的**最终**调准几何，不能盲跑目前初值。
- `geometry.compare_boxes()` 的 1e-8 mm 容差用于 AEDT 文本输出舍入；新工程求解前必须比较真正从目标设计导出的操作数，而不是把本坐标表同自己比较。操作数吻合不等于最终实体拓扑认证。
- 每次真实 Analyze 调用均应计数。第 5 节的新预算不能借用旧批；本文不授权任何一次调用。
- 推送后停止，等待审核和用户对下一批的直接授权；不修复/启动桌面工具，不创建定时任务或通知其他聊天。
