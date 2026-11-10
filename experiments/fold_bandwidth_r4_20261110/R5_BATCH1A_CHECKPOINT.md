# R5 batch 1a — ten-Analyze checkpoint

**N04 is complete and accepted under R5. N14 is technically stopped after its first Analyze. N08 has not started.** No solver remains active.

- N04: [cache recovery, three-way comparison and evidence](R5_N04_RECOVERY_REPORT.md). Reopened 16 matching rows and finished at 22 passes, 100,374 solved elements, ΔS 0.0015121. R5 baseline and nominal design gates both passed. The recovery did not consume a new geometry slot.
- N14: a new isolated cold project was run once with the planned 16-pass, 30% initial setup and Sweep1 off. AEDT reported the setup completed in 4 min 57 s. All 49 observed owned processes used the case scratch directory. 48 matched the 14-core/one-group command signature; the first did not. Its exact command/role was not retained, so this is neither proof of a reduced-core solve nor enough evidence to exempt that process. The conservative verifier stopped before accepting the adaptive history, requesting another pass, or running Sweep1. The project and its cache were preserved; the solver closed and scratch preferences were restored. N14 has no evaluated numerical, design or baseline pass.
- Do not rerun or bypass the failed evidence guard. First determine how to distinguish a native preparation process from an adaptive solver using retained command-role evidence. If a separate N14 recovery is authorized, re-export and validate its preserved convergence history before any Analyze; stop if the cache is not usable.

**Accounting:** 3/186 geometry attempts (3/4 batch 1a) including the original R4 N04; 10 actual Analyze requests (1 original R4 N04, 8 R5 N04, 1 N14). N08 and later batches remain unstarted. Both the historical N04 and the new N14 stop records remain unchanged.
