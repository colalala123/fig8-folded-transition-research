# R5 — Batch 1a prelaunch freeze

Source: `claude/fold-bandwidth-plan` at `c4f0667`; direct user approval of the R5 accounting and one N04 redo. The R4 numerical stop, first N04 result (96,396 elements), and R4 ledger remain immutable. The new R5 runtime carries over one geometry and one actual Analyze call. Batch 1a permits four geometry solves including the historical result; overall ceiling 186. Physical calls are counted separately, including failures.

Sequence: N04 redo → N14 → N08, gated on R5 baseline comparability. Each fresh project starts with no solution files and runs in an independent headless AEDT. Initial 16/30%, continuations +1/30%, 10%, or 5% as R5 prescribes (maximum 12). Verify saved solver settings and prior convergence history before and after each continuation. Enable Sweep1 without changing adaptive settings; require identical convergence history after sweep. Each Analyze blocks; assert scratch directory readback and verify real 14-core/one-group owned process evidence. Keep all full-mode S, Zo and Gamma; no power-normalization claim. No old batch, hooks, or uniform data.

Gate: native slot geometry, 100,000–112,000 Solved Elements, ΔS ≤ 0.005, same-grid complex S11/S21 comparison inside the archive −15 dB main component, and the R5 valley/BW15 limits. Peak dB differences are descriptive only. Negative design performance is distinct from invalid numerical data. First R4 run remains diagnostic only.

Prelaunch verification: eight R5 offline tests, 11 repository tests, all 8,765 protected archive hashes. No Analyze in preparation. R4 §6 assumptions retained.
