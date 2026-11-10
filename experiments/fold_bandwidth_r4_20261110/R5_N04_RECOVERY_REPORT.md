# R5 batch 1a — N04 cache recovery and verification

**N04 passed the R5 baseline gate and the nominal interpolated design gate.** This is a completed baseline, not completion of all of batch 1a.

The recovery opened a separate byte-verified copy of the interrupted project and its result directory. Before any Analyze it re-exported and matched all 16 convergence rows. It did not edit geometry or repeat any of those passes. Six continuations added exactly one pass each (10%, 10%, 10%, 5%, 5%, 5%). Sweep1 ran once at the final mesh and left the 22-row history unchanged. Independent OS evidence on each call verified owned HFSS processes, actual 14 cores / one group, and case-isolated scratch. The source cache still matches its original manifest.

| Metric | Archive N04_A18 | Original R4 diagnostic | R5 recovered |
|---|---:|---:|---:|
| Adaptive passes | 21 | 32 | 22 |
| Solved Elements | 101,852 | 96,396 | **100,374** |
| Final ΔS | 0.0021 | 0.0045884 | **0.0015121** |
| Low/high inner S11 peaks (dB) | −20.854 / −20.432 | −20.544 / −20.339 | **−20.676 / −20.321** |
| Central valley (GHz) | 6.74 | 6.73 | **6.73** |
| BW15 (GHz) | 6.324987 | 6.319224 | **6.325672** |
| BW20 (GHz) | 6.001733 | 5.995590 | **6.004205** |

Inside the archive −15 dB main passband, max complex differences were **0.0031494 for S11** and **0.0005122 for S21** (both ≤ 0.005). The valley is 10 MHz lower (inclusive limit), and BW15 is 0.685 MHz wider. The inner peak differences (+0.178/+0.111 dB) are reported but are not R5 gates; an R1 comparison that used the old 0.1 dB thresholds is not the acceptance decision. The slot comparison, mesh, ΔS, and S-parameter gates all passed. The exported S11/S21 plot was inspected. BW20 is the R2 main-component nominal interpolated bandwidth, not direct-frequency or manufacturing certification.

**Budget at this checkpoint:** 2/186 geometry attempts, including the original R4 diagnostic; batch 1a 2/4. Actual Analyze requests: 9 total (1 R4 + 8 R5 N04). This recovery added 7 requests to the existing R5 geometry, not a new geometry. N14 and N08 were unstarted at the checkpoint. Next is N14, then N08 only if N14 passes.

Evidence and hashes: `r5_cache_results/S1_BASE_N04/`. The previous R5 interruption and R4 diagnostic remain intact.
