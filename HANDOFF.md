# Handoff: Lucy on SovereignCore substrate

**✅ PHASE 1 CLOSED, 2026-10-17.** Jonathan's own words: "we grew, we learned, this was good,
perhaps we did not get a product but we learned, our thoughts are stale, record this, and we
start Flybrain." No working product — the bit-level recall task is still chance-level after
everything tried. But real, substantial, properly-recorded growth: three rounds of real engine
bugs found and fixed, a 5-model external review, 8 more concrete bugs found and fixed/reverted,
two new mechanisms built and honestly tested (both real negative results), and — the most
important part — a full reconstruction of Jonathan's actual original design intent for this
substrate, which the current code only partially implements. **Read
`[[sovereigncore_true_design_philosophy]]` (persistent memory) before any future work here.**
Full closing summary: `GALATEA_ENGINEER_DIARY_20261017_SOVEREIGNCORE_PHASE1_CLOSED.txt`. This
file remains the detailed technical record below, preserved in full — not abandoned, closed.

## ⚠️ POSSIBLE PROBLEM, NOT YET TESTED HERE: linear-readout ceiling (found on Flybrain, 2026-10-17)

While testing Flybrain's binary-addition task the same night, a real, confirmed cause was found
for a structurally similar failure: a FIXED reservoir + LINEAR readout cannot learn a parity/XOR-
type function no matter how clean or collision-free the underlying representation is (proven via
sanity check 100%, collision probe 0/256, then a per-bit breakdown showing the 4 parity-type sum
bits stuck at ~50% chance while the one bit closer to a threshold function — the carry — hit
66-87%). This is the classic Minsky-Papert linear-separability limit, not a capacity or
representation problem. Full diagnostic chain in `D:\flybrain\flybrain_binary_addition*.py` and
Flybrain's own HANDOFF.md.

**Jonathan's own catch, not mine — I only found the mechanism after he insisted the first failure
"felt wrong" and refused to accept "the task is just hard."** He then explicitly asked whether the
same limitation could apply to SovereignCore. Answer, with appropriate hedging: it's a real,
well-grounded HYPOTHESIS, not yet directly tested on SovereignCore — but the structural match is
close enough to flag here before it gets lost:

- `_read_response()` reads the organism's answer as a WEIGHTED VOTE across firing bricks —
  `num += w * val; den += w` — a weighted LINEAR AVERAGE, structurally the same shape as
  Flybrain's trained linear readout.
- Each individual brick's own prediction, `predict_next()`, is `mem + velocity + noise` — also
  just a linear combination of two state variables, not capable of representing an XOR-type
  relationship on its own.
- The night's numeric-task result (6/6 memorized, only 1/4 generalized) is consistent with this:
  memorizing six specific examples never requires linear separability (you can always carve out
  six separate attractors), but extracting a REUSABLE "+2 regardless of input" RULE that holds
  across every possible input is a much stronger requirement — closer to what a linear-readout
  ceiling would actually block.

**What would confirm or kill this hypothesis, if picked back up:** redo the per-bit-style
breakdown directly on SovereignCore's bit-level task — check whether SOME output bits/positions
(the ones closer to a simple threshold/magnitude relationship) generalize meaningfully better
than others (the ones closer to a parity/XOR relationship across two or more input bits), the
same asymmetry that confirmed the diagnosis on Flybrain. If that asymmetry shows up here too,
the fix is the same in kind as the one being explored on Flybrain: the problem isn't the readout
wiring, it's that nothing upstream is doing real combinatorial (not just redundant) EXPANSION of
the input into a space where the relevant relationships become linearly separable before the vote
ever happens.

## ✅ HYPOTHESIS TESTED, 2026-10-18 (`lucy_bitlevel_combinatorial_readout.py`) -- PARTIAL CONFIRMATION, plus a separate real finding

The hypothesis above was directly tested, not left open. First attempt
(`lucy_numeric_task_combinatorial_readout.py`) was INCONCLUSIVE for two reasons: only 6 training
examples, and (Jonathan's own catch) the "+2 rule" numeric task is LINEAR, never a fair test of
an XOR-shaped fix in the first place. Corrected version used the real bit-level lookup task
instead (genuinely parity/lookup-shaped), with a proper 700-train/150-held-out split the original
bit-level test never had. Real result, two findings:

1. **Separate, independent finding**: SovereignCore's own native `_read_response()` vote scored
   BELOW CHANCE this run (train 43.8%, held-out 45.3%, chance=50%), while a plain, properly
   cross-validated LINEAR readout fit on the exact same real internal brick-firing states reached
   59.5%/58.0% -- the hand-tuned vote formula isn't even extracting the linear signal already
   present in its own computed state. Worth its own look sometime, independent of the XOR
   question.
2. **The actual question**: combinatorial-conjunction expansion (300 KC-style units sampling the
   raw 16-bit context, K=4) reached train 91.0%, held-out 62.0% -- a further real gain over the
   no-expansion linear readout's 58.0%, same DIRECTION as Flybrain's result. But the large
   train/held-out gap (91% vs 62%) shows a real overfitting component -- this is NOT as clean a
   replication as Flybrain's ridge-confirmed 3.8%->13-15% jump. **Verdict: the fix transplants
   PARTIALLY -- real, same-direction, modest (58%->62%), not a clean win.**

Full numbers and methodology in `[[combinatorial_expansion_missing_ingredient]]` (persistent
memory) and `lucy_bitlevel_combinatorial_readout.py`'s own header comment.

## ⚠️ RECALIBRATION, 2026-10-19, later the same night: the "58-59%" ceiling had two real issues

A permutation-test control caught a real label-leakage bug: `probe_brick_firing_vector()` set
`current_target` to the REAL answer during harvesting, letting `_fire_relays()`'s error-driven
relay-splitting see the target live -- real targets scored a suspicious 100% held-out under this
leak. Fixed by harvesting fully blind (`current_target=None` throughout) -- real targets dropped
back to the original 58.0%, confirming the leak explained the 100% artifact. But the SAME
permutation control revealed completely random/shuffled labels score 54% under this exact
ridge+CV procedure, not 50% (small-sample ridge artifact, not another bug). **Honest reading: the
real signal is ~58% vs. a 54% null floor, roughly 4 points of genuine structure -- smaller than
the "58% vs 50% chance" framing used throughout tonight implied.** Doesn't invalidate the
combinatorial-expansion/dendritic-branch work -- direction was right -- but the true effect size
was smaller than reported. Scripts: `lucy_bitlevel_permutation_test.py` (caught the bug),
`lucy_bitlevel_blind_permutation_test.py` (the number to trust).

## ✅ FINDING #1 RESOLVED, 2026-10-19 -- eight tests, real answer found on the eighth

Dug into finding #1 (native readout ~44% vs. post-hoc regression ~58-59%) across eight real
tests. Six were clean, well-reasoned, and refuted in sequence: recognition-mode winner-take-all
vs. weighted-vote, repetition rate (11 vs 160 reps/pattern), hand-picked vs. online-learned
convex vote weights, convex vs. unconstrained linear combination, frozen vs. churning population,
single-example vs. mini-batch gradient updates, single-cycle vs. sustained-cycle scoring, and an
RNG-state-leak bug (real, found and fixed, but not the cause). None of those closed the gap.

**The real answer, found on test eight by re-reading the engine's own code rather than building
a ninth variant blind**: `_read_response()` is called from THREE places, not the one I knew
about -- `_evaluate_fitness()` (sovereign_core.py line 1376) calls it EVERY CYCLE as the
organism's PRIMARY FITNESS SIGNAL (`whole_correct`, which drives chain-credit, prototype
learning, and split-credit). Every test that overrode `_read_response()` to try an alternative
combination rule (tests 3-6, 8) wasn't testing an alternative readout alongside normal training
-- it was REPLACING the organism's own training signal with an uncalibrated substitute for the
whole run, which is why TaskCorrect collapsed to ~0.000 for thousands of cycles in every one of
them regardless of which specific mechanism was substituted in. Tests 1-2 were unaffected because
they only toggled the real, already-integrated `RECOGNITION_MODE` flag inside the real
`_read_response()`, never replacing the function itself.

