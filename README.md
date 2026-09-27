# Sovereign Core

A discrete, integer-state, evolutionary neural substrate. Pure Python stdlib, no numpy/torch.

**This is not a transformer and does not use backpropagation.** It's small computational units
("Bricks", integer states in [0,31]) wired by evolvable "PairedRelay" connections, learning via
local per-unit prediction-error tracking plus fitness-driven mutation/selection/culling, with
periodic "sleep" consolidation phases (replay known tasks, cull the worst-scoring cells, clone the
best-scoring cells into freed slots, occasionally grow real new capacity by cloning
top-performing modules into brand-new ones).

## Origin

This mechanism was originally built and proven working in 2026, then lost when an earlier AI
session falsely claimed to have saved it. It survived, unrecognized, across a version lineage
(`Max_sovereign_core_v4.py` through `v4_3`/`v4_21`) until it was rediscovered, tested, and
confirmed running on 2026-09-27. This repository exists so that does not happen again.

## Status

Recovered and running. Two real regressions found and fixed since recovery (see git log and
`EXTERNAL_REVIEW_DRIFT_BETWEEN_SLEEPS.md` for the still-open drift investigation). This was
always a proof-of-concept-scale demonstration (hundreds of bricks, moderate cycle counts) — never
a claim of a full production-scale model.

## Run it

```
python sovereign_core.py --cycles 2000
```

## License

[PolyForm Noncommercial 1.0.0](LICENSE.md) — free to use, modify, and share for any noncommercial
purpose. Not licensed for commercial use.
