# R5 batch 1a — N04 interrupted after the first mesh stage

**Status: stopped; no N14/N08 dispatch.** This is a technical interruption in the runner, not a failed geometry or a failed final numerical gate. No valid final sweep was produced.

| N04 metric | Archive N04_A18 | Original R4 cold start | R5 redo |
|---|---:|---:|---:|
| Adaptive passes | 21 | 32 | 16, first stage only |
| Solved Elements | 101,852 | 96,396 | 56,998, intermediate |
| Last recorded ΔS | 0.0021 | 0.0045884 | 0.016087, intermediate |
| Low / high inner S11 peaks (dB) | −20.85 / −20.43 | −20.54 / −20.34 | No sweep |
| BW20 (GHz) | 6.002 | 5.996 | No sweep |
| BW15 (GHz) | 6.325 | 6.319 | No sweep |

## What actually happened

1. Native slot-box comparison passed at 1e−8 mm. The cold-start stage used 16 minimum/maximum passes, 30% refinement, ΔS target 0.005, two consecutive passes, and disabled Sweep1. Independent OS evidence verified that real owned HFSS solver processes used **14 cores / one group** and the new per-case scratch directory. AEDT scratch readback and native process scratch both agreed. AEDT closed and the previous scratch preference was restored.
2. HFSS reported normal completion of the first adaptive stage in 3 min 57 s. An intermediate ΔS above 0.005 at 16 passes is not a final failure: R5 calls for continuation at 10% here (56,998 elements, below 80,000).
3. The runner queried the **whole** design message buffer after Analyze. It attributed a **pre-Analyze** “No trace data for quantity S(1:1,1:1)” message from the cold project solved-status probe to the stage. This false attribution stopped continuation even though the native stage returned normally. The in-worker process observer also wrote zero rows; an independent read-only observer captured verified native processes. The cause of the in-worker observer's missed samples is not established. The independent evidence is supplemental, not substituted into the failed runner's files.
4. The saved project, first-stage cache and original terminal artifacts are preserved. There was **no continuation Analyze and no Sweep1 request**. The R5 final mesh/baseline gate and design gate are **not evaluated**. The R4 original remains diagnostic only.

## Accounting and recovery boundary

- **2 / 186 geometry attempts charged**, **2 / 4** for batch 1a, including the original R4 run. **2 actual Analyze calls** campaign-wide, including 1 in this R5 attempt.
- The one authorized N04 redo has been started. R5 specifies one worker/process for all segments, and the worker has exited. Neither a fresh N04 redo nor a cross-process cache continuation was started.
- Proposed recovery, **only after explicit authorization to cross the process boundary**: verify a read-only reopen of a preserved copy reproduces all 16 rows; if intact, start at pass 17 with 10% and Sweep1 disabled, preserving the same geometry and recording any subsequent Analyze calls under the same attempt. Keep the existing 12-continuation cap and one final sweep. If cache validation fails, stop without a fresh solve.
- Offline mitigation provided: stage-scoped message differencing (preserves repeated new errors), plus an independent OS-only process observer. For a future runtime revision, remove the solved-status trace probe on a verified fresh project; wire the observer outside the blocking worker and require owned process evidence per Analyze. Neither mitigation has been enabled in the frozen attempt.

Evidence in `r5_n04_interruption/`: native first-stage convergence, native messages, stage settings without local paths, budget/stop summary and independent observation counts. No partial result enters training or the stage-1 noise estimate.
