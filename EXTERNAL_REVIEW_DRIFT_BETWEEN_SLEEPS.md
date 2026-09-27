# External review request: recovered evolutionary-neural substrate still drifts down between consolidation cycles

## Context (read before the code)

This is a real, working, tested piece of software (`sovereign_core.py`, ~1200 lines, pure Python
stdlib, no numpy/torch) that was believed lost, recovered from an earlier archived version, and is
being restored and extended. It is **not a transformer and does not use backpropagation** (its own
header says so explicitly) -- it's a discrete, integer-state ([0,31]), evolutionary substrate: small
computational units ("Bricks") wired by evolvable "PairedRelay" connections, learning via local
prediction-error tracking plus fitness-driven mutation/selection/culling, with periodic "sleep"
consolidation phases (replay all known tasks, cull the worst-scoring cells, clone the best-scoring
cells into the freed slots, occasionally grow real new capacity by cloning top-performing modules
into brand-new ones).

Two real bugs have already been found and fixed, verified by direct before/after test runs (2000
cycles each, `--cycles 2000`), not assumed:

1. **Growth broke the output pathway.** Several places in the code determined "the output module"
   as `module_id == (self.num_modules - 1)` -- fine when the module count never changes, but adding
   real new capacity (growth) increments `num_modules`, silently moving "the output" to a brand-new,
   untrained module every time. FIXED by fixing `self.output_module_id` once at init and never
   recomputing it. Verified: before the fix, `TaskCorrect` crashed from 0.594 to 0.364 immediately
   after the first growth event; after the fix, it went from 0.594 to 0.651 (real recovery, not
   collapse) at the same point in an otherwise-identical run.

2. **A specific "moss/cancer" failure mode, already named in the code's own original comments**
   ("evolution cannot win by 'split constantly + stay calm', that would be the cancer/moss
   failure") turned out to be under-guarded in practice: a relay's fitness only ever got
   updated `if relay.split_count > 0` -- meaning a relay that mutates toward a high
   `split_threshold` and simply never splits is invisible to that whole reward/penalty
   mechanism, making "never act" a risk-free strategy. Added a direct penalty for high
   prediction-error situations where a relay *should* plausibly have split but didn't
   (`missed_split_count`, penalized in the same credit-assignment step). This measurably slowed
   (did not fully stop) the observed upward drift of the population's average `split_threshold`.

## The still-open problem

Even with both fixes applied, `TaskCorrect` (a 0-1 correctness metric averaged across the live
population, printed every 100 cycles) still shows a real pattern across a 2000-cycle run: strong
early (0.77-0.86 in the first few hundred cycles), declining through the run with real but partial
recoveries right after each "sleep" consolidation event, ending around 0.59-0.60 by cycle 2000 --
never fully returning to its early peak.

## A second, real, distinct candidate mechanism found while investigating (not yet fixed)

In the sleep DAG's cull-and-clone step (`_run_sleep_dag`, the "REPLACE-ONLY" block), every weak
cell that gets replaced by a clone of a proven winner is deliberately discounted, not fully
inherited:

```python
slot.recent_task_score = w.recent_task_score * 0.5   # HALVED, not inherited
slot.fitness = w.fitness * 0.6                          # discounted
...
slot.relays = []                                        # relay structure wiped entirely
```

`recent_task_score` only updates slowly per cycle (`b.recent_task_score = b.recent_task_score *
0.7 + max(my_credit, recog_reward) * 0.3`), and the protection floor for surviving the *next* cull
is `recent_task_score >= 0.55` (`WORKING_FLOOR`). A clone of a winner scoring 0.85 starts at
~0.42 -- already below the protection floor, unprotected, and has to slowly re-earn in real cycles
what its "parent" had already proven, while simultaneously starting with zero relay-routing
structure at all (relays are only preserved on the separate *growth* path, added into brand-new
modules -- not on this in-place replacement path).

**This looks like a strong candidate for the repeating post-sleep dip-then-partial-recovery
pattern**, distinct from the moss/split_threshold issue above -- but it has not yet been fixed or
tested, and there may be a real reason for the discount (e.g. preventing a single lucky/overfit
winner from monopolizing the population) that a naive "just inherit fully" fix would break.

## What we're asking

1. Is the `recent_task_score * 0.5` / `fitness * 0.6` discount on clone-replacement the right
   explanation for the residual drift, or is there a third mechanism we're missing?
2. If it is the right explanation, what's the correct fix -- inherit more of the winner's score
   directly, inherit the relay structure on this path too (matching what growth already does),
   add a faster-updating score for freshly-cloned cells specifically, or something else entirely?
3. Is there a principled reason (bet-hedging against overfit winners, preventing premature
   population collapse toward one strategy, etc.) that the ORIGINAL discount might have been
   deliberate, and if so, what's the standard fix for getting that safety property without
   this much performance cost?

Full source attached/pasted below (or see `sovereign_core.py` in the same directory this document
lives in). Real, run test data for both the broken-then-fixed growth bug and the still-open drift
issue is in the conversation history that produced this document; ask for specific numbers if
useful rather than assuming any are omitted here for a reason.
