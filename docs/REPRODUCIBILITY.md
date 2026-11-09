# 离线复现与数据说明

## 数据边界

`model/dataset.npz`包含80个几何，`model/DATASET.json`提供几何、P/R、家族、来源及评分。

- 78开发：原48采集+30调谐几何，共24宽度家族。
- 2回顾性留出：N19_A14_D1、N22_A18_D1，结果此前已知，不是前瞻盲测。
- `data/raw/INV01_A14`是模型冻结后的单例，**没有加入训练数组或重新拟合**。
- `data/RAW_INDEX.json`列出81条原生曲线，按原始SHA256核对。
- 更早24/34/18阶段另存archive，不与上述80直接堆叠，避免重复和不同验收口径混合。

NPZ主数组：X为5维特征；Z为复数S11/S21（几何×频率×2）；f为GHz频率；Y为5个指标。公式NPZ中intercept为频率×2，coefficients为5×频率×2。

## 预测和验证

按README安装环境后运行：

```bash
python tests/test_research.py
python analysis/predict_response.py --Wm 1.9136201833872932 --Ws 0.34596701899421023 --Lm 6.584499793266415 --Ls1 12.619994699196244 --Ls2 1.2419340379884205 --Ls3 1.74596701899421
python tools/verify_archive.py
```

预测仅需NumPy/SciPy和纯数学模块，不反序列化joblib。附带历史joblib只供可信归档的训练回放；不要加载未知来源pickle/joblib。

接口可改变检查的频率窗，但中心谷/材料/模型仍固定，**不代表支持任意目标频率或自动综合任意指标**。完整形状检查沿用冻结定义。超出联合四维凸包、未支持折臂、非法几何会拒绝。

## 训练与逆向计算回放

```bash
python tools/reproduce_offline.py --output-dir scratch/training --mode train
python tools/reproduce_offline.py --output-dir scratch/inverse --mode inverse
```

输出目录必须不存在，禁止覆盖冻结model目录。train模式在新目录重跑A/B/C嵌套分组验证和C0同输出消融；inverse模式从已冻结可信C模型回放唯一目标的离线候选搜索与条件式。均无HFSS控制调用、无通知。

训练为6外层×3内层家族折；degree=1/2，alpha=.001/.01/.1/1/10，预处理折内拟合，按家族均衡。正式部署C选degree1、alpha.01。组划分详情在FOLDS_AND_TUNING.json。数组来源与评分不可在看了新单例后悄悄修改。

## 移植改动

原始代码保持在archive（`.py.txt`）；analysis版本有明确工程性改动：

- 去除F/D盘硬编码和本机依赖目录，数据目录由仓库位置或`FIG8_MODEL_DIR`决定。
- 将旧控制文件里的纯评分函数以AST抽出，避免导入控制器产生副作用。
- 原训练结尾的旧磁盘/暂停文件哈希检查改由仓库归档校验与原生曲线哈希检查负责；没有伪造旧环境存在。
- 不改特征、评分阈值、家族划分、超参集合或冻结模型系数。
- 新训练产物只能写入独立目录，不覆盖原结果。

`provenance/VALIDATION.json`记录本次实际运行过的测试。提供了训练回放脚本不等于已在所有操作系统验证；运行平台和版本见该记录。

## 归档哈希与脱敏

SOURCE_MANIFEST保留原文件SHA和归档SHA。聊天ID、个人路径等文本脱敏会改变归档字节，因此旧ACK里原哈希不一定能对脱敏JSON逐项重放；不能把这种预期变化误报为原始审核失败。原生S参数CSV和最终AEDT工程不改字节。

ARCHIVE_MANIFEST覆盖交付文件，verify_archive逐项核验。历史路径`${WORKSPACE}`是来源占位，不是另一台电脑上的有效路径。历史源码归档不是可直接执行的工程环境，复现入口只限analysis和tools中明确说明的离线工具。
