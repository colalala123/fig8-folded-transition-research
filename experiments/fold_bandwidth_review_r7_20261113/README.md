# R7 审核的复核数据

离线，只读仓库里已提交的结果，不启动 HFSS，不发消息。对应 `docs/PLAN_20261110_FOLD_BANDWIDTH_R7.md`。

运行：`python review_checks.py`，结果写到 `out/`。

| 文件 | 内容 |
|---|---|
| `out/ALL_GEOMETRIES.json` | 103 个完成求解的几何：尺寸、中央谷、两个内峰、BW15、BW20、BWref、网格、ΔS |
| `out/SUMMARY.json` | 网格和 ΔS 的范围；与执行者记录的内峰、BW15 的最大差 |
| `out/TRADEOFF.json` | 纹波与带宽的折算斜率；各平衡点折算到 −20.3 dB 的 BW15（R7 第 2.3 节） |
| `out/SENSITIVITY.json` | 调参灵敏度的回归和所用的 37 步（R7 第 2.2 节） |
| `out/EXAMPLE_FIRST_STEPS.json` | 既有可用点；8 个新设计按 J0 算的第一步改动量（R7 第 3.2、3.3 节） |

全部是回顾性分析：口径是看了数据之后定的，不能当作已验证的规律。
