# 阶段0审核入口

**先读 [REPORT.md](REPORT.md)**，再读 [geometry_convention.md](geometry_convention.md)。
这是原计划的离线审计与工程准备，不是新的HFSS启动授权。

当前状态：离线交付完成；live CAD核验、g效应建模、正式阶段4冻结与部分候选筛选问题尚未解除。
原计划和冻结模型/数据/工程均未修改。

## 文件导航

- `chain.py`：带范围保护的正向/逆向规律链，等频闭式连通带宽。
- `audit.py`、`audit_results/`：原脚本复现比对、80条回代、6起点提取、78开发点分组CV、几何静态证据。
- `reproduction/`：原脚本本机新输出，不覆盖Claude的out。
- `prepare_designs.py`、`freeze/`：77条离线登记及不可执行先验冻结；5条几何排除；系数和源文件哈希。
- `review/SCREENED_CANDIDATES.csv`：移除5个rho失败项后的72条待审候选，仍没有执行权限。
- `RUN_RECORD_SCHEMA.json`、`RUN_DIRECTORY_RULES.md`：新批数据契约和目录/预算/暂停/hook约束。
- `test_phase0.py`、`VALIDATION.json`：阶段0测试及默认测试证据。
- `PHASE0_MANIFEST.json`：本阶段新增交付文件哈希，不替换原归档manifest。

## 离线复核

安装仓库`requirements.txt`及本目录`requirements-extra.txt`，从仓库根执行：

```sh
python tests/test_research.py
python tools/verify_archive.py
python experiments/fold_bandwidth_phase0_20261110/test_phase0.py
```

重新计算审计/先验时**用不存在的新目录**（audit和prepare会拒绝已存在目录）：

```sh
python experiments/fold_bandwidth_20261110/offline_fold_analysis.py --out experiments/fold_bandwidth_phase0_20261110/rerun_original
python experiments/fold_bandwidth_phase0_20261110/audit.py --out experiments/fold_bandwidth_phase0_20261110/rerun_audit
python experiments/fold_bandwidth_phase0_20261110/prepare_designs.py --out experiments/fold_bandwidth_phase0_20261110/rerun_proposals
```

`audit.py`固定读取提交的`reproduction/`，以便其比对对象明确；第一条命令的新复现目录可独立与它比较，
不要把新结果覆盖回`reproduction/`或`freeze/`。
原脚本自身允许覆盖输出目录，因此第一条也应由操作者保证使用不存在的目录。
当前所有代码只做本地数组/文本计算，没有HFSS、网络或hook调用。

本目录本地开发中的`proposals/`和`proposals_v2/`为未提交草稿，被忽略；只有`freeze/`为本次审核版。
