# Sovereign Core

A discrete, integer-state, evolutionary neural substrate. Pure Python stdlib, no numpy/torch.

**This is not a transformer and does not use backpropagation.** It's small computational units
("Bricks", integer states in [0,31]) wired by evolvable "PairedRelay" connections, learning via
local per-unit prediction-error tracking plus fitness-driven mutation/selection/culling, with
periodic "sleep" consolidation phases (replay known tasks, cull the worst-scoring cells, clone the
best-scoring cells into freed slots, occasionally grow real new capacity by cloning
top-performing modules into brand-new ones).

The design philosophy, Jonathan's own framing: this imitates the neural cortex the way a
clean-room reverse-engineering project duplicates an app without its source code — built blind,
from the cortex's observed *behavior* (learning, forgetting, consolidation, teacher/student
roles, predator-prey population dynamics), not from its actual biological implementation.

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

## Real finding, 2026-10-16: the task domain is the variable, not a lost "secret ingredient"

A real question got asked and answered directly: does this substrate's apparent weakness on
language/character-level tasks mean something was lost or done wrong, or does it just need the
right kind of task? Tested both, same proven config (`WOLFPACK_SISTER_MATCH=False`), same 8000
cycles, same held-out evaluation discipline:

| Task | Internal `TaskCorrect` | Exact-match |
|---|---|---|
| Favorite-color recall, character-level (`lucy_favorite_color_core*.py`, 3 variants + the v4.21b lineage) | ~0.2-0.3 | 1.4-4.2% (chance) |
| **The substrate's own original, built-in numeric task** (`lucy_original_numeric_task.py` — 6 fixed `(a,b,c)->d` triples, all the same "+2" rule, never modified from `sovereign_core.py`'s own defaults) | **0.74-0.89** | **peaked 66.7%** |

A real mechanism — bricks that prove reliably high-performing get promoted to a protected
"teacher" role other bricks learn from (`IMMUNE+TEACH`) — fired repeatedly on the numeric task
and never once on any character-level task. An earlier character-level test (2026-10-01, see
git log `eae052e`) already landed at the same "noisy, 0-20%" range the character-level tests
land at today — nothing was lost there; the substrate genuinely engages with the kind of task
it was built for (numeric/bit-level pattern extraction) far more than with character-level
language tasks. Honest limitation: generalization to held-out triples following the same rule
was only 1/4 — real, substantial engagement, not yet clean rule-extraction. Next real question,
not yet tested: does a BIT-level (not character-level) encoding of a language task close this
gap, since the successful task here is fundamentally numeric/bit-pattern shaped.

## Run it

```
python sovereign_core.py --cycles 2000
python lucy_original_numeric_task.py --cycles 8000       # the real positive result
python lucy_favorite_color_core_v2_proven_baseline.py --cycles 8000   # the character-level null result
```

## License

[PolyForm Noncommercial 1.0.0](LICENSE.md) — free to use, modify, and share for any noncommercial
purpose. Not licensed for commercial use.