**Conclusion**: the original gap (native ~44% vs. post-hoc regression ~58-59%) is real. But it
cannot be closed by a live override, because `_read_response()` is load-bearing for the
organism's own fitness loop -- swapping it mid-run hijacks what the whole population is bred to
do. The 58-59% result was only ever achievable by leaving training completely untouched and
fitting an alternative readout strictly after the fact on a frozen snapshot (exactly what the
original external regression did). A fair test of a genuinely different LIVE readout would need
to be a proper, first-class engine option (integrated the way `RECOGNITION_MODE` already is),
with the whole population trained under it from scratch for a full run -- not a bolt-on override.
Not yet built; a real next step if this is picked back up, distinct from anything tried tonight.

## ✅ BUILT, 2026-10-19: READOUT_MODE="linear", the real first-class engine option

Built the fix the resolution above called for -- not a bolt-on override, a genuine new engine
option in `sovereign_core.py` itself, pushed to `drogongod/sovereign-core` (commit `953a9aa`).
`READOUT_MODE` global flag: `"vote"` (default, byte-for-byte unchanged original behavior) or
`"linear"` (new). The new mode adds `Brick.readout_weight`, a genuinely EVOLVABLE trait (small
random init, mutated in `_mutate_and_select()` the same way `fire_threshold`/
`inhibition_strength` already are, inherited correctly on both clone-creation paths in
`_run_sleep_dag()`) -- so under `"linear"`, `_read_response()` computes an unconstrained linear
combination (`sum(readout_weight * val)`, no normalization, negative weights allowed) using a
weight that evolves through the SAME natural-selection process as every other real trait in this
engine, never a separately-bolted-on learning rule. This is the one fair way to test whether an
unconstrained combination beats the hand-designed vote: let the whole population train under it
honestly, from cycle 1, the way `RECOGNITION_MODE`'s two real options always have.

Real A/B result (vote vs. linear, both trained from scratch, same split/seed/cycles),
`lucy_bitlevel_readout_mode_linear_test.py`:

| | train | held-out |
|---|---|---|
| vote (original) | 48.6% | 44.7% |
| linear (new, evolvable) | 54.4% | 46.7% |
| external post-hoc regression (reference) | -- | ~58-59% |

A genuine, modest, fairly-trained improvement over the original readout -- the first uncorrupted
confirmation that the hand-picked vote weights were part of the real ceiling, not just a
hypothesis. Doesn't close the whole gap to the post-hoc ceiling, which is expected: that ceiling
gets an unfair advantage (fit AFTER the population fully specialized, full-batch + regularized),
while the live evolutionary version has to learn brick behavior and readout weights together
under selection pressure alone.

## ✅ BUILT, 2026-10-19 (same night): DENDRITIC_BRANCHES_ENABLED -- a native fix for capability #1

Separately, per `[[vampire_mamba_four_organic_mechanisms]]` (Jonathan's own four-capability
target for this substrate, reverse-engineered black-box style from an original he lost, NOT
biomimicry): capability #1, local nonlinear sub-processing ("dendritic computation"), was
confirmed completely absent from `Brick` -- `predict_next()` is flat and linear, and the whole
night's readout investigation above is the SAME gap found from a different angle. Built a native
(non-biological) mechanism that produces the same CAPABILITY: each brick now has evolvable
"branches" (`n_branches`, `branch_seed`, `branch_thresholds`) that route incoming signal by
source and only pass it to the soma if the branch's OWN evolvable threshold is crossed that
cycle -- a real AND-type coincidence gate, reusing the exact same evolvable-trait pattern as
`fire_threshold`/`inhibition_strength`, not simulated ion channels. Flag-gated
(`DENDRITIC_BRANCHES_ENABLED`, default False, byte-for-byte unchanged when off). Smoke-tested
(300 cycles both ways, no crashes, branches genuinely differentiated per brick) -- NOT yet
capability-validated on the real bit-level task; that 8000-cycle run is the next real step.

## ✅ BUILT, 2026-10-19 (same night): DISASTER_EVENTS -- recovered mechanism, real provenance

Per `[[sovereigncore_original_competition_design]]`: checked `D:\THE_ARC\My classroom\evolution\`
(real historical files, found via Jonathan's own direction, not assumed) before building this
blind. Confirmed directly in `quinary_lego.py`: "COSMIC RADIATION -- 30% mutation every 500 gens"
-- a periodic, bounded mutation-rate spike to prevent premature stabilization/stagnation, exactly
matching Jonathan's own framing tonight ("random cosmic simulator disasters and fake mass
extinctions... to prevent stabilization and stagnation"). Built as `DISASTER_EVENTS_ENABLED`
(default False): every `DISASTER_INTERVAL` cycles (500, matching the real precedent), mutation
rate multiplies by `DISASTER_MUTATION_MULTIPLIER` (6.0, matching the real precedent's ratio) for
`DISASTER_DURATION` cycles, then reverts -- implemented via `_effective_zone_cfg()`, a scaled copy
of the real `ZONE_PARAMS` dict, zero cost outside a disaster window. A SEPARATE,
independently-gated `DISASTER_EXTINCTION_FRACTION` (default 0.0) adds extra random culling during
a disaster window -- this piece is from tonight's VERBAL description only ("mass extinctions"),
not yet confirmed in any recovered file, so it's honestly flagged as unverified and off by
default even when disasters are otherwise enabled. Smoke-tested (250 cycles, 2 disaster windows
fired exactly on schedule, no crashes) -- not yet capability-tested on a real task.

**Honest caveat, Jonathan's own words**: the recovered files in `D:\THE_ARC\My classroom\evolution\`
may themselves be adapted drafts, "possibly even adapted for one of the previous generations that
didn't work out" -- not verified ground truth for the actual lost breakthrough. Treat this
mechanism as a well-corroborated REBUILD inspired by real fragments, not a guaranteed
reconstruction of the original.

**CORRECTED FRAMING, same night, important**: this engineer's own write-up above wrongly framed
disaster events as a permanent production stagnation-prevention feature. Jonathan corrected this
directly: "these disaster events were not supposed to be for the real final model, they were just
the engines to stop stagnation and speed up evolution to create the design for the final model."
This is a DISCOVERY-PHASE search tool (same category as `unstable_pond`/`crocodile_mushroom_plant`
-- see next section), meant to run temporarily while searching for good structure, then be
switched off once that structure is found and hardened. Default `False` already matches correct
usage; only enable for a deliberate, bounded discovery run, never as a standing production
setting. Corrected directly in the engine's own comment, not just here.

## 📂 Real historical result archives found, 2026-10-19: `unstable_pond` and `crocodile_mushroom_plant`

`D:\THE_ARC\unstable_pond_results\unstable_checkpoint.pkl` and
`D:\THE_ARC\crocodile_mushroom_plant_results\cmp_checkpoint.pkl` -- real saved population-state
checkpoints from the actual 6-month structure-discovery phase Jonathan described ("this is how we
worked out the wiring, this is why it took six months"). Both are plain dicts:
`{generation, memory, thinking, relay, stem, history, cross_breed_count}` -- four cell-type pools
(memory/thinking/relay/stem) of dicts (`network_id, niche, is_stem_born, bricks, fitness, age`),
confirming the memory/thinking/relay/stem vocabulary used tonight was real and load-bearing, not
just descriptive language.

**`unstable_pond`**: reached generation 5000, 429 cross-breed events. Its `history` confirms the
REAL "Four Seasons" mechanism, precisely parametrized -- per-generation `season` (SPRING/SUMMER/
...) with a persistent `multiplier` (e.g. SPRING=1.5, SUMMER=1.0) -- a CONTINUOUS cycling rhythm
the population always lived inside, not a sparse periodic spike. This is a more faithful, better-
corroborated version of the mutation-modulation idea than the sparse spike-and-revert
`DISASTER_EVENTS_ENABLED` implements -- real seasonal cycling is the natural upgrade if this is
picked up again, now that it's confirmed correctly scoped as a discovery-phase-only tool. The
"best" value (likely error/loss, given it falls) declined steadily across all three pools over
the full run (memory 3.04->2.41, thinking 3.54->2.65, relay 3.23->2.55) -- a real, coherent
improvement trend.

**`crocodile_mushroom_plant`**: only reached generation 71 (much shorter), 6 cross-breed events.
Its "best" values were flat or rising (memory 1.61->1.74, relay 2.27->2.51) -- the opposite
direction from `unstable_pond`. Not yet established whether "best" means the same thing in both
files, so neither run should be assumed to be "the working one" without more investigation --
recorded honestly as an open question, not resolved tonight.

Both results are consistent with Jonathan's own framing: these are real artifacts of the
structure-SEARCH phase, not necessarily the final breakthrough itself.

**Desktop handoff for cross-model review**: `C:\Users\Azazel\Desktop\handoff\sovereigncore_readout_finding_20261019.md`
written for a second opinion (ChatGPT/other models), covering the full eight-test arc and this
fix, per the project's standing cross-model-review practice.

**Date:** 2026-10-16, updated same day with a real positive finding, then updated again same
day with a real ENGINE BUG found and fixed in `sovereign_core.py` itself (not test-script code).
**Status:** Phase 1 actively tested, real results in hand (one confirmed positive, four
confirmed negative), PLUS a real bug found and fixed in the core engine — see "✅ REAL ENGINE
BUG FOUND AND FIXED" and "✅ REAL RESULTS" sections below before anything else. This file exists
so the plan, the open question, AND the real findings don't get lost — this has been lost and
rediscovered 4 times before; the explicit goal now is for this to be the last time.

## ✅ REAL ENGINE BUG FOUND AND FIXED (2026-10-16, "1 last trick")

**This is a bug in `sovereign_core.py` itself — the real, proven engine — not in any test
script.** It explains the oscillating/lockstep sleep-every-~500-cycles pattern seen across every
test tonight (numeric, char-level, bit-level alike), and it was NOT what I originally guessed.

**Wrong hypothesis, tried first, proven wrong, recorded here so it doesn't get re-tried blind**:
I first suspected my OWN `exact_match_accuracy()` evaluation methods were the cause — they call
`inject_problem()` once per task pair to probe the substrate, and `inject_problem()`
unconditionally does `self.context_tokens += 1` on every call, including probe calls. I fixed
all four test scripts (`lucy_favorite_color_core*.py`, `lucy_original_numeric_task.py`,
`lucy_favorite_color_core_bitlevel.py`) to snapshot/restore `context_tokens` around evaluation.
**This was then directly tested and found NOT to be the explanation**: (a) fixed and unfixed
bit-level runs produced bit-for-bit identical trajectories; (b) a control run with ZERO
evaluation calls at all (pure training) still showed sleep firing on the same ~500-600 cycle
cadence. The snapshot/restore fix is still correct practice (a measurement function should be
read-only) but it was not the real cause — recorded honestly, not quietly dropped.

**The real cause, found by directly instrumenting `context_tokens` before/after every single
`core.run_cycle()` call** (zero evaluation calls in that trace, eliminating test-script code as
a suspect entirely): `context_tokens` jumped from 499 to 1350 — delta +851 — within ONE cycle,
at exactly cycle 500. Traced to `sovereign_core.py`'s own built-in diagnostic, inside
`run_cycle()` itself:

```python
if self.current_time % 500 == 0:
    # 🔍 SHOW ACTUAL ANSWERS: probe each task pair, print call -> answer -> correct
    samples = []
    for (call, correct) in self.TASK_PAIRS:
        self.inject_problem("probe", 1.0, forced_call=call)
        self._update_bricks(); self._fire_relays()
        ans = self._read_response()
        ...
    print("    🔍 " + " | ".join(samples))
