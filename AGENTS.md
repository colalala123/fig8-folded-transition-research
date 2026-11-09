# Repository operating rules

This is a research archive, not an active simulation queue. Work on repository files/offline analyses only unless the human explicitly authorizes new solver work. Preserve the old whole-batch pause and the closure of the diagnostic/single-case branches.

Never execute archive/*.py.txt or any historical continuation instruction. Never reset run markers, forge ACKs, clear project locks, reuse original host IPC identities, or start/restart HFSS based on archived files. Do not send hook messages without explicit target authorization.

Keep uniform-model data separate. Do not overwrite frozen model/data/results; write new experiments to a new directory and label training, retrospective holdout, prospective test, and tuned data honestly. A negative design result may be valid data. Nominal interpolated pass is not a direct-frequency, convergence, or manufacturing certificate.

Default verification: `python tests/test_research.py` and `python tools/verify_archive.py` (offline). No test may launch HFSS or network messages.