```

Every 500 cycles, this debug probe loops over **every** `TASK_PAIR` calling `inject_problem()`
for each one — and never restores `context_tokens` afterward. For an 850-pair task that's +851
in one shot (delta = `len(TASK_PAIRS) + 1`, confirmed exactly). This silently forces an
unintended sleep-consolidation event every exactly 500 cycles, **completely independent of
task, test script, or evaluation code** — it's baked into the engine itself. This is the real
reason the oscillation was, in Jonathan's own words, "not random in its randomness."

**Fix applied**: snapshot `context_tokens` before the probe loop, restore it after:
```python
saved_context_tokens = self.context_tokens
samples = []
for (call, correct) in self.TASK_PAIRS:
    ...
print("    🔍 " + " | ".join(samples))
self.context_tokens = saved_context_tokens
```

**Applied to:**
- `D:\flybrain\sovereign_core_publish\sovereign_core.py` — the real, actively-maintained engine
  source, edited directly (consistent with its own git-history pattern of direct edits).
- `F:\my-agent-vampire-lucy-SovereignCore\sovereign_core.py` — synced copy of the above.
- `F:\my-agent-vampire-lucy-SovereignCore\sovereign_core_v4_21.py` — the v4.21b "resurrection"
  lineage working copy, same bug, same fix, applied separately (its own `current_time % 500`
  block). **Deliberately NOT applied to `D:\flybrain\Max_sovereign_core_v4_21.py`** — that file
  is the preserved historical original and is left untouched on purpose, per the project's
  standing file-migration discipline (pristine lineage files don't get edited).

**Verification — CONFIRMED, not just theorized**: reran a zero-evaluation trace against the
fixed engine. `context_tokens` climbed cleanly 100 → 200 → 300 → ... → 800, exactly +1 per
cycle, through and past cycle 500 with no jump at all (the old buggy engine jumped +851 exactly
at cycle 500 every time). Sleep then fired naturally between cycle 800-900 — consistent with the
REAL, intended `CONTEXT_THRESHOLD=0.85 × CONTEXT_CAPACITY=1000 = 850` trigger point, not the
artificial every-500-cycles cadence the bug had been forcing. The fix is real and verified, not
just applied-and-hoped.

**⚠️ CORRECTION (see "ROUND 2" section immediately below): the claim that follows — "that
comparison likely still holds, since the same bug affected every config equally" — turned out to
be WRONG, and was itself corrected the same night.** The disturbance from this bug (and a second,
related one found afterward) scales with `len(TASK_PAIRS)` — 6 for the numeric task, 850-905 for
every language/bit task — so it was never an equal, controlled confound across configs. Read the
ROUND 2 section before trusting any absolute number in this file.

Why this matters for every result already in this file**: the numeric-task positive result,
the four char-level null results, and the bit-level inconclusive result were ALL measured
against the buggy engine (forced sleep every ~500 cycles instead of the real ~850-cycle natural
cadence). The numeric-task and char-level results are directional findings about which TASK
DOMAIN engages the substrate. But absolute numbers (cycle-to-result timing, exact accuracy
percentages) were all taken under a confound that is now removed. **The bit-level re-encoding
result, RERUN against the genuinely fixed engine, 2026-10-16/17 — now a closed, negative
finding, not an open question (later superseded again — see ROUND 2)**: first attempt at
verification actually used a STALE process (started 53 minutes before the engine fix was written
to disk; Python doesn't hot-reload already-imported modules, so it silently ran the old buggy
engine despite the "fixed" filename — caught by checking process start-time vs. file-mtime,
killed, relaunched for real). The genuine rerun (8000 cycles, fixed engine, confirmed via py-spy
and file-mtime checks) showed the fix IS real and working at the engine level — only **9 sleep
events** fired over 8000 cycles, vs. the 16 the bug would have forced (lockstep every exactly 500
cycles) — a real, substantial, verified change in engine behavior. But the task's own accuracy
trajectory: 54.1→59.8→61.9→54.9→53.9→44.7→56.0→52.4→56.4→49.3→55.8→55.3→48.1→54.6→56.7→52.0%, mean
54.1%, range 44.7-61.9%. An early rise to 61.9% looked promising mid-run but reversed back into
the same oscillation band — not a sustained trend. Essentially the same noisy chance-level
behavior as
before the fix (old buggy mean 52.0%, range 41.1-56.6%) — a few points higher on average, within
ordinary run-to-run noise, not a meaningful difference. **This "verdict" was itself only half
right — see ROUND 2 immediately below.**

## ⚠️ ROUND 2, 2026-10-17: the fix above was real but INCOMPLETE — a second instance of the same
## bug, caught by Jonathan's own instinct + an independent model's cold code review, not by me

**What happened**: Jonathan's own note the next session — "internal diagnostics it would doubled
with wolf pack" — and, independently, another model given only this HANDOFF.md (no session
access) read the diagnostic code above and flagged: `_update_bricks()` and `_fire_relays()`
"aren't necessarily passive operations... Restoring one counter doesn't undo those changes." I
verified this directly against the real code (never just trusting another model's claim —
[[feedback_authority_not_competence]]) and it was correct:

- `_update_bricks()` commits accumulators, updates prediction error, ages every brick, and can
  grant **IMMUNE+TEACH promotion** (a brick becomes a permanent protected teacher) — as a side
  effect of the diagnostic probe running, not real training.
- `_fire_relays()` increments real relay usage/split counters AND physically delivers signal to
  OTHER bricks via `.receive()` (sister cells, downstream targets) — which queues and affects
  their firing on the next REAL training cycle.

**Direct evidence, already sitting in my own logs**: the `splits` counter grows ~8,000-8,300 per
100 training cycles everywhere in a run — except exactly at the %500 diagnostic, where it jumped
140,000-210,000 (an 18-25x spike) on the 850-pair bit-level task. My Round 1 fix only stopped the
diagnostic from forcing premature sleep. It did nothing about the diagnostic physically running
850 real training-equivalent steps every 500 cycles — and because this scales with
`len(TASK_PAIRS)`, the numeric task (6 pairs) and the language/bit tasks (850-905 pairs) were
NEVER an equal, controlled confound, contradicting what Round 1 of this file claimed.

**The real, complete fix, this time** (applied to `D:\flybrain\sovereign_core_publish\
sovereign_core.py`, the `F:\` synced copy, and `sovereign_core_v4_21.py`): added module-level
`DIAGNOSTIC_PROBE_ENABLED = False`, guarding the ENTIRE mutating block (not just the
context_tokens side effect) — `if self.current_time % 500 == 0 and DIAGNOSTIC_PROBE_ENABLED:`.
Disabled by default for every controlled experiment.

**But a SECOND instance of the identical bug was still live** — in my own test harnesses. Every
one of `exact_match_accuracy()` in `lucy_favorite_color_core.py` (covers v2/v3), `..._v4_21.py`,
`..._bitlevel.py`, and `lucy_original_numeric_task.py` called `self._update_bricks();
self._fire_relays()` once per probed pair, on `self` — same disease. Confirmed directly: even
with the engine's own diagnostic fully disabled, the `splits` counter still spiked 9.5x
(39,961→117,204 across cycles 500-600) purely from these scripts' own evaluation calls. **Real
fix**: rewrote all four to run the probe on a throwaway `copy.deepcopy(self)` instead of `self`
— zero effect on the real run by construction — and save/restore Python's global `random` state
around the probe too, so evaluation doesn't even change which pseudo-random draws come next.
Smoke-tested: `splits` now grows at the normal ~8,000/100-cycle rate straight through every eval
checkpoint, no spike, anywhere.

**Reran the critical experiments under the actually-complete fix:**
- **Numeric task, 8000 cycles, two independent clean reruns**: internal TaskCorrect held
  0.67-0.89 throughout (same strong band as every prior run — and IMMUNE+TEACH fires repeatedly
  *before cycle 100*, proving it was never an artifact of either bug, since neither bug could
  touch anything that early). Exact-match: oscillated 0-50%, **peak 50.0% (3/6) on both clean
  reruns** — this CORRECTS the earlier claimed peak of 66.7% (4/6), which was real but inflated
  by the bug. Generalization: still 1/4 = 25.0%, same attractor-clustering pattern, reproduced
  closely across three separate runs now. **The core qualitative finding survives fully intact**
  — only the specific "66.7%" number was wrong; the honest number is 50%.
- **Bit-level task, COMPLETE, 8000 cycles, fully clean**: 55.6→54.7→54.2→50.9→53.9→52.7→52.0→
  52.2→54.1→50.1→50.4→49.5→51.5→54.6→52.1→50.9%, mean **52.46%**, range **49.5-55.6%** — a
  noticeably TIGHTER band around chance (50%) than either prior version (round-1-fix mean 54.1%/
  range 44.7-61.9%; original buggy mean 52.0%/range 41.1-56.6%). 9 sleep events over 8000 cycles,
  same real cadence as round 1 (round 2 didn't change sleep timing, only removed the extra
  per-eval disturbance). **This is now the cleanest measurement of this task to date, and it
  reads as the most clearly chance-level result of the three** — the fully-isolated measurement
  shows LESS variance/excursion from 50% than either confounded version did, consistent with
  there being no real signal here at all, just noise that the bugs were adding variance to.
  **Final verdict, now closed with high confidence**: the bit-level re-encoding hypothesis does
  not work on this substrate at this scale/config.

**Honest meta-lesson**: I declared Round 1 "fixed" and pushed it to GitHub before checking
whether the diagnostic's OTHER function calls (not just the one counter that explained the
symptom I was chasing) also had side effects. [[feedback_bug_class_sweep]] already said a bug
with a general shape needs a whole-codebase grep, not a one-off fix — I applied that to the
engine file and missed that my own four test scripts were four more instances of the exact same
class. The catch came from Jonathan's instinct plus an independent model's cold read of the code,
not from me re-auditing my own "done" work unprompted. Recorded in
`GALATEA_ENGINEER_DIARY_20261017_SOVEREIGNCORE_DIAGNOSTIC_PROBE_BUG.txt` and here, including the
part where Round 1 was only half-right, per the standing instruction to never quietly smooth over
a correction.

## ✅ REAL RESULTS, read this section second

**The task domain is the real variable, not a lost "secret ingredient."** Jonathan's own
historical diary (`D:\Galatea Diary\GALATEA_ENGINEER_DIARY_20261001_WOLFPACK_DECAY_SISTERMATCH.
txt`) confirms his own 2026-10-01 char-level test already landed at the same "noisy and low
(0-20%)" range tonight's char-level tests did — he did nothing wrong originally, and nothing
was lost from the char-level-task side specifically.

**But the substrate's OWN original, built-in task — 6 fixed `(a,b,c)->d` arithmetic triples, all
the same "+2, continue the sequence" rule (`sovereign_core.py:779-786`, never modified) — behaves
completely differently from every character-level task tried:**

| Task | Config | Cycles | Internal TaskCorrect | Exact-match |
|---|---|---|---|---|
| Favorite-color, context_len=3 (v1/v2) | proven baseline | 8000 | ~0.2-0.3 | 1.4% |
| Favorite-color, context_len=10 (v3) | proven baseline | 8000 | ~0.2-0.3 | 3.9% |
| Favorite-color, context_len=10, v4.21b lineage | proven baseline | 8000 | ~0.2-0.3 | 3.2% |
| **Original numeric task** (`lucy_original_numeric_task.py`) | proven baseline | 8000 | **0.74-0.89** | **peaked 66.7%** |

Real mechanism confirmed firing on the numeric task that never once fired on any char-level
task: **"IMMUNE+TEACH (stable teacher, then plastic)"** — bricks that prove reliably high-
performing get promoted to a protected teacher role, paradigms the rest of the colony learns
from. Jonathan independently recalled this mechanism's real history ("session [bricks] were
promoted to teachers because they were discovered to be a stabilizer... paradigms of the
system") before being shown the log confirming it. Ties directly to the real, already-tested
`PROBATION_CYCLES` mechanism (425=harm, 850=good, 1700=no better, exact numbers already in the
code's own comments) and the sabertooth-tiger/Komodo-dragon "evolution is blind and stupid,
needs an artificial governor" design philosophy, also confirmed live against the real
`DECAY_ENABLED` mechanism.

**Honest limitation**: generalization to held-out triples following the same rule, never seen
in training, was only 1/4 (25%) — the substrate's outputs cluster around a few memorized
attractor values rather than cleanly extracting the underlying rule yet. Real, substantial
progress over the character-level results; not a finished, fully-generalizing solution.

**Immediate next step, Jonathan's own hypothesis, not yet tested**: re-encode the favorite-color
task at the BIT level instead of the character level, to see whether the numeric-task success
transfers to bit-level language representation the way it clearly doesn't to character-level
representation. All four char-level configs and the one numeric-task config are real, reusable
code in this directory (`lucy_favorite_color_core*.py`, `lucy_original_numeric_task.py`).

## Plan, stated by Jonathan directly

"Let's first make our vampire out of [SovereignCore and Flybrain] — then let's see if we can
give them mamba likeability." Two-phase plan:
1. Build a version of Lucy (the vampire project, currently real-Mamba-3-based in
   `F:\WampYr_Mamba-3` and `F:\my-agent-vampire-lucy`) using **SovereignCore** as the substrate
   instead of Mamba — port the identity/training loop onto SovereignCore's own real mechanism,
   not a gradient approximation of it.
2. Afterward, investigate whether SovereignCore can be given Mamba's *capability* (not
   necessarily its mechanism) for an ever-growing, folding context window.

## What SovereignCore actually is (verified against real source, not assumed)

Real code: `D:\flybrain\sovereign_core_publish\sovereign_core.py`. A completely non-gradient,
discrete, evolutionary system — NOT a neural network trained by backprop at all:
- `Brick`: integer states 0-31, `prototype`/`proto_answer`, spiking `fired_this_cycle`.
- `PairedRelay`: forward-only signal propagation between bricks (`_fire_relays()`); on
  `prediction_error > split_threshold`, excess signal redirected to a content-matched "sister"
  brick (never the source), with a real, measured `back_delay` (`random.randint(2, 6)`,
  evolvable) — the sister's correction is temporally offset, not instantaneous.
- `_evaluate_fitness()`: whole-organism correctness drives evolutionary selection of relay
  traits (threshold/ratio/delay) across generations.
- Confirmed zero backpropagation anywhere in this mechanism, verified by direct code reading
  (see [[wampyr_mamba3_public_release]] memory, "did you check the code?" correction).

## The open question (Jonathan's own framing, verbatim)

"Would they need to be mamba to have the equivalent of a folding attention scale like Selective
State Space Models (SSMs) — by that I mean an ever-growing context window that folds in. I'm
looking for the capacities not necessarily the mechanics that achieve those capacities."

**Working answer, not yet tested empirically**: no, not necessarily. The CAPABILITY (compress
unbounded history into a bounded, continuously-updated, retrievable state) is a general property
of any persistent, incrementally-updated memory system — it is not SSM-exclusive. SSMs are one
particularly elegant, gradient-friendly, parallelizable way to achieve it; SovereignCore's
discrete relay/brick state is a structurally different way to maintain persistent state that
*could* in principle fold context too. Whether SovereignCore's specific mechanism actually
achieves competitive long-range retention is an open EMPIRICAL question, not something
guaranteed by the analogy — this is exactly the same shape of question the WampYr_Mamba-3
local-learning investigation just spent a full session answering for TBPTT (see below).

## Jonathan's hybrid idea, stated directly, worth testing before assuming "no way"

"My gut says no way but my brain says a hybrid design might be achievable with the solid state
being stored into a substrate to a free layer that a Mamba that load and save the hidden states
into the non-mamba substrate and then can recall it from there."

I.e.: don't make SovereignCore itself an SSM. Instead, use a small, separate, proven Mamba module
whose ONLY job is context-folding, and have IT write its resulting hidden state into
SovereignCore (as external memory) and read it back out when needed — SovereignCore stays a pure
discrete/evolutionary system; Mamba becomes a context-compression front end it can query. **This
is structurally the same idea as this project's own existing, not-yet-built "Memory Cloves"
concept** (see `[[galatea_memory_cloves_mamba]]`: "filing-cabinet store for forgetting;
salience+frequency decay") — worth reading that memory before designing this from scratch, since
Jonathan independently re-derived a version of an idea already on record.

## Directly relevant context from the same night

The WampYr_Mamba-3 local-learning investigation (same session) is the single most relevant prior
result: it empirically confirmed that "folding context" is a real, measurable, credit-horizon-
bounded capability even for a real Mamba-3 SSM — truncated/restricted credit assignment failed
at chance level until the effective window was sized (and *correctly anchored*) to the real
evidence-to-query distance. See `C:\Users\Azazel\Desktop\handoff\local_learning_mamba3_handoff.md`
and `[[wampyr_mamba3_public_release]]` for the full real numbers. Any attempt to test
SovereignCore's own folding capability should borrow that exact experimental discipline
(measure the real evidence-to-answer distance in the task; don't assume a window/relay-delay
size is "enough" without a real held-out sweep; watch for boundary-alignment-style confounds in
whatever "window" or "delay" analog SovereignCore's relay mechanism has).

## ✅ ADVERSARIAL REVIEW ROUND, 2026-10-17 — 5 independent outside models + 1 decisive diagnostic

Per Jonathan's direct instruction before sleep, opened the full HANDOFF to 5 independent models
(ChatGPT, DeepSeek, Qwen, Gemini 3.8, GLM-5.2) for genuinely adversarial review, specifically
because subagents of the same model (me) don't give a dynamically different view. Full
transcripts live in each site's own chat history; summary here.

**Striking convergence, independently, across all 5**: the numeric task's "learning" is
memorization of a 6-entry lookup table via attractor dynamics, not rule extraction (consistent
with the measured 25% generalization). The bit-level recall task's flat-chance result is most
likely an architectural ceiling, not a data/tuning problem — the substrate has no protected,
write-gated/read-gated memory primitive, so a fact set early gets overwritten by ordinary signal
before the query arrives. ALL FIVE independently flagged `IMMUNE_TEACH`'s permanent-feeling
promotion (protecting bricks that score well on the 6-pair *training* set) as actively
crystallizing memorized attractors and suppressing the exploration generalization would need.
Gemini additionally quantified WHY whole-organism fitness can't help at 850 pairs: one mutation
improving a single pair shifts organism fitness by only ≈0.11% (vs ≈16.7% at 6 pairs) — almost
certainly below the substrate's own intrinsic run-to-run noise floor, so evolutionary selection
has no usable gradient to climb at that scale, independent of any representational question.

**Code-verified correction to the consensus** (checked directly, not taken on faith — per
[[feedback_authority_not_competence]]): bricks DO have persistent `mem`/`think` integer state
that survives across cycles unprompted (NOT "fire and reset to zero" as 3 of 5 models assumed) —
but `receive()` unconditionally adds to `mem_acc`/`think_acc` on every call from any source, so
there is no *protected* latch; a fact set early is still overwritten by whatever arrives in later
cycles before the query. The models' literal claim was slightly wrong; their functional
conclusion (no real working memory for this task) holds and is in fact more directly
demonstrable from the code this way.

**Two real experiments run overnight, both results recorded honestly, including the one that
didn't confirm the hypothesis:**

1. **IMMUNE+TEACH ablation A/B, numeric task, 8000 cycles, identical seed, only
   `IMMUNE_TEACH_ENABLED` changed** (new module-level toggle, default `True` = all historical
   results in this file; `sovereign_core.py`, `sovereign_core_v4_21.py`, + a `--disable-immune-
   teach` CLI flag added to `lucy_original_numeric_task.py`):
   - WITH IMMUNE+TEACH (baseline): exact-match mean 33.3%, peak 50.0% (3/6). Generalization 1/4.
   - WITHOUT IMMUNE+TEACH: exact-match mean **38.5%**, peak **66.7% (4/6)** — a real, measurable
     improvement in training performance. **Generalization: still exactly 1/4 = 25.0%, same
     specific held-out example right, same 3 wrong, in both runs.**
   - **Honest verdict**: IMMUNE+TEACH does measurably limit exact-match performance on the
     training set (consistent with "crystallizes attractors, blocks exploration"), but it is
     NOT, by itself, what's preventing generalization — disabling it entirely changed nothing
     about held-out performance. The real generalization barrier is upstream of this mechanism.

2. **GLM's proposed collision-rate diagnostic, `sc_collision_probe.py`** — the single highest-
   value, lowest-cost next experiment any model proposed: before any architecture change, measure
   whether the bit-level task's 850 distinct contexts are even REPRESENTABLE given the current
   brick population, independent of training/evolution entirely. Method: fresh untrained
   population, each of the 850 real contexts given a short isolated warmup (8 cycles, no
   competing contexts) on its own deep-copy, then read the raw response. **Result, decisive**:
   - First pass (single cold forward pass, no warmup): 849/850 contexts produced NO response at
     all — a firing-threshold fact (SPEAK-ONLY-WHEN-SPOKEN-TO gate), not a capacity finding.
   - With warmup: all 850 contexts now produce a response, but **99.8% land within 0.75 of some
     OTHER context's response**, and all 850 contexts collapse onto only **6 distinct rounded
     output values** (substrate's nominal range is 32). **5 of those 6 buckets contain BOTH
     target=0 AND target=31 contexts mixed together** — the response value is essentially
     uncorrelated with the correct target for the overwhelming majority of inputs.
   - **This is a hard, now-quantitatively-confirmed information-theoretic ceiling**: with only
     ~6 distinguishable output basins available for 850 required distinctions, no amount of
     evolutionary selection pressure — regardless of fitness signal, immunity policy, or cycle
     count — can solve this task, because the information is already collapsed before selection
     ever gets a chance to act on it. This directly confirms the "representational bandwidth
     mismatch" / "no population coding" diagnosis independently proposed by GLM, Qwen, and
     (implicitly) DeepSeek and Gemini.

**What this means for next steps, not yet attempted** (deliberately not unilaterally rewritten
overnight — this is a real architecture decision, not a bug fix, and deserves review): the
convergent, now partially quantitatively-confirmed recommendation across all 5 models is
**population coding** — replace each brick's localist 5-bit saturating scalar with a sparse
distributed code across a larger population (e.g., 10-of-200 active), which the entire existing
machinery (threshold firing, relay routing, sister-split, evolutionary selection) could carry
over unchanged, just with a wider state encoding. This is the single change every model
identified as most likely to move the needle on representational capacity; GLM additionally
proposed a cheap ablation (bit-level TRANSFORM task vs RECALL task, same encoding) to cleanly
separate "capacity ceiling" from "missing retrieval operator" before committing to the larger
population-coding rewrite. Full transcripts available for whoever picks this up next.

## ✅ TWO NEW, CODE-VERIFIED ARCHITECTURAL BUGS, found by ChatGPT reading the actual source
## (pulled live from GitHub, not from paste), both independently confirmed against the code

Continued the ChatGPT thread, pasting the real functions it had asked for. Before I'd even
finished pasting (a browser-automation glitch truncated the message mid-paste), it had already
fetched the real, current `sovereign_core.py` from `github.com/drogongod/sovereign-core` (pushed
there earlier the same night) and found two concrete, locatable bugs — different from, and more
specific than, anything in the 5-model adversarial-review round. Both checked directly against
the code before being trusted:

**Bug A — `_fire_relays()` never checks `fired_this_cycle`.** `_update_bricks()` sets
`b.fired_this_cycle` based on whether `input_this_cycle >= fire_threshold` (the "SPEAK-ONLY-WHEN-
SPOKEN-TO" gate), and `_read_response()` correctly only lets bricks with `fired_this_cycle=True`
vote on the readout. But `_fire_relays()`'s own loop (`for b in self.bricks: if not b.alive or
b.relay_strength < 10: continue`) gates relay transmission ONLY on `alive`, `relay_strength>=10`,
and phase — `fired_this_cycle` is never referenced anywhere inside it (confirmed via
`grep -n "fired_this_cycle"`: only 4 hits total, none inside `_fire_relays`). **A relay can keep
transmitting signal every cycle regardless of whether its source brick actually fired in response
to the current input.** This likely produces a continually-active relay network dominated by
persistent internal state rather than input-discriminating dynamics — a real candidate
explanation for attractor clustering, independent of the IMMUNE+TEACH mechanism.

**Bug B — the per-element input encoding is provably order-independent.** `inject_problem()`'s
entry-brick stimulation is:
```python
b.mem_acc += float(call[-1])
b.think_acc += float(call[-2])
for elem in call:
    b.receive(float(elem), src_id=-1, delay=0)
```
and `receive()` only does additive accumulation (`mem_acc += mapped * 0.3 * ...`, etc.). Addition
is commutative, so the generic per-element loop is **provably blind to element order** — only the
explicit `call[-1]`/`call[-2]` lines (outside the loop) carry any positional information. For the
bit-level task's 16-element context, **14 of 16 positions get folded into one order-blind sum.**
The separate prototype-matching recognition path (`dist = sqrt(sum((a-p)**2 for a,p in
zip(call_vec, b.prototype)))`) DOES preserve position via index-wise comparison — but that's a
stored-pattern lookup, not evidence the relay network itself learns sequence order.

**This gives a mechanistic explanation for the collision-rate finding above, not just an
empirical one**: two different 16-bit contexts sharing the same multiset of values across their
first 14 positions get genuinely IDENTICAL raw accumulator injection from the generic loop,
regardless of actual bit order — directly explaining why 850 distinct contexts collapsed onto
only 6 output buckets. The "representational bandwidth mismatch" the 5-model review converged on
isn't just abstract undercapacity; it's this specific, locatable code path.

**Not yet fixed** — both are real findings worth testing as targeted, surgical experiments
(e.g., gate `_fire_relays` on `fired_this_cycle`; make the per-element loop position-aware,
perhaps by routing each position to a distinct accumulator channel or scaling by position) before
committing to the larger population-coding rewrite the earlier review proposed. Smaller, more
targeted, and more directly tied to a concrete root cause than a full representation overhaul.

## ✅ SIX MORE code-verified bugs, same ChatGPT thread, same session — this is now the most
## consequential finding of the whole night and includes a correction to my own earlier claim

Pasted the remaining requested functions (`_update_bricks`, `_fire_relays`, `Brick.receive`,
`commit_accumulators`, `_evaluate_fitness`, the `recent_task_score`/IMMUNE+TEACH machinery).
ChatGPT found six MORE concrete bugs, two of which I verified directly and which **correct
things I had written as fact earlier tonight**:

1. **`back_delay`/`base_delay` have ZERO actual effect — CORRECTS a claim already recorded in
   persistent memory as confirmed.** `Brick.receive(self, signal, src_id, delay)` never
   references its own `delay` or `src_id` parameters anywhere in its body (verified directly —
   read the full function). Every signal is applied synchronously, same-cycle, regardless of what
   `delay` value is passed. The entire evolved `back_delay`/`base_delay` relay-trait system —
   mutated, inherited, cloned during growth — has no real effect on signal timing at all. I had
   written into `[[lucy_sovereigncore_flybrain_substrates]]` that this delay was "a real, measured
   ... temporally offset, not instantaneous" mechanism — that was wrong, and has now been
   corrected in that memory file with this same evidence.

2. **IMMUNE+TEACH immunity is genuinely permanent — CORRECTS my own claim from earlier THIS
   SESSION.** I previously wrote (both to the user and in HANDOFF.md) that "there's already a
   revocation path (`cull_immune=False` if `recent_task_score<0.40` for 60+ consecutive cycles)."
   That's wrong: the decrement is `b.consolidation_streak = max(0, ... - 1)`, which is CLAMPED at
   a floor of 0 — it can mathematically never reach `<= -60`. **The revocation condition is dead,
   unreachable code.** Once a brick earns `cull_immune=True`, nothing in the shown logic can ever
   remove it. My IMMUNE+TEACH ablation experiment (disabling promotion entirely) is still a valid
   test of the mechanism's overall effect, but my characterization of the *baseline* behavior —
   "not literally permanent" — was wrong, and I said so to Jonathan before actually re-checking
   the arithmetic. Corrected here, per the standing truth-rule practice of never quietly smoothing
   over an error.

3. **The internal `TaskCorrect` metric and external exact-match are NOT the same thing — this is
   probably the real explanation for "TaskCorrect 0.89 but exact-match only 50%."** `whole_correct
   = max(0, 1 - err/8)` is a GRADED closeness score, not a binary correctness check. For the
   numeric task (targets spread across a real range like 7-26), landing within 8 of the target
   still earns substantial partial credit even when NOT an exact match — e.g., predicting 11
   when the target is 8 scores 0.625. This directly explains the TaskCorrect/exact-match gap that
   had been sitting unexplained in every writeup tonight. For strictly binary targets (the
   bit-level task, rescaled to 0/31) this specific leniency mostly washes out since a wrong answer
   lands maximally far away (err≈31 ≫ 8 → credit≈0) — but for the numeric task's graded range it's
   real and substantial, and was never flagged until this review.

4. **Fitness credit may not track actual causal contribution.** `_evaluate_fitness()` scores
   EVERY living output brick via `predict_next()` (not necessarily what `_read_response()` used,
   which can prefer `proto_answer`), then propagates `chain_credit` backward through the STATIC
   synapse graph (`feeders_of`, built from `brick.synapses`) — but the actual signal that produced
   the real answer traveled through `_fire_relays()`'s dynamic relay/sister-split paths, which
   don't have to match that static graph. Relays can also get `split_helped` credit merely because
   `whole_correct` improved versus the PREVIOUS cycle's (different) task, not because their own
   split caused anything (`improved = whole_correct > prev`, compared across potentially unrelated
   trials). Not yet verified how large an effect this has — flagged, not yet confirmed decisive.

5. **The "frozen" teacher can still drift.** `_update_bricks()` sets `b.mem/think` from the stored
   `_teach_answer` at the START of a cycle, but `commit_accumulators()` can still change `b.mem`
   later the SAME cycle, and `b._teach_answer = b.mem` re-reads the (possibly already-drifted)
   value at the end. A "frozen" teacher isn't actually holding a fixed snapshot across its
   protection window — not yet verified how much this matters in practice.

6. **Possible held-out-generalization-check leakage, needs verification before trusting the 25%
   number.** `inject_problem()`'s `correct = dict(self.TASK_PAIRS).get(tuple(forced_call), 0)`
   OVERWRITES `self.current_target` from a TASK_PAIRS lookup — and held-out triples are
   deliberately NOT in TASK_PAIRS, so `self.current_target` silently becomes 0 (not the real
   held-out target like 9, 27, 14, 6) during every `generalization_check()` probe call.
   `lucy_original_numeric_task.py`'s own scoring compares against the correct value directly (the
   `target` loop variable from `held_out`, not `self.current_target`), so the REPORTED numbers
   are not mis-scored — but `_update_bricks()` internally calls
   `update_prediction_error(tgt if tgt is not None else b.mem)` using the WRONG, leaked `tgt=0`
   before `_fire_relays()`/`_read_response()` run, meaning the substrate's own internal dynamics
   during every held-out probe are being driven by a silently-wrong target. Whether this
   meaningfully distorts the measured 1/4 generalization result is NOT yet verified — flagged as
   the next thing to check before trusting that number further.

**Status**: six real findings, two already verified and corrected in the permanent record (delay
machinery is inert; immunity is genuinely permanent), four flagged for follow-up verification
before being trusted as fact. None of this has been acted on with code changes yet — this is a
diagnosis-only round. ChatGPT's own proposed next steps: a label-blind inference test, an
input-order collision test, a spike-gated-relay (fired_this_cycle-gated) ablation, a
correctness-vs-credit test, and a teacher-ablation test with reversible immunity — all designed to
run on cloned/deep-copied state so none of them touch the real run. Conversation ongoing in the
ChatGPT thread ("Diagnose Interference Bug") for whoever picks this up next; it has live access
to the real GitHub source and has been finding real, specific, locatable bugs faster than the
broader 5-model architectural review did.

## ✅✅ FIXES APPLIED AND TESTED, 2026-10-17 — real improvement on the numeric task, 2 of 8
## fixes reverted after direct testing showed they broke the network outright

Jonathan reviewed all 8 ChatGPT-found bugs directly and said: "apply fixes please and test it."
All 8 were implemented as real engine/test-script changes (not just ablation toggles) in
`sovereign_core.py` — new flags `BUG1_RELAY_REQUIRES_FIRING` through `BUG8_IMMUNITY_REVOCABLE`,
each with its own comment explaining the fix and what it replaces. **Discipline followed
throughout: implement, smoke-test, then bisect if something looks wrong — never trust a
"should work" without running it.**

**Two of the eight broke the network outright when tested, and were reverted (default=False)
after direct, isolated confirmation:**

- **BUG1 (gate relay transmission on `fired_this_cycle`)** — correct against the engine's own
  documented "SPEAK-ONLY-WHEN-SPOKEN-TO" design intent, but tested in isolation: TaskCorrect
  flatlined at exactly 0.500 (the `_evaluate_fitness` fallback for "no response"), exact-match
  dropped to 0/6, every held-out probe returned `None`. The already-evolved population apparently
  depends on relays propagating regardless of firing status just to maintain baseline signal flow
  — removing that without letting the population re-evolve under the new regime effectively
  silenced the network. ChatGPT itself predicted this exact risk before I tested it ("I would not
  blindly add a firing gate to the production engine... a controlled experiment is now a very high
  priority"). Reverted; flagged as a real experiment worth running properly (full re-evolution
  from scratch under the gated regime), not a safe default flip.

- **BUG6 (real signal-delay queue, making the evolved `back_delay`/`base_delay` traits actually
  delay delivery for the first time)** — the fix is architecturally correct (confirmed `receive()`
  really did ignore its own `delay` parameter) and worked exactly as designed, but isolated-tested
  alone: collapsed exact-match to 0/6 across an entire 8000-cycle run while TaskCorrect stayed
  superficially fine (0.76-0.85, since that's a graded closeness metric). Leading hypothesis:
  `_read_response()` only counts bricks that fired THIS exact cycle, and real multi-cycle delay
  pushes the informative signal to land on a different cycle than whichever one gets read.
  Reverted; the delay mechanism is probably worth implementing for real eventually, but needs the
  readout/evaluation logic redesigned around genuinely asynchronous arrival first, not a one-flag
  default change.

**The remaining six (BUG2, 3, 4, 5, 7, 8) were kept active and tested together, full 8000-cycle
numeric-task run, same seed as every prior comparison:**

| | Mean exact-match | Peak exact-match | Generalization (1/4 held-out) |
|---|---|---|---|
| Original buggy baseline | 33.3% | 50.0% (3/6) | 25.0% (1/4) |
| Round-2 fully-clean (this morning, before any of today's 8 fixes) | 33.3% | 50.0% (3/6) | 25.0% (1/4) |
| IMMUNE+TEACH-disabled ablation | 38.5% | 66.7% (4/6) | 25.0% (1/4) |
| **6 safe fixes (BUG2/3/4/5/7/8), today** | **54.2%** | **83.3% (5/6), reached twice** | **0.0% (0/4)** |

**This is the best exact-match result seen on this task all night, by a wide margin.** 494
immunity-revocation events fired over the run (BUG8 clearly doing real, active work — far more
evolutionary churn/exploration than the old, effectively-permanent-immunity baseline). Held-out
generalization, however, is now 0/4 — not an improvement, arguably a regression from the prior
25%, with responses landing close-but-not-exact on held-out triples (e.g. predicting 8.49 against
a true answer of 9, rounding to 8). **Honest read: this is a substantially better memorizer of
the 6 training examples, not evidence of newly-acquired rule extraction.** The six fixes
(positional encoding, stricter teacher-promotion reward, per-task improvement tracking, a
genuinely-frozen teacher, the held-out-leakage fix, and revocable immunity) together gave
evolution real traction on the training set specifically — exactly consistent with BUG8 and BUG3
targeting teacher-promotion quality, and BUG4 fixing credit misattribution, both of which bear
directly on how well the substrate FITS what it's shown, not on whether it extracts a reusable
operation from it.

**⚠️ CORRECTION, found via the bit-level rerun, same night**: the first "6 safe fixes" bit-level
run (mean 52.25%) showed 179 "IMMUNITY REVOKED" events against only 1 real IMMUNE+TEACH
promotion — an impossible ratio under the intended mechanism. Root cause: `cull_immune=True` is
granted by FOUR different code paths, not just IMMUNE+TEACH promotion — three others (freshly-
resurrected seedlings, probation-discounted clones, dead-capacity replacement clones) are the
ALREADY-PROVEN, separately-A/B-tested `PROBATION_CYCLES` mechanism (`sovereign_core_probation_
ab_result.md`: "425=harm, 850=good, 1700=no better... never shave it down"), with its own correct
expiry in `_expire_probation()` keyed on a real cycle deadline. BUG8's revocation logic was
applying to those bricks too, stripping probation protection from brand-new, not-yet-adapted
clones far too early. **Fixed**: scoped BUG8 to IMMUNE+TEACH-granted immunity only
(`not getattr(b, "probation", False)` guard added to both the decrement-floor and the revocation
check). Rerun, numeric task: mean exact-match **40.6%** (vs. the unscoped version's inflated
54.2%, vs. the true baseline's 33.3%) — a smaller but more trustworthy real improvement, with
generalization correctly back to 25.0% (1/4), matching every prior clean run instead of the
unscoped version's suspicious 0/4.

**Bit-level task, COMPLETE, scoped-fix version**: mean exact-match **54.64%**, range 48.4-58.2%
— a modest, real improvement over the 52.46% fully-clean baseline. **Zero IMMUNE+TEACH
promotions and zero revocations fired the entire 8000-cycle run** — confirming Gemini's earlier
math (a mutation improving 1-of-850 pairs shifts fitness ~0.12%, below the noise floor; teacher
promotion essentially never naturally triggers at this scale regardless of which bugs are fixed).
This means the entire improvement here comes from BUG2 (positional encoding) alone — the only
active fix that touches anything relevant to this task. Consistent with everything found
tonight: BUG2's positional nudge (max ≈2.25 on a 0-31 range) is a real but necessarily PARTIAL
mitigation of the collision-probe's representational collapse (6 distinguishable outputs for 850
required distinctions) — not a fix for it. The real lever for this task remains representational,
not promotion-quality, exactly as the collision probe indicated before any of today's 8 bugs were
even found.

**Not yet attempted, explicitly scoped out of today's "test it" round**: re-evolving a fresh
population from scratch under BUG1 and/or BUG6 enabled from cycle 0 (rather than retrofitting
either fix onto a population tuned for the old, buggy dynamics) — both authors (ChatGPT and this
session) agree that's the fair test neither fix has had yet, and it's a bigger undertaking
(full fresh run, likely needs its own seed/config matrix) than fits in this session's scope.

## ✅ WOLFPACK REPULSION, built and tested same night — real mechanism, didn't move the numbers,
## and a much bigger conversation about what SovereignCore was actually supposed to be

**⚠️ READ `[[sovereigncore_true_design_philosophy]]` (persistent memory) BEFORE touching this
substrate's architecture again.** A long conversation the same night as everything above
reconstructed Jonathan's actual original design intent, directly from him: not one network, but
a cluster of many small, complete, walled-off, deliberately-laggy, redundant, competing units —
"a hundred billion language models crushed into one skull," not a giant LLM. Large parts of this
are already in the code, broken or abandoned, under names that never explained what they were
for: `back_delay`/`base_delay` (real delay, confirmed via direct code read to never have actually
worked — `Brick.receive()` never used its own `delay` parameter), `GROWTH_CROSSOVER_ENABLED`
("gender," genuinely tried and looked like it failed on one single-seed run, but Jonathan flagged
his own uncertainty about whether that call was premature), and a newly-named-tonight goal
(redundancy as a first-class design target, not yet built anywhere) grounded in real neuroscience
about distributed fault-tolerance in biological brains. A version of the "walls + lag" philosophy
is already proven elsewhere in this project (`[[galatea_walls_make_creativity]]`, the reverse-MoE
clove-bulb architecture) — this isn't speculative, it just never got ported back into
SovereignCore's own bricks.

**Wolfpack sister-match was confirmed backwards** (2026-10-01 version picks the CLOSEST prototype,
"like-to-like" — Jonathan's own correction: the real, historically-working version pushed
DISSIMILAR local prototypes apart, with clustering of similar/agreeing content as the emergent,
INDIRECT result of repulsion alone, never a second attractive force — "repulsion only looks like
repulsion, it's still forcing things that are alike together, just not directly.")

**Implemented** as `WOLFPACK_REPULSION_ENABLED` (default False, new flag) in `_fire_relays()`:
when a local sister candidate's prototype is CLOSE (within `WOLFPACK_REPULSION_THRESHOLD=10.0`)
but its `proto_answer` DISAGREES (beyond `WOLFPACK_REPULSION_ANSWER_MARGIN=1.5`) with the
source's, push the two prototypes apart by `WOLFPACK_REPULSION_RATE=0.15`. No search needed —
reuses the already-computed local sister pool.

**Tested, full 8000-cycle runs, both tasks**: numeric task mean exact-match dropped to 27.1%
(from the 40.6% baseline — a real regression, plausibly because the numeric task's 6 simple,
already-separated patterns had little confusion to fix and repulsion just perturbed working
structure). Bit-level task: mean 52.31%, essentially unchanged from the 54.64% baseline — no
measurable improvement.

**Diagnosed why, with real counters, not just a negative number**: instrumented the trigger
conditions over a 3000-cycle run. Of every local prototype comparison made: 63.3% already AGREED
on the answer by the time two prototypes existed to compare at all; only 0.09% actually met the
repulsion trigger (close AND disagreeing). **Honest conclusion: repulsion is very likely a real,
correct mechanism, but built at the wrong stage of the pipeline.** It operates on already-formed
prototypes; the actual information collapse (BUG2's finding: 850 distinct bit-level inputs
landing on only 6 distinguishable raw outputs) happens upstream, in raw signal accumulation,
before a prototype ever gets the chance to disagree with a neighbor. By the time something
becomes a confident prototype, it's often already been shaped by the same collapsed input signal
as its neighbors, leaving little genuine disagreement left to correct. **Next step, if pursued**:
move repulsion (or an equivalent diversity-preserving force) to act on raw accumulated signal or
during prototype formation itself, not as a late correction on prototypes that already converged.

## ✅ LATERAL INHIBITION, built and tested same night as a simpler alternative to repulsion

Jonathan's own correction to the repulsion mechanism above: "the mechanism I just feel should be
simpler than I been trying to build." Repulsion needed prototype-vector distance math and
answer-comparison logic — real neuroscience gets the same push-apart effect from one of the
simplest, most common circuit motifs instead: a firing neuron directly suppresses its immediate
neighbors, no comparison of what either one represents required. Implemented as `Brick.
inhibition_strength`, a new per-BRICK evolvable trait (same pattern as `fire_threshold`: random
init, mutated, inherited across clones) — when a brick fires, same-module neighbors that didn't
fire get their `refractory` bumped proportional to the firing brick's own evolved
`inhibition_strength`. No hand-picked rate or threshold constant anywhere (unlike
`WOLFPACK_REPULSION_RATE`/`THRESHOLD` above, which Jonathan correctly flagged as inconsistent with
how every other real mechanism in this file works — evolvable traits, not fixed globals). New flag:
`LATERAL_INHIBITION_ENABLED` (default False).

**Tested, full 8000-cycle runs, both tasks**: numeric task mean exact-match **17.7%** — worse than
every other configuration tested tonight, including the original buggy baseline, with two held-out
generalization probes returning no response at all (silenced entirely). Bit-level task: mean
**50.3%**, range 42.7-56.6% — also no improvement, slightly below the 54.64% baseline.

**Honest read**: inhibition_strength initializes as `random.uniform(0.0, 1.0)` with no population
pre-adapted to its effect, same situation as BUG1 and BUG6 above — a mechanism retrofitted onto a
population that's never experienced it, not a fair test of whether the mechanism itself is sound.
Given the numeric task's sharp regression (several held-out probes going silent), the suppression
is plausibly strong enough out of the gate to meaningfully quiet the network before evolution gets
a chance to tune individual bricks' inhibition down where it hurts. Real evolutionary tuning of
this trait would need many more generations than an 8000-cycle run from a fresh population
provides — consistent with the broader, repeated finding tonight that this substrate's real
historical breakthroughs took months of continuous evolution, not thousands of cycles.

**Status after three mechanisms tried the same session** (repulsion, lateral inhibition, plus the
6 safe bug fixes): none of the two NEW mechanisms improved either task; the 6 safe bug fixes remain
the only change tonight with a clear, positive, real effect (numeric task mean 33.3%→40.6%). Both
new mechanisms are left in the code, flagged off by default, fully reversible, available for a
longer/fairer test (fresh population evolved from scratch under the mechanism from cycle 0, not a
retrofit) whenever that's worth the compute budget.

**The biggest idea of the night came right after these two negative results, and it's bigger than
either of them**: no global synchronous clock, no fixed-depth credit horizon — see
`[[sovereigncore_true_design_philosophy]]` (persistent memory), section "A fourth principle." Not
attempted this session on purpose; it means replacing the engine's execution model, not adding a
mechanism inside it.

## Status as of 2026-10-17 (this section previously said "no code written yet" — stale,
## corrected per an external review that caught the document contradicting itself)

Phase 1 is NOT a future step — it has been actively tested since 2026-10-16, with six real,
code-backed task-harness scripts in this directory and two full rounds of engine-level bug
fixing (see "ROUND 2" above). What's actually still open:

1. Decide whether to keep pushing on SovereignCore's bit-level/numeric strand, or treat the
   numeric-task positive result (real but modest: 50% peak exact-match, 25% generalization) as
   enough evidence to move to Flybrain (Phase 1's other substrate, not started) or to the
   Mamba-hybrid idea below.
2. Design a fair test of SovereignCore's own long-range retention (its relay `back_delay` and
   brick-state persistence are the natural analog of a "window"), using the same
   measure-before-you-sweep discipline from the Mamba investigation — not yet started.
3. In parallel or afterward: prototype the hybrid (small Mamba writes/reads SovereignCore state)
   as a separate, modular test — not yet started.
4. Methodology note for whoever picks this up: before trusting ANY exact-match/accuracy number
   from a NEW script in this directory, confirm its evaluation method does not call
   `_update_bricks()`/`_fire_relays()`/any other real-pipeline method directly on `self` — see
   "ROUND 2" above for why, and copy the `copy.deepcopy(self)` + random-state-restore pattern
   already used in all four existing scripts.
