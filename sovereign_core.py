#!/usr/bin/env python3
"""
Max_sovereign_core_v4_3.py
SOVEREIGN EVOLUTIONARY NEURAL SUBSTRATE (v4.3)
=====================================================================================
Architect: Jonathan David Wint (Azazel / Plato)
Engineer: Qwen (Integrated v4.2 Persistence + Zone Tags + Sleep DAG + Accumulator Bridge + Patches)
Date: May 2026

⚠️ FUTURE LLM / DEVELOPER DIRECTIVE:
- DO NOT MODIFY CORE LOGIC WITHOUT READING ALL COMMENTS FIRST.
- This is a DISCRETE, EVOLUTIONARY, MEMORY-BOUND substrate. It is NOT a transformer.
- It does NOT use backpropagation, floating-point quantization, or static DAGs.
- All observable states are INTEGER [0, 31]. Micro-signals use HIDDEN FLOAT ACCUMULATORS.
- Zone routing, sleep consolidation, and evolutionary NAS are HARD REQUIREMENTS.
- Biological mappings are architectural constraints, not metaphors.

CORE PRINCIPLES:
📐 STRICT DISCRETE STATES: mem, think, relay_strength are ALWAYS integers 0-31.
🌉 ACCUMULATOR BRIDGE: Micro-signals accumulate in hidden float buffers.
   Observable states only commit when |acc| >= 1.0. Prevents quantization oscillation.
🧬 ZONE PLASTICITY: FAST (cleanup), SLOW (persistence), MIRROR (simulation/empathy).
   Each zone routes its own LR, mutation, decay, pruning, weight bounds, and signal maps.
🌙 SLEEP CONSOLIDATION DAG: Triggered by context saturation.
   Flow: FAST replay → SLOW injection → ROM promotion → Zone drift → Context reset.
🔒 ROM PROMOTION: ≥3 consolidations + T≥8 + R≥7 + S≥8 → plasticity=0.0, weights frozen.
🔄 ZONE DRIFT: Modules self-discover optimal plasticity allocation via error/survival pressure.
🧬 EVOLUTIONARY NAS: Fitness-driven mutation, pruning, and structural growth at the synapse level.
💾 PERSISTENCE: Full state serializable, resumable, generation-tracked. Atomic checkpoint writes.

PATCHES INTEGRATED IN v4.3:
🔹 Velocity-based local prediction (replaces static mem/think mix)
🔹 Asymmetric gradient scaling (pos_scale dampens positive pushes in negative-heavy zones)
🔹 Cave Woman salience triage (deviation-sum replaces flat T*R*S multiplication)
🔹 Atomic checkpointing (.tmp → rename) survives Windows forced updates

USAGE:
  python Max_sovereign_core_v4_3.py
  python Max_sovereign_core_v4_3.py --cycles 5000
  python Max_sovereign_core_v4_3.py --resume
"""

import sys
import os
import json
import math
import random
import argparse
import gc
import signal
import atexit
import io
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# ENCODING FIX (2026-09-27): Windows console defaults to cp1252, which cannot encode the
# arrow/emoji characters this file's own status output uses -- crashes with UnicodeEncodeError on
# first print. Same class of bug already documented in this project's history (a prior "First
# Drive Result" hit an identical crash). Force UTF-8 stdout/stderr rather than editing every print
# call; does not touch any of the file's actual logic.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────────────────────────────────────
# ARCHITECTURAL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
# 📐 Discrete state bounds. All observable brick states live in [0, 31].
STATE_MIN = 0
STATE_MAX = 31

# 🌉 Accumulator threshold. Micro-signals commit to discrete state only when |acc| >= 1.0.
ACCUM_THRESHOLD = 1.0

# 🐺 WOLFPACK (2026-10-01, Jonathan) -- "socializing": a continuously-running pass that hunts for
# SICK bricks (pinned at the state boundary, the substrate's own documented ratchet-to-STATE_MAX
# risk -- every zone's signal_map above is entirely positive-valued, no inhibitory signal exists
# anywhere in this substrate, confirmed by direct measurement in sovereign_core_charlm_test.py:
# state-pinning hit 100% of living bricks by cycle 600, accuracy collapsed to chance). The existing
# sleep-DAG cull+copy mechanism (_run_sleep_dag) already replaces whole bad bricks with clones of
# good ones by TASK CREDIT, but is capped by how many "winner" bricks exist to clone from at any
# moment -- if the ratchet drifts most of the population toward STATE_MAX simultaneously (a SYSTEMIC
# bias, not per-brick), there aren't enough winners left and the whole population collapses together
# before the next sleep. Wolfpack operates at a finer grain, every cycle, not just at sleep: a sick
# brick's content isn't thrown away and replaced with an unrelated clone -- its PROTOTYPE gets
# DECOMPOSED and GRAFTED onto whichever living, healthy brick already holds the closest-matching
# prototype (reinforcing a real existing signal, "socializing" it rather than discarding it), then
# the sick brick is RESET to a fresh state so it can start over. Toggle for direct A/B testing
# (same pattern as PROBATION_CYCLES being set from the test harness): sc.WOLFPACK_ENABLED = False
# reproduces the pre-Wolfpack baseline exactly.
WOLFPACK_ENABLED = True
WOLFPACK_PIN_THRESHOLD = 50    # consecutive cycles pinned at STATE_MAX/MIN before a brick is "sick"
WOLFPACK_GRAFT_ALPHA = 0.15    # how strongly a graft nudges the healthy match's prototype toward the
# sick brick's -- small and incremental (reinforcement, not overwrite), matching this file's own
# "sloppy, cheap, constant" design philosophy rather than a single large corrective jump.
WOLFPACK_MATCH_RADIUS = 10.0   # max prototype-space distance to accept a graft target; beyond this,
# nothing living resembles the sick brick closely enough to be worth reinforcing -- reset only.

# 🐺🚫 WOLFPACK REPULSION (2026-10-17) -- Jonathan's own correction to WOLFPACK_SISTER_MATCH above:
# the 2026-10-01 "like-to-like" version (pull similar prototypes together) is confirmed, by his own
# account, to be the wrong direction -- "I switched wolf pack because it failed like to like, and
# made it reverse achieving same thing, pushing dislikes apart... created an approximation effect."
# The reverse needs no expensive search for the single best match; it just has to notice when two
# ALREADY-local candidates are confusably close in representation space despite disagreeing on the
# answer, and push them apart -- clustering of genuinely similar/agreeing prototypes is the emergent
# side effect of that alone, not a second force (see the trigger-condition comment at the call site
# in _fire_relays for the exact rule and why). Default False -- new, untested mechanism; flip True
# for a direct A/B against the collision-probe / bit-level exact-match numbers before considering it
# a default. See sc_collision_probe.py for the diagnostic this is meant to move.
WOLFPACK_REPULSION_ENABLED = False
WOLFPACK_REPULSION_THRESHOLD = 10.0   # same scale as WOLFPACK_MATCH_RADIUS -- "close enough to risk
# being confused for the same thought" is the same real distance either direction should care about.
WOLFPACK_REPULSION_ANSWER_MARGIN = 1.5   # proto_answers within this are "agreeing" (leave alone);
# matches the ans_err full-credit margin used elsewhere for "this cell's answer counts as right."
WOLFPACK_REPULSION_RATE = 0.15   # how strongly a single repulsion event pushes apart -- matches
# WOLFPACK_GRAFT_ALPHA's scale (small, incremental, "sloppy cheap constant" philosophy, not a
# single large corrective jump) since this is the same file's established design discipline.

# 🦔 LATERAL INHIBITION (2026-10-17) -- Jonathan's own simplification of WOLFPACK_REPULSION above:
# "the mechanism I just feel should be simpler than I been trying to build." Real nervous systems
# get the same "push distinct things apart, let similar things cluster" effect from one of the
# simplest, most common real circuit motifs: a firing neuron directly suppresses its immediate
# neighbors, no comparison of what either one represents required. Implemented as a per-BRICK
# evolvable trait (Brick.inhibition_strength, same pattern as fire_threshold) with NO other tunable
# constant here on purpose -- "structure is ours to design, simple, local; the parameters are never
# ours to pick." Default False -- new, untested mechanism; A/B against WOLFPACK_REPULSION_ENABLED
# and the clean baseline before considering either a default.
LATERAL_INHIBITION_ENABLED = False

# 🐺🔬 WOLFPACK LSL GATE (2026-10-08, Jonathan: "LSL might have some clues to fix my wolf pack") --
# replaces WOLFPACK_MATCH_RADIUS's single fixed global distance with a density-based accept/reject
# test, adapted from Local Support Learning (arXiv:2610.02126, verified real this session, see
# galatea_superposition_interference_idea.md Pass 10). LSL's real mechanism: an adapter's gate opens
# only when an input's density under that adapter's OWN fitted distribution (Phi_pos) exceeds its
# density under a shared reference distribution (Phi_neg) -- not a fixed threshold, a MARGIN that
# adapts to how tight or loose the local distribution actually is. Applied here: instead of "accept
# any living brick within a fixed radius of 10.0, treating a dense cluster and a sparse one
# identically," fit Phi_pos from the WOLFPACK_GATE_K_NEIGHBORS healthy prototypes nearest the sick
# brick (the local neighborhood the graft target actually sits in) and Phi_neg from ALL living
# healthy prototypes pooled (the generic reference, same role as LSL's small generic pretraining
# sample) -- accept the graft only if the sick brick's prototype is MORE consistent with that local
# neighborhood than with the population at large. A tight, crowded neighborhood gets a strict
# effective radius; a sparse one gets a lenient one -- exactly what a single hand-picked constant
# cannot do. The actual graft TARGET is still the single nearest healthy brick (unchanged); this
# only changes the ACCEPT/REJECT decision. Pre-validated on a separate substrate before being ported
# here: lsl_gate_routing_test.py (D:\flybrain) showed a real fitted gate of this same shape (diagonal
# Gaussian Phi_pos/Phi_neg, log-density margin) recovers routing performance indistinguishable from
# (slightly better than) oracle-labeled routing -- 94.2% agreement, 6.871 vs 6.906 loss.
# ✅ MULTI-SEED A/B CONFIRMED on Sovereign Core itself, 2026-10-09 (5 seeds: 42, 7, 13, 99, 2024;
# 2000 cycles each, same methodology as every other A/B in this file): final-checkpoint exact-match
# improved on 4/5 seeds (avg 6.06% baseline -> 11.3% gate, nearly double; seed 7 alone: 8.7% -> 23.9%).
# The gate grafts LESS OFTEN in 5/5 seeds (more selective, no exceptions) and does NOT reduce raw
# pinning (a wash, 32.7% baseline vs 34.2% gate) -- it trades quantity for quality: fewer grafts, but
# the ones it accepts are precise enough to show up in real task retention, exactly what LSL's own
# theory predicts. First Wolfpack-family mechanism in this file's history to earn default-ON purely
# on a measured multi-seed CAPABILITY gain, not just symptom containment (every prior result here --
# decay, Wolfpack alone, sister-match -- only ever touched pinning without moving accuracy). Full
# numbers: galatea_superposition_interference_idea.md Pass 10. Toggle for direct A/B:
# sc.WOLFPACK_LSL_GATE = False reproduces the pre-gate fixed-radius baseline exactly.
WOLFPACK_LSL_GATE = True
WOLFPACK_GATE_K_NEIGHBORS = 5       # size of the local neighborhood Phi_pos is fit from
WOLFPACK_GATE_VAR_FLOOR_FRAC = 0.1  # variance floor as a fraction of the GLOBAL (Phi_neg) per-dim
# variance -- prevents a near-degenerate local neighborhood (e.g. K neighbors that happen to be
# nearly identical) from producing a near-zero variance that makes the gate pathologically strict;
# same role as the variance floor in lsl_gate_routing_test.py's fit_diag_gaussian, same fraction
# scaled down slightly since K=5 here is a much smaller sample than that test's whole-cluster fits.

# 🐺🔬 WOLFPACK LSL PIN-GATE (2026-10-09, Jonathan: "port the same gate idea to the pin-threshold
# timer, the last unbuilt piece") -- the third of the three swaps scheduled in
# galatea_superposition_interference_idea.md Pass 10. WOLFPACK_PIN_THRESHOLD=50 gates on a hard
# structural fact (mem/think/relay_strength exactly AT the integer boundary) for a fixed number of
# consecutive cycles, applied identically to every zone regardless of that zone's own dynamics (FAST
# decay=0.35, SLOW=0.15, MIRROR=0.25 -- a SLOW brick's natural restoring force is more than twice as
# weak as FAST's, so "stuck 50 cycles" is not equally anomalous in both). Unlike the graft-accept
# gate (a genuine two-sided "does this match THIS neighborhood or the background" question), raw
# boundary-touching is a hard yes/no fact, not something density estimation improves. What a density
# gate CAN improve: the exact-equality check misses a brick persistently oscillating just short of
# the boundary (e.g. 29-30-29-30 in a zone whose healthy baseline sits near the center) -- genuinely
# unhealthy drift that `>= STATE_MAX` structurally cannot see. WOLFPACK_LSL_PIN_GATE replaces the
# per-cycle accumulate condition: instead of "touching the exact boundary," accumulate when a
# brick's (mem, think, relay_strength) state has LOWER density under its OWN ZONE's healthy
# baseline (Phi_pos, fit each cycle from that zone's living pin_streak==0 bricks) than under the
# shared background (Phi_neg, fit from every living brick pooled) -- same Phi_pos/Phi_neg margin
# mechanism as the graft gate, applied to raw state instead of prototype. WOLFPACK_PIN_THRESHOLD
# itself (the consecutive-cycle requirement) is UNCHANGED and deliberately not touched in this same
# edit -- that is a separate, orthogonal question with no evidence yet either way, and bundling two
# unproven changes into one A/B would make neither result interpretable. A zone with fewer than 2
# currently-healthy bricks has nothing to fit Phi_pos from; those bricks fall back to the original
# exact-boundary check that cycle rather than guessing.
# ❌ MULTI-SEED A/B RESULT, 2026-10-09 -- NEGATIVE, not just unproven. Same 5-seed/2000-cycle
# methodology as WOLFPACK_LSL_GATE's confirmation, isolating only this toggle on top of that
# already-default-on gate. Final exact-match: baseline avg 11.3% -> pin-gate avg 6.1% (nearly
# halved); wins 1/5 seeds, ties 1/5, loses 3/5 (two large losses, -21.7pp and -10.9pp). Root cause
# visible directly in the data: this gate flags ~2x MORE bricks as sick than the exact-boundary
# check, every seed -- the opposite direction from the graft gate (which won by being MORE
# selective). Over-triggering resets real, harmless state for bricks that were never actually
# pathological. Full numbers: galatea_superposition_interference_idea.md Pass 11. Stays OFF --
# this is a tested, closed, negative result, not an open question. Toggle for re-verification only:
# sc.WOLFPACK_LSL_PIN_GATE = True.
WOLFPACK_LSL_PIN_GATE = False

# 🐺🤝 WOLFPACK SISTER-MATCH (2026-10-01, Jonathan: "the relays... they are the Wolfpack. That's the
# mistake, that's what I forgot to do.") -- real correction to where Wolfpack actually belongs. The
# EXISTING sister-split mechanism in _fire_relays (below) already does the hard structural half of
# Wolfpack correctly: detects an overloaded brick (prediction_error > the relay's own evolvable
# threshold), splits off the excess, and redirects it to a DIFFERENT "sister" cell in the same module
# (never the source, never its direct feeders -- the design that already correctly avoids forming a
# tight loop). What it was missing is the "like-to-like" half Wolfpack specifically requires -- sister
# selection was pure `random.sample`, no awareness of which sister's existing pattern the excess
# signal actually resembles. WOLFPACK_SISTER_MATCH=True makes that selection CONTENT-AWARE: prefer
# sisters whose prototype is closest to the source brick's own prototype, falling back to the original
# random behavior only when the source has no prototype yet (nothing to content-match against) or no
# prototype-bearing sister exists.
WOLFPACK_SISTER_MATCH = True

# 🐊 DECAY WIRING (2026-10-01, Jonathan) -- "the sabertooth went extinct from being too perfect a
# predator; crocodiles and Komodo dragons independently evolved brumation/torpor instead -- near-zero
# metabolism, still reflexively reactive to a real trigger." His point, made precise against the real
# code: each ZONE_PARAMS entry above ALREADY DEFINES its own "decay" value (FAST 0.35, SLOW 0.15,
# MIRROR 0.25) -- but a direct grep of this entire file found it is NEVER READ anywhere. A real,
# designed-but-never-wired restoring force, not a new mechanism being invented: the zone orientations
# even already say what was intended ("cleanup" for FAST = light sleeper, fast decay; "persistence"
# for SLOW = deep torpor, rarely disturbed; "simulation" for MIRROR = in between). This is a DIFFERENT
# fix than Wolfpack: Wolfpack cleans up a brick AFTER it's already pinned (reactive); decay pulls every
# brick continuously back toward center at its OWN zone's designed rate (preventive, targets the root
# cause the substrate's own comments already named -- "no inhibitory signal exists anywhere").
DECAY_ENABLED = True
DECAY_PULL_SCALE = 0.05   # keeps the per-cycle pull GENTLE (a continuous restoring force, not a
# sudden correction) -- a brick pinned at STATE_MAX in the fastest-decaying zone (FAST, 0.35) pulls
# by roughly (31-15.5)*0.35*0.05 =~ 0.27/cycle, taking dozens of cycles to meaningfully move, same
# "sloppy, cheap, constant" design philosophy as Wolfpack rather than a jarring one-shot fix. Tunable;
# this is a starting value to measure from, not a derived constant.

# 🧬🔀 GROWTH CROSSOVER + SIZE-AWARE SELECTION (2026-10-02, ported from G-EvoNAS, arXiv:2403.02667,
# after Jonathan asked for a direct comparison: "see if it can fix mine or if necessary replace mine").
# G-EvoNAS's SuperNet weight-sharing does NOT transfer here -- it fixes proxy-ranking noise from cheaply
# evaluating untrained candidates, a problem this substrate doesn't have (bricks are already live and
# continuously self-evaluating on real feedback). But two real structural gaps in _grow_network DO map
# directly onto two of G-EvoNAS's real mechanisms:
# (1) growth previously cloned from a SINGLE top-fitness donor module and gaussian-mutated the copy --
#     pure asexual mutation, no crossover at all. G-EvoNAS crosses TWO elite parents' connections and
#     operations together (its "constrained uniform crossover").
# (2) growth previously ranked candidate modules by raw average fitness only. The EXISTING
#     `n_alive < INIT_BRICKS*2` check (see _run_sleep_dag) is a global binary size gate, not a
#     per-candidate trade-off the way G-EvoNAS's two-objective (accuracy vs size) pNSGAIII selection is.
GROWTH_CROSSOVER_ENABLED = False  # OFF by default -- unlike Wolfpack/decay/PROBATION_CYCLES, this has
# NOT been shown to help. The only real A/B run so far (2000 cycles, same seed/task as every other test
# in this file) trended WORSE, not better: baseline exact-match 4/46 (8.7%) vs crossover+size-aware ON
# 2/46 (4.3%). One run, one seed -- not a verdict either way, but not grounds for a default ON either.
# Toggle for direct A/B: sc.GROWTH_CROSSOVER_ENABLED = True to test it.
GROWTH_CROSSOVER_RATE = 0.3     # fraction of new clones built by blending TWO parent modules' traits
# (real two-parent crossover) instead of mutating a single donor's, when GROWTH_CROSSOVER_ENABLED=True.
GROWTH_SIZE_AWARE = False        # OFF by default, same reason as GROWTH_CROSSOVER_ENABLED above -- not
# yet shown to help, same single A/B run. When True, ranks candidate modules for growth by fitness PER
# BRICK (avg_fitness / module_size) instead of raw avg_fitness alone -- a cheap proxy for G-EvoNAS's
# accuracy-vs-size Pareto objective. Needs multi-seed testing before this is a real default candidate.

# 🏗️ Initial substrate size & spatial layout
INIT_BRICKS = 500
MODULE_SPACING = 40.0
MODULE_SIZE = 25.0
MAX_SYNAPSES_PER_BRICK = 24

# 🧠 Context capacity & sleep trigger
CONTEXT_CAPACITY = 1000
CONTEXT_THRESHOLD = 0.85       # sleep fires at this context-load fraction (RAISE = sleep LESS OFTEN)

# 🔍 2026-10-17: the %500 "SHOW ACTUAL ANSWERS" debug probe in run_cycle() calls _update_bricks()
# and _fire_relays() once per TASK_PAIR -- those are NOT passive reads, they are the real training
# machinery (commit_accumulators, prediction-error update, IMMUNE+TEACH promotion, relay split/
# usage counters, real signal delivery to sister cells via .receive()). Confirmed directly: the
# `splits` counter jumps by ~140,000-210,000 every time this probe fires on an 850-pair task,
# vs. a steady ~8,000/100-cycles baseline everywhere else -- an 18-25x spike, not a passive read.
# Earlier fix (context_tokens snapshot/restore) only stopped this probe from forcing premature
# sleep; it never addressed this much larger disturbance, and the disturbance scales with
# len(TASK_PAIRS) -- 6 for the numeric task, 850-905 for every language/bit task -- so it was
# never an equal, controlled confound across configs. DIAGNOSTIC_PROBE_ENABLED=False makes every
# controlled experiment run with this probe fully disabled (not merely restored); flip to True
# only for interactive/manual debugging where seeing live sample answers matters more than a
# clean measurement.
DIAGNOSTIC_PROBE_ENABLED = False

# 🧪 2026-10-17: A/B TOGGLE for the IMMUNE+TEACH ablation experiment, proposed convergently by
# four independent models (ChatGPT, DeepSeek, Qwen, Gemini) given the clean post-fix numeric-task
# results (TaskCorrect 0.67-0.89, exact-match peak 50%, generalization only 1/4=25%, outputs
# cluster around a few memorized attractor values). Shared theory: a brick that gets lucky on a
# few of only 6 training pairs crosses recent_task_score>0.85, earns permanent-feeling protected
# "teacher" status (cull_immune=True) after only 40 cycles, then broadcasts its (memorized, not
# general) answer as a stable target for neighbors to imitate -- actively crystallizing the
# memorized attractors rather than letting evolution keep searching for something that
# generalizes. ⚠️ CORRECTION (2026-10-17, later the same night): I originally wrote here that
# immunity is "NOT literally permanent" because of a revocation path (cull_immune=False if
# recent_task_score<0.40 for 60+ consecutive cycles). That was WRONG -- checked again after
# ChatGPT (reading this file directly) pointed out the decrement that feeds that check is
# `consolidation_streak = max(0, ... - 1)`, which is FLOORED at 0 and can mathematically never
# reach <=-60. The revocation branch was dead code; immunity really was permanent once granted.
# See BUG8_IMMUNITY_REVOCABLE below for the real fix. Default True preserves the exact historical/
# proven behavior (every result recorded in HANDOFF.md through this point used this). Set False
# for a clean ablation run: does held-out generalization improve with teacher promotion disabled
# entirely, same seed, same task, nothing else changed?
IMMUNE_TEACH_ENABLED = True

# 🐛✅ 2026-10-17, "apply fixes and test it": 8 concrete, code-verified bugs found by ChatGPT
# (given live GitHub read access to this exact file) during the adversarial-review follow-up, all
# reviewed by Jonathan directly, all applied here as real fixes (not just ablation toggles) since
# they're genuine defects against the engine's own documented design intent, not design-philosophy
# questions. Each flag below defaults to the FIXED/correct behavior; set False only to reproduce
# the old (buggy) behavior for an A/B comparison against every prior result in HANDOFF.md.

# BUG1: _fire_relays() never checked b.fired_this_cycle -- relays kept transmitting regardless of
# whether the source brick actually fired in response to the current input, completely decoupled
# from the engine's own "SPEAK-ONLY-WHEN-SPOKEN-TO" firing-gate design. This IS a real, confirmed
# discrepancy against the documented design intent. The "fix" (gate relay transmission on
# fired_this_cycle) is correct in principle, but TESTED DIRECTLY (2026-10-17) and found to break
# the numeric task outright when applied as a hard default: TaskCorrect flatlined at exactly 0.500
# (the _evaluate_fitness fallback for "no response produced"), exact-match dropped to 0/6, every
# held-out generalization probe returned None (no output brick ever fired). The existing,
# already-evolved population apparently relies on relays propagating regardless of firing status
# to maintain enough baseline signal flow to function at all -- removing that without letting the
# population re-evolve under the new regime effectively silences the network. Confirmed via direct
# A/B: reverting ONLY this one flag (all 7 other fixes still applied) restored healthy behavior
# (TaskCorrect 0.76-0.89, real IMMUNE+TEACH promotions AND revocations both firing correctly).
# ChatGPT itself flagged this exact risk when it found the bug: "I would not blindly add a firing
# gate to the production engine -- doing so could change its existing dynamics dramatically. But a
# controlled experiment comparing firing-gated versus ungated relays is now a very high priority."
# Default False (preserves working behavior) until a real controlled experiment -- ideally letting
# the population evolve from scratch UNDER the gated regime, not retrofitting it onto a population
# tuned for the old one -- can test whether gating helps once given a fair chance to adapt.
BUG1_RELAY_REQUIRES_FIRING = False

# BUG2: inject_problem()'s generic `for elem in call: b.receive(...)` loop is provably
# order-independent (receive() only does additive accumulation, and addition is commutative) --
# only call[-1]/call[-2] carried any positional information via separate explicit lines. For a
# 16-element bit-level context, 14 of 16 positions collapsed into one order-blind sum -- the
# mechanistic root cause of the 99.8% collision rate found by sc_collision_probe.py. Real fix:
# scale each element's injected signal by a position-dependent factor so order actually matters.
BUG2_POSITION_AWARE_ENCODING = True
POSITION_WEIGHT_SCALE = 0.15  # tuning knob for how strongly position affects injected magnitude

# BUG3 (partial fix -- see HANDOFF.md for the part NOT changed): recent_task_score's recog_reward
# gate (the signal that specifically drives IMMUNE+TEACH promotion eligibility) was too lenient --
# ans_err<1.5 -> full reward, ans_err<3.0 -> half reward -- on a [0,31] range that's a wide margin
# for "close enough to be trusted as a teacher." Tightened here. NOTE: the core whole_correct
# graded-closeness fitness formula (which drives ordinary evolutionary selection pressure, not
# teacher promotion specifically) is intentionally left untouched -- smooth partial-credit shaping
# for a search/selection signal is standard practice, not obviously a bug, and changing it would
# alter the whole fitness landscape in ways nobody has reason to be confident about yet.
BUG3_STRICT_TEACHER_REWARD = True
TEACHER_REWARD_FULL_MARGIN = 0.75   # was 1.5
TEACHER_REWARD_HALF_MARGIN = 1.5    # was 3.0

# BUG4 (partial fix -- see HANDOFF.md for the part NOT changed): `improved = whole_correct > prev`
# compared the current cycle's whole-organism correctness against a SINGLE GLOBAL previous value,
# even though consecutive cycles can present completely different, unrelated task pairs under
# interleaved training -- a relay could get "split_helped" credit merely because a DIFFERENT,
# easier task happened to score higher right after it split, not because its own split caused
# anything. Real fix: track the previous score PER TASK (keyed by the call tuple), so "improved"
# genuinely means "this same task scored better than last time it was presented." NOTE: the
# deeper static-synapse-graph-vs-dynamic-relay-path credit mismatch ChatGPT also flagged is NOT
# fixed here -- redesigning credit propagation to follow the actual relay/sister delivery graph
# instead of the static synapse graph is a much larger change than this batch's scope.
BUG4_PER_TASK_IMPROVEMENT_TRACKING = True

# BUG5: a "frozen" teacher brick's _teach_answer could still drift -- _update_bricks() pins
# b.mem/think to the stored _teach_answer at the TOP of the cycle, but commit_accumulators() ran
# for teach_freeze bricks too (only rom_locked bricks were skipped) and could change b.mem again
# the SAME cycle, and the drifted value then became the new _teach_answer at the bottom. Real fix:
# skip commit_accumulators/update_prediction_error for teach_freeze bricks too, matching the
# "hold a stable target while teaching" design intent already stated in the code's own comments.
BUG5_TRUE_FROZEN_TEACHER = True

# BUG6 (the biggest architectural change in this batch, and -- confirmed by direct testing,
# 2026-10-17 -- the one that breaks exact-match precision outright): Brick.receive(signal, src_id,
# delay) never referenced its own `delay` or `src_id` parameters -- every signal applied
# synchronously, same-cycle, regardless of the evolved back_delay/base_delay relay traits. The
# "delayed, temporally offset" signal-propagation design described in this file's own comments had
# zero actual effect. The fix (a real pending-delivery queue, flushed once per cycle) is correct
# and DOES make the evolved delay traits actually delay signal arrival -- but isolated-tested
# against the numeric task, it alone collapses exact-match to 0/6 across an entire 8000-cycle run
# (TaskCorrect stayed superficially healthy, 0.76-0.85, since that's a graded closeness metric, not
# exact correctness). Leading hypothesis, not yet confirmed: _read_response() only counts bricks
# that fired THIS exact cycle, and introducing real multi-cycle delay pushes the informative signal
# to arrive on a DIFFERENT cycle than whichever one _read_response() happens to be called on,
# systematically losing exact-value precision even though the substrate is still "in the right
# ballpark." Confirmed via direct A/B: reverting ONLY this flag (BUG1 also off, all other 6 fixes
# on) restored healthy exact-match (2/6, 1/6, 3/6 across checkpoints, matching/exceeding the proven
# baseline). Default False (preserves working behavior) -- real delayed delivery is architecturally
# correct and probably worth pursuing, but needs the readout/evaluation logic redesigned around
# genuinely asynchronous arrival (and likely a population re-evolved under the new timing regime)
# before it can be a safe default, not a one-flag flip.
BUG6_REAL_SIGNAL_DELAY = False

# BUG7 is fixed at the test-script level (lucy_original_numeric_task.py's generalization_check),
# not here -- inject_problem()'s TASK_PAIRS-lookup default (0 for any call not in TASK_PAIRS) was
# silently leaking a wrong target into the substrate's internal dynamics during every held-out
# probe. No engine-level flag needed; see that script for the fix.

# BUG8: the de-immunization check `consolidation_streak <= -60` was unreachable because the decay
# branch floored the streak at 0 (`max(0, ... - 1)`), so it could never go negative. Real fix:
# remove the floor on the DECAY path only (the GROWTH path still requires a real positive streak
# to re-earn immunity, unaffected) so sustained poor performance can actually revoke protection.
BUG8_IMMUNITY_REVOCABLE = True

GROWTH_FACTOR = 1.25
MAX_CULL_FRAC_CFG = 0.20       # cull at most this fraction of worst cells per sleep (LOWER = punish LESS)
ALIVE_FLOOR_FRAC_CFG = 0.60    # never cull below this fraction of population (RAISE = punish LESS)
DAY_CONTEXT = 5000            # context window size = a "DAY" of experience; fills ~once per this many cycles -> sleep. RAISE = longer day.
PRESERVE_DIVERSITY = True      # don't merge distinct prototype clusters; protect endangered prototypes

# PROBATION WINDOW (2026-09-28): originally "one full inter-sleep window," which is an EMERGENT
# duration (sleep is context-fullness-triggered, not a fixed cadence) -- at defaults, ~850 cycles
# (CONTEXT_CAPACITY * CONTEXT_THRESHOLD). Made an explicit, cycle-precise, independently-testable
# parameter (decoupled from sleep cadence entirely) specifically to A/B it: is ~850 cycles of
# cull-immunity for a discounted clone too long, too short, or about right? Cleared every cycle in
# the main loop now, not just at the next sleep event, so a shorter window actually takes effect
# sooner rather than silently waiting for the next sleep regardless of the configured value.
#
# REAL A/B RESULT (2026-09-28, --cycles 4000 --seed 42, identical seed across all three arms,
# runs bit-identical through cycle 1600 before diverging -- see probation_test_{FULL_850,HALF_425,
# LONG_1700}.log in this directory):
#   PROBATION_CYCLES=425 (half):  late-run (cyc 3400-3900) TaskCorrect DROPPED to 0.64-0.66 for
#                                 four straight checkpoints before partially recovering to 0.750 --
#                                 a real, measured degradation. Discounted clones got re-exposed to
#                                 culling before they'd had time to re-prove themselves.
#   PROBATION_CYCLES=850 (default): late-run (cyc 3400-4000) TaskCorrect held 0.81-0.85, avg ~0.836.
#   PROBATION_CYCLES=1700 (double): late-run (cyc 3400-4000) TaskCorrect held 0.81-0.86, avg ~0.837
#                                 -- statistically indistinguishable from 850. Doubling the window
#                                 bought NOTHING further.
# CONCLUSION: shorter is a real, measured harm; longer (at least up to 2x) is FREE -- costs nothing,
# gains nothing. This argues against "just tune the constant bigger" (no evidence more helps) and
# does NOT clearly argue for adaptive feedback either (if slow-but-eventually-good clones existed,
# more time should have helped at 1700 and didn't -- the clones that recover mostly do so well
# within 850; the ones that don't likely wouldn't with more time either). Single-seed result, not
# fully conclusive -- but the practical takeaway stands regardless: when in doubt, err LONG. Since
# padding this constant costs nothing, there is no reason to ever set it below the default out of a
# desire to "save" population churn -- that trade doesn't exist in the data.
PROBATION_CYCLES = 850

# 🧬 Evolutionary pressure constants
MUTATION_RATE = 0.15
VARIATION_MAGNITUDE = 0.2
SELECTION_PRESSURE = 0.15
PRUNE_FITNESS_FLOOR = 0.15
ROM_CONSOLIDATION_THRESHOLD = 3
SEED_CRANK_PASSES = 50   # MINIMUM crank passes before even CHECKING for engine-catch
ENGINE_CATCH_MIN_CELLS = 25   # this many NON-seed cells reliably correct => engine caught => crank may release
TEACH_FREEZE_WINDOW = 30   # cycles a newly-consolidated cell stays a STABLE teacher, then returns to plastic
RECOGNITION_MODE = "nearest"   # "graded" (RBF kernel, 1/distance) or "nearest" (closest prototype wins)
# 🗳️➡️➕ READOUT_MODE, 2026-10-19: "vote" (default, unchanged) is the original hand-designed
# weighted-AVERAGE readout -- num/den, confined to the convex combination of whatever the voting
# bricks already report, no matter how the weights are chosen. "linear" is the first-class
# alternative born from a long night of digging into why that ceiling exists: an UNCONSTRAINED
# linear combination (sum of readout_weight*val, no normalization, negative weights allowed),
# using a genuinely EVOLVABLE per-brick trait (Brick.readout_weight, mutated the same way as
# fire_threshold/inhibition_strength -- "the parameters are never ours to pick"). Eight tests
# tonight (see SovereignCore's HANDOFF.md, "FINDING #1 RESOLVED") proved this can only be tested
# fairly as a properly integrated engine option, trained from scratch, never as a live override
# bolted onto a running system -- a bolt-on override hijacks _evaluate_fitness()'s own training
# signal (which reads _read_response() directly, every cycle) before the substitute readout's own
# weights have had any chance to converge. This flag makes "linear" a real, equal alternative to
# "vote" from cycle 1, so the WHOLE population evolves under it honestly, the same way
# RECOGNITION_MODE's two real options always have.
READOUT_MODE = "vote"          # "vote" (original weighted-average) or "linear" (unconstrained,
                                 # evolvable combination weights)
RBF_SIGMA = 6.0               # kernel width: how close counts as "recognized" (graded mode)
PROTO_LEARN_RATE = 0.10       # EMA rate at which a cell's prototype moves toward calls it answers correctly

# 💾 Checkpoint & persistence
CHECKPOINT_PATH = Path("sovereign_checkpoint_v4_3.json")

# ─────────────────────────────────────────────────────────────────────────────
# ZONE PARAMETERS (Plasticity Allocation & Signal Mapping)
# ─────────────────────────────────────────────────────────────────────────────
# 🧬 Each zone defines its own learning rate, mutation pressure, decay rate,
# pruning threshold, weight bounds, functional orientation, signal map, and
# asymmetric scaling factor (pos_scale) to prevent negative basin trapping.
ZONE_PARAMS = {
    "FAST": {
        "lr": 0.20, "mut": 0.25, "decay": 0.35, "prune": 0.30,
        "weights": (-3, 1), "orientation": "cleanup",
        "signal_map": {-3: 0.05, -2: 0.2, -1: 0.5, 0: 0.8, 1: 1.3},
        "pos_scale": 0.75  # 🔒 Dampens positive pushes in negative-heavy zones
    },
    "SLOW": {
        "lr": 0.05, "mut": 0.05, "decay": 0.15, "prune": 0.10,
        "weights": (-1, 3), "orientation": "persistence",
        "signal_map": {-1: 0.5, 0: 0.8, 1: 1.3, 2: 1.8, 3: 2.5},
        "pos_scale": 1.0   # Balanced/positive zone: no damping needed
    },
    "MIRROR": {
        "lr": 0.12, "mut": 0.18, "decay": 0.25, "prune": 0.20,
        "weights": (-2, 2), "orientation": "simulation",
        "signal_map": {-2: 0.15, -1: 0.4, 0: 0.7, 1: 1.1, 2: 1.6},
        "pos_scale": 0.9   # Slight damping for symmetric stability
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────
class Synapse:
    """
    🧬 Discrete connection between bricks.
    Weight lives in zone-bounded integer range. Delay enables temporal coding.
    Accumulator bridges micro-gradient signals to discrete weight updates.
    """
    def __init__(self, target_id: int, weight: int, delay: int):
        self.target_id = target_id
        self.weight = weight
        self.delay = delay
        self.fitness = 0.5
        self.acc = 0.0

    def update_discrete(self, zone_cfg: dict):
        """🌉 Commit accumulator to discrete weight when threshold crossed."""
        if abs(self.acc) >= ACCUM_THRESHOLD:
            delta = int(self.acc)
            self.weight += delta
            self.acc -= delta
            w_min, w_max = zone_cfg["weights"]
            self.weight = max(w_min, min(w_max, self.weight))

    def weaken(self):
        """🍂 Decay synapse for pruning/autosarcophagy."""
        self.weight = max(-3, self.weight - 1)
        self.fitness *= 0.9

class PairedRelay:
    """
    🧠 Structural glue between bricks/modules.
    RelayA: Decision gate. RelayB: Distribution router.
    Phase offset prevents crosstalk between unrelated signal streams.
    """
    def __init__(self, source_id: int, targets: List[int], base_delay: int):
        self.source_id = source_id
        self.targets = targets
        self.base_delay = base_delay
        self.phase = random.uniform(0, 2 * math.pi)
        self.fitness = 0.5
        self.age = 0
        self.usage_count = 0
        self.suppressed = False
        # 🧬 EVOLVABLE SPLIT TRAITS (the relay-split anti-runaway mechanism).
        # These are TRAITS, not constants: each relay starts with its own random values, and selection
        # (driven by WHOLE-ORGANISM correctness, NOT local comfort) tunes them. A relay whose splitting
        # helps the substrate answer correctly survives & multiplies; one that games stability dies.
        # 🔒 GOVERNANCE: these only get rewarded via the substrate's correctness (see _evaluate_fitness),
        #    so evolution cannot win by "split constantly + stay calm" (that would be the cancer/moss failure).
        self.split_threshold = random.uniform(1.5, 4.0)   # how big an ERROR before this relay splits & retrains
        self.split_ratio = random.uniform(0.4, 0.6)        # fraction sent BACK (rest goes forward). Starts ~half.
        self.back_delay = random.randint(2, 6)             # delay on the backward (retrain) signal (temporal spread)
        self.split_count = 0                               # how often it fired a split (for telemetry)
        self.split_helped = 0                              # how often a split was followed by improved correctness
        # MOSS/CANCER FIX (2026-09-27): a relay that never splits was never evaluated at all by the
        # split_helped/fitness credit step below (it only fired `if relay.split_count > 0`) -- making
        # "never act" a strictly risk-free strategy and letting split_threshold drift upward across
        # generations with zero penalty, exactly the "successful moss that changes the climate and
        # kills everything off" failure this file's own comments already named. Track missed chances
        # so inaction stops being invisible to selection.
        self.missed_split_count = 0                        # how often error was real but this relay chose not to split
        # CREDIT-WINDOW FIX (2026-09-27, independently verified against this exact file): split_count
        # is cumulative and NEVER reset -- the credit step below originally checked `split_count > 0`,
        # meaning a relay that split even ONCE, ever, stays eligible for reward/punishment on every
        # future cycle regardless of whether it actually acted this cycle. split_this_cycle is the
        # transient flag credit is actually allowed to see; split_count remains as pure telemetry.
        self.split_this_cycle = 0

    def mutate_traits(self, rate: float):
        """🧬 Evolve the split traits. Small random walk, bounded to sane ranges."""
        if random.random() < rate:
            self.split_threshold = max(0.5, min(8.0, self.split_threshold + random.uniform(-0.3, 0.3)))
        if random.random() < rate:
            self.split_ratio = max(0.1, min(0.9, self.split_ratio + random.uniform(-0.05, 0.05)))
        if random.random() < rate:
            self.back_delay = max(1, min(10, self.back_delay + random.choice([-1, 0, 1])))

    def tick(self):
        """⏱️ Advance relay lifecycle. Age increases, phase rotates."""
        self.age += 1
        self.phase = (self.phase + 0.1) % (2 * math.pi)
        if self.usage_count == 0:
            self.fitness *= 0.98

class Brick:
    """
    🧱 Fundamental computational unit.
    States: mem (integration), think (pattern recognition), relay_strength (fire amplitude).
    All observable states are integers 0-31. Hidden accumulators bridge micro-signals.
    """
    def __init__(self, brick_id: int, pos: Tuple[float, float, float], module_id: int, zone: str):
        self.id = brick_id
        self.pos = pos
        self.module_id = module_id
        self.zone = zone
        self.alive = True
        self.energy = 20.0
        self.stability = 0.9
        self.fitness = 0.5
        self.age = 0
        self.rom_locked = False
        self.plasticity = 1.0          # default; consolidation reduces it, ROM-lock zeroes it
        self.consolidation_count = 0
        
        self.mem = random.randint(0, STATE_MAX)
        self.think = random.randint(0, STATE_MAX)
        self.relay_strength = random.randint(0, STATE_MAX)
        
        self.mem_acc = 0.0
        # 🔇 SPEAK-ONLY-WHEN-SPOKEN-TO (v4.7): silent by default, fire only on sufficient input.
        # Energy-frugal (organic tissue is silent by default), anti-explosion (silence can't run away),
        # anti-drowning (silent cells don't dilute the readout), multi-reflex (each cell quiet except for
        # its own call). fire_threshold is EVOLVABLE so selection finds the right "how much before I speak".
        self.fired_this_cycle = False
        self.input_this_cycle = 0.0       # magnitude of input received this cycle (were we spoken to?)
        self.prototype = None             # 🧠 the call-pattern this cell has learned to RECOGNIZE (avg of calls it answered well)
        self.proto_answer = None          # the answer associated with that prototype
        self.match_weight = 0.0           # how well the CURRENT call matches this cell's prototype (set each cycle)
        self.fire_threshold = random.uniform(0.3, 1.5)   # evolvable cost-gate to speak
        self.refractory = 0               # cycles of forced silence remaining after firing
        # 🦔 LATERAL INHIBITION (2026-10-17, Jonathan's own correction to the prototype-distance
        # repulsion tried earlier the same night -- "the mechanism I just feel should be simpler
        # than I been trying to build"): the real biological mechanism for "push dissimilar things
        # apart, let similar things cluster as the side effect" isn't vector-distance comparison --
        # it's lateral inhibition, one of the simplest, most common real circuit motifs: when I
        # fire, I suppress my immediate neighbors' ability to also fire. No prototype math, no
        # distance threshold, no comparing answers. A brick doesn't need to know WHAT it or its
        # neighbor represents for this to work. Evolvable, same pattern as fire_threshold right
        # above it -- "structure is ours to design, simple, local; the parameters are never ours to
        # pick" (Jonathan's own framing, after noticing WOLFPACK_REPULSION_RATE/THRESHOLD were
        # fixed global constants I'd hand-picked, unlike every other real trait in this file).
        self.inhibition_strength = random.uniform(0.0, 1.0)   # how hard MY firing suppresses
        # local competitors -- 0 = no inhibitory effect at all, 1 = maximal
        # 🗳️➡️➕ READOUT_WEIGHT (2026-10-19, see READOUT_MODE above): this brick's own weight in
        # the UNCONSTRAINED linear-combination readout ("linear" mode only -- "vote" mode ignores
        # this entirely and keeps using stability*fitness, unchanged). Small random init, evolvable
        # by mutation like every other real trait here, free to drift negative -- a brick that
        # turns out to be anti-correlated with the right answer is exactly as useful as one that's
        # positively correlated, once the combination rule isn't forced to be a simple average.
        self.readout_weight = random.uniform(-0.5, 0.5)
        self.think_acc = 0.0
        self.relay_acc = 0.0
        
        self.prediction_error = 0.0
        self.consecutive_errors = 0
        self.correct_predictions = 0
        self.pin_streak = 0    # 🐺 Wolfpack: consecutive cycles touching STATE_MAX/MIN (see module const)

        # 🍼 TASK INTERFACE (call-and-response / "mama" loop):
        # An input (call) is presented; the brick predicts the completion (response). If it matches the
        # known-correct answer, the WHOLE substrate is rewarded (and so, downstream, is this brick).
        self.last_call = None          # the call value most recently received (for prediction)
        self.last_response = None      # the response this brick emitted
        self.task_correct = False      # did this brick's response match the target on the last trial?
        self.recent_task_score = 0.5   # rolling correctness (the part's contribution to the whole's success)

        self.synapses: List[Synapse] = []
        self.relays: List[PairedRelay] = []

    def clamp_state(self):
        """🔒 Ensure observable states stay within [0, 31]."""
        self.mem = max(STATE_MIN, min(STATE_MAX, self.mem))
        self.think = max(STATE_MIN, min(STATE_MAX, self.think))
        self.relay_strength = max(STATE_MIN, min(STATE_MAX, self.relay_strength))

    def commit_accumulators(self, zone_cfg: dict):
        """🌉 Bridge micro-signals to discrete states. Prevents quantization oscillation."""
        if DECAY_ENABLED:
            # 🐊 DECAY (2026-10-01) -- the zone's own "decay" config value, wired in for the first
            # time (see module constant docstring for the full story: defined a year ago, never
            # connected). A gentle, continuous pull of each state back toward center, at THIS zone's
            # own designed rate -- the restoring force this substrate's own comments say never
            # existed. Added to the SAME float accumulators the real signal already uses, so it goes
            # through the existing threshold-commit bridge below rather than mutating state directly.
            center = (STATE_MIN + STATE_MAX) / 2.0
            rate = zone_cfg["decay"] * DECAY_PULL_SCALE
            self.mem_acc -= (self.mem - center) * rate
            self.think_acc -= (self.think - center) * rate
            self.relay_acc -= (self.relay_strength - center) * rate
        for acc_name, state_name in [("mem_acc", "mem"), ("think_acc", "think"), ("relay_acc", "relay_strength")]:
            acc_val = getattr(self, acc_name)
            if abs(acc_val) >= ACCUM_THRESHOLD:
                delta = int(acc_val)
                setattr(self, state_name, getattr(self, state_name) + delta)
                setattr(self, acc_name, acc_val - delta)
        self.clamp_state()
        for syn in self.synapses:
            syn.update_discrete(zone_cfg)

    def receive(self, signal: float, src_id: int, delay: int):
        """📥 Integrate incoming signal. ROM-locked bricks still RECEIVE (ROM = frozen WEIGHTS, not deaf!
        a reflex must hear its call to respond). Tracks input_this_cycle = 'were we spoken to?'."""
        if not self.alive:
            return
        zone_cfg = ZONE_PARAMS[self.zone]
        mapped = zone_cfg["signal_map"].get(signal, signal)
        sign_scale = zone_cfg.get("pos_scale", 1.0) if mapped > 0 else 1.0
        # ROM bricks integrate input for FIRING decisions but don't let it overwrite their frozen state much
        scale = 0.3 if self.rom_locked else 1.0
        self.mem_acc += mapped * 0.3 * sign_scale * scale
        self.think_acc += mapped * 0.5 * sign_scale * scale
        self.relay_acc += mapped * 0.2 * sign_scale * scale
        self.input_this_cycle += abs(mapped)      # 🔇 record that we were spoken to (and how loudly)
        self.energy -= 0.05

    def predict_next(self) -> float:
        """
        🔮 LOCAL FIRST-ORDER DERIVATIVE PREDICTION
        Replaces static mem/think mix with discrete velocity tracking.
        Matches cortical temporal derivative tracking.
        """
        velocity = (self.mem - self.think) * 0.5
        noise = random.uniform(-0.3, 0.3)
        return self.mem + velocity + noise

    def update_prediction_error(self, actual: float):
        """📉 Compare prediction to reality. Drives local learning & structural growth."""
        pred = self.predict_next()
        err = abs(pred - actual)
        self.prediction_error = self.prediction_error * 0.8 + err * 0.2
        if err > 2.0:
            self.consecutive_errors += 1
            self.correct_predictions = 0
        else:
            self.consecutive_errors = 0
            self.correct_predictions += 1

# ─────────────────────────────────────────────────────────────────────────────
# SOVEREIGN CORE ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class SovereignCore:
    """
    🧠 Brainstem + Hippocampus Controller.
    Manages brick lifecycle, zone routing, sleep consolidation DAG,
    evolutionary NAS, context capacity, and persistence.
    """
    def __init__(self, init_bricks: int = INIT_BRICKS):
        self.current_time = 0
        self.generation = 1
        self.num_modules = max(1, init_bricks // 50)
        self.spacing = MODULE_SPACING
        self.module_size = MODULE_SIZE
        # GROWTH FIX (2026-09-27): "output module" was computed as (num_modules - 1) everywhere --
        # fine when num_modules never changes, but growth adding new trailing modules silently moves
        # "the output" to a brand-new, untrained module every time, cutting off the real trained
        # pathway. Fix: fix this ONCE, before growth can ever touch it, and never recompute it.
        self.output_module_id = self.num_modules - 1
        
        self.context_tokens = 0
        self.context_capacity = CONTEXT_CAPACITY
        self.context_triggered_sleep = False
        self.is_sleeping = False

        # BUG6 FIX: real pending-delivery queue so relay.back_delay/base_delay actually delay
        # signal arrival, instead of being evolved, inherited, mutated numbers with zero effect
        # (Brick.receive() never used its own `delay` argument). Entries: (deliver_at_cycle,
        # target_brick_id, signal, src_id). Flushed once per cycle in run_cycle(), before that
        # cycle's own _update_bricks()/_fire_relays() pass.
        self._pending_deliveries = []

        self.bricks: List[Brick] = []
        self.brick_lookup: Dict[int, Brick] = {}
        self._max_id_tracker = 0
        self.seed_brick_ids = set()      # ROM-locked firmware bricks (the "mama" reflex) -- never reaped/mutated
        self._init_substrate(init_bricks)
        self._plant_seed()               # 🌱 plant the hardcoded working reflex(es) AFTER the substrate exists

    def _grow_network(self):
        """
        🌱 GROWTH BY CLONING WHAT WORKED (recovered 2026-09-27 -- see GALATEA_BOOK26 diary entry).
        This is the piece that was lost: the sleep DAG's existing cull+copy replaces weak cells
        WITHIN a fixed population -- it never adds real new capacity. This is real structural
        growth, adapted from a working method found in an earlier version of this same lineage
        (Max_sovereign_core_v4_2.py's _grow_network): rank whole MODULES by fitness, take the top
        performers, and clone bricks FROM them into a brand new module -- each clone inherits its
        donor's state (mem/think/relay_strength) AND its donor's evolved relay traits
        (split_threshold/split_ratio/back_delay), with small gaussian variation, not exact
        duplication. "Growth came from cloning bricks that worked" -- his own words for it.

        2026-10-02 additions (ported from G-EvoNAS, see GROWTH_CROSSOVER_ENABLED/GROWTH_SIZE_AWARE
        above): module ranking can use fitness-PER-BRICK instead of raw average fitness (size-aware),
        and a clone can be built by crossing TWO parent modules' traits instead of mutating one donor
        (real crossover, not just mutation) -- both toggleable for direct A/B against the original.
        """
        living = [b for b in self.bricks if b.alive]
        if not living:
            return
        mod_fitness = defaultdict(list)
        mod_bricks = defaultdict(list)
        for b in living:
            mod_fitness[b.module_id].append(b.fitness)
            mod_bricks[b.module_id].append(b)
        avg_by_mod = {m: sum(f) / max(len(f), 1) for m, f in mod_fitness.items()}
        if GROWTH_SIZE_AWARE:
            # fitness PER BRICK: a small module pulling its weight beats an equally-fit large one --
            # cheap proxy for G-EvoNAS's accuracy-vs-size Pareto objective, not a full Pareto front.
            rank_key = {m: avg_by_mod[m] / max(len(mod_bricks[m]), 1) for m in avg_by_mod}
        else:
            rank_key = avg_by_mod
        top_mods = sorted(rank_key.items(), key=lambda x: x[1], reverse=True)[:2]
        top_mod_ids = [m for m, _ in top_mods]

        grid = 4
        new_bricks = 0
        n_crossed = 0
        for mod_id, fit in top_mods:
            src_bricks = mod_bricks[mod_id]
            other_mod_ids = [m for m in top_mod_ids if m != mod_id]
            other_bricks = mod_bricks[other_mod_ids[0]] if other_mod_ids else []
            new_mod_id = self.num_modules
            cx = (new_mod_id % grid) * self.spacing
            cy = (new_mod_id // grid) * self.spacing
            n_clone = max(1, len(src_bricks) // 3)
            for _ in range(n_clone):
                pos = (cx + random.uniform(-self.module_size, self.module_size),
                       cy + random.uniform(-self.module_size, self.module_size),
                       random.uniform(-self.module_size, self.module_size))
                donor = random.choice(src_bricks)
                do_cross = (GROWTH_CROSSOVER_ENABLED and other_bricks
                            and random.random() < GROWTH_CROSSOVER_RATE)
                donor2 = random.choice(other_bricks) if do_cross else None
                nb = self._create_brick(pos=pos, module_id=new_mod_id, zone=donor.zone)
                if donor2 is not None:
                    # real two-parent crossover: blend each scalar trait by a random mix factor per
                    # trait (arithmetic crossover -- the real-coded analogue of G-EvoNAS's uniform
                    # crossover over connections/operations), THEN apply the same gaussian variation
                    # as the single-donor path so a crossed clone isn't just a frozen average.
                    def _blend(a, b):
                        t = random.random()
                        return a * t + b * (1.0 - t)
                    base_mem = _blend(donor.mem, donor2.mem)
                    base_think = _blend(donor.think, donor2.think)
                    base_relay = _blend(donor.relay_strength, donor2.relay_strength)
                    n_crossed += 1
                else:
                    base_mem, base_think, base_relay = donor.mem, donor.think, donor.relay_strength
                # inherit (donor, or blended donor+donor2) STATE, mutated, not copied exactly
                nb.mem = int(max(STATE_MIN, min(STATE_MAX, base_mem + random.gauss(0, 1.0))))
                nb.think = int(max(STATE_MIN, min(STATE_MAX, base_think + random.gauss(0, 1.0))))
                nb.relay_strength = int(max(STATE_MIN, min(STATE_MAX, base_relay + random.gauss(0, 1.0))))
                nb.energy = 20.0
                nb.stability = donor.stability if donor2 is None else _blend(donor.stability, donor2.stability)
                # inherit evolved RELAY TRAITS (split_threshold/split_ratio/back_delay) -- the actual
                # point of cloning "what worked"; crossed when donor2 is present, else single-donor
                # mutated as before. A fresh PairedRelay from _create_brick starts at random init.
                if donor.relays and nb.relays:
                    donor_relay = donor.relays[0]
                    if donor2 is not None and donor2.relays:
                        donor2_relay = donor2.relays[0]
                        base_thresh = _blend(donor_relay.split_threshold, donor2_relay.split_threshold)
                        base_ratio = _blend(donor_relay.split_ratio, donor2_relay.split_ratio)
                        base_delay = donor_relay.back_delay if random.random() < 0.5 else donor2_relay.back_delay
                    else:
                        base_thresh, base_ratio, base_delay = (donor_relay.split_threshold,
                                                                 donor_relay.split_ratio,
                                                                 donor_relay.back_delay)
                    for nr in nb.relays:
                        nr.split_threshold = max(0.5, min(8.0, base_thresh + random.gauss(0, 0.2)))
                        nr.split_ratio = max(0.1, min(0.9, base_ratio + random.gauss(0, 0.03)))
                        nr.back_delay = max(1, base_delay + random.choice([-1, 0, 0, 1]))
                new_bricks += 1
            self.num_modules += 1
        if new_bricks:
            print(f"      🌱 Growing network: cloned {new_bricks} bricks from {len(top_mods)} "
                  f"high-fitness module(s) into new capacity ({n_crossed} via two-parent crossover).")

    def _next_id(self) -> int:
        self._max_id_tracker += 1
        return self._max_id_tracker

    def _init_substrate(self, count: int):
        """🏗️ Spawn initial modules and distribute bricks across spatial layout."""
        for m_id in range(self.num_modules):
            cx = (m_id % 4) * self.spacing
            cy = (m_id // 4) * self.spacing
            cz = random.uniform(0, 20)
            zone_bias = random.choice(["FAST", "SLOW", "MIRROR"])
            for _ in range(count // self.num_modules):
                pos = (cx + random.uniform(-self.module_size, self.module_size),
                       cy + random.uniform(-self.module_size, self.module_size),
                       cz + random.uniform(-self.module_size, self.module_size))
                self._create_brick(pos=pos, module_id=m_id, zone=zone_bias)

    def _plant_seed(self):
        """🌱 THE SEED ("mama" firmware): plant a few HARDCODED working call->response reflex arcs.
        NOT random. ROM-locked from birth so evolution cannot delete the boot reflex everything learns from.
        Each seed = a thin wired chain from an entry brick, forward module by module, to an output brick
        whose state is SET to emit the correct answer. The reflex WORKS at cycle 0; the rest of the
        substrate learns the other task pairs by IMITATION (sister-spreading from this working pattern).
        We plant SEED_REPEATS copies of the first task pair (one 'word', repeated a few times -- redundancy
        costs nothing and gives the pattern more sister-neighbors to spread from)."""
        SEED_REPEATS = 3
        if not self.TASK_PAIRS:
            return
        seed_call, seed_answer = self.TASK_PAIRS[0]   # the one hardcoded "word", e.g. (2,4,6)->8
        self._seed_call = tuple(seed_call)            # remember it so inject can excite the reflex
        for rep in range(SEED_REPEATS):
            chain = []
            # build one brick per module, wired forward module 0 -> last module
            prev = None
            for m_id in range(self.num_modules):
                pos = ((m_id % 4) * self.spacing, (m_id // 4) * self.spacing, 10.0)
                b = self._create_brick(pos=pos, module_id=m_id, zone="SLOW")  # SLOW = persistence zone
                b.synapses = []   # clear random synapses; this is a clean hardcoded chain
                b.relays = []
                self.seed_brick_ids.add(b.id)
                # 🔧 HAND-CRANK: seed is PLASTIC (read-write), not frozen. It injects the answer to crank
                # the flywheel, then DISENGAGES to a normal plastic cell once the pattern propagates. It is
                # PROTECTED-FROM-CULL (immune) while cranking, but its weights stay free to move with the
                # swarm. NOT rom_locked (a read-only seed = a crank that never lets go = a millstone).
                b.rom_locked = False
                b.plasticity = 1.0
                b.fitness = 1.0
                b.energy = 30.0
                b.is_seed_crank = True       # currently cranking (protected + injecting)
                b.crank_passes = 0           # how many times it has injected; disengages after a few
                if prev is not None:
                    # forward synapse prev -> b (strong, short delay): the reflex pathway
                    prev.synapses.append(Synapse(b.id, weight=ZONE_PARAMS["SLOW"]["weights"][1], delay=1))
                    prev.relays.append(PairedRelay(source_id=prev.id, targets=[b.id], base_delay=1))
                prev = b
                chain.append(b)
            # set the OUTPUT brick of this chain to emit the correct answer (the reflex's hardcoded response)
            out_b = chain[-1]
            out_b.mem = int(seed_answer)            # memory state = the answer
            out_b.mem_acc = float(seed_answer)
            out_b.think = int(seed_answer)          # think = answer too -> predict_next ~ answer
            out_b.think_acc = float(seed_answer)
            out_b.fire_threshold = 0.05             # seed output fires readily (the reflex always responds)
            out_b._seed_answer = float(seed_answer) # remember its hardcoded answer to refresh against drift
            # record what this seed answers (for clarity / future use)
        print(f" 🌱 Seed planted: {SEED_REPEATS}x reflex {seed_call}->{seed_answer} "
              f"(ROM-locked firmware, wired entry->output across {self.num_modules} modules)")

    def _create_brick(self, pos: Tuple[float, float, float], module_id: int, zone: str) -> Brick:
        """🧱 Instantiate a new brick, register in lookup, wire initial synapses."""
        bid = self._next_id()
        b = Brick(bid, pos, module_id, zone)
        self.bricks.append(b)
        self.brick_lookup[bid] = b
        # SINGLE-OUTPUT / FORWARD morphology: a brick may target bricks in its OWN module (sideways)
        # or the NEXT module (forward). It may NOT wire directly back to an earlier module (no tight loop;
        # feedback only ever returns the long way, through the network). This also finally CONNECTS
        # entry(module 0) -> ... -> output(last module) so the call can actually reach the answer.
        valid_targets = [x.id for x in self.bricks if x.id != bid and
                         (x.module_id == module_id or x.module_id == module_id + 1)]
        targets = random.sample(valid_targets, k=min(3, len(valid_targets))) if valid_targets else []
        for t in targets:
            w = random.randint(*ZONE_PARAMS[zone]["weights"])
            d = random.randint(1, 8)
            b.synapses.append(Synapse(t, w, d))
        # 🧠 give the brick a PairedRelay so the backward-split mechanism has structure to act on.
        # (Original v4.3 never instantiated relays; the split mechanism needs them to exist.)
        if targets:
            b.relays.append(PairedRelay(source_id=bid, targets=list(targets), base_delay=random.randint(1, 4)))
        return b

    def _reap_dead(self):
        """🍂 Remove bricks that exhausted energy. Fitness-floor pruning is GENTLE early (slime-mold:
        keep the network alive long enough to learn). Only reap on true energy death, or sustained
        very-low fitness AFTER the brick has had time to learn (age gate)."""
        alive = []
        for b in self.bricks:
            truly_dead = (b.energy <= 0)
            chronic_fail = (b.fitness < PRUNE_FITNESS_FLOOR * 0.5 and b.age > 80)  # age-gated, lenient
            is_seed = (b.id in self.seed_brick_ids)   # 🌱 firmware is never reaped
            if b.alive and (is_seed or (not truly_dead and not chronic_fail)):
                alive.append(b)
            else:
                b.alive = False
                self.brick_lookup.pop(b.id, None)
        self.bricks = alive

    def _autosarcophagy(self):
        """🔪 Metabolic pruning: decay low-fitness synapses, return resources."""
        for b in self.bricks:
            if b.fitness < 0.2 and b.age > 50:
                for syn in b.synapses:
                    syn.weaken()
                b.energy = max(0, b.energy - 2.0)

    # 🍼 THE TASK: a small fixed library of call -> response pairs (sequence completions).
    # The substrate hears the CALL and must produce the RESPONSE. Correct answers are REAL and KNOWN,
    # so fitness can reward TRUE correctness (whole-organism success), not self-consistency.
    # Start tiny (a few "words") so it can actually be learned by repetition -- like mama.
    # MULTI-TASK (v4.13): several +2 sequences (SAME operation, different sequences). The seed knows ONE
    # (2,4,6->8); the OTHERS must be learned by GENERALIZING the +2 operation -- a memorizer of "8" fails
    # them, only a rule-extractor wins. Values in [0,31]. This is the proof-of-concept: if it learns the
    # OPERATION here (math), the mechanism generalizes to anything.
    TASK_PAIRS = [
        ((2, 4, 6), 8),     # the seeded one
        ((5, 7, 9), 11),
        ((10, 12, 14), 16),
        ((1, 3, 5), 7),
        ((20, 22, 24), 26),
        ((11, 13, 15), 17),
    ]

    def inject_problem(self, problem_type: str, signal: float, forced_call=None):
        """📤 Present a CALL to entry bricks and store the KNOWN-CORRECT response for fitness scoring.
        problem_type is now USED: it selects which call/response pair (round-robin over the task library)."""
        self.context_tokens += 1
        # pick a task pair deterministically-ish so every pair gets practiced (repetition = learning)
        if forced_call is not None:
            call = forced_call
            correct = dict(self.TASK_PAIRS).get(tuple(forced_call), 0)
        else:
            # INTERLEAVED waking presentation: random task each cycle (not blocked) so all tasks are
            # rehearsed frequently -- reduces recency-dominated overwriting (catastrophic forgetting).
            call, correct = random.choice(self.TASK_PAIRS)
        self.current_call = call
        self.current_target = float(correct)

        # 🌱 SEED REFLEX: if the current call matches the seed's call, directly excite the seed chain so
        # the firmware RELIABLY fires its response (a reflex always responds to its own call -- not by luck).
        if hasattr(self, "_seed_call") and tuple(call) == self._seed_call:
            for b in self.bricks:
                if b.id in self.seed_brick_ids:
                    if getattr(b, "is_seed_crank", False):
                        b.input_this_cycle += 5.0      # CRANK: inject the answer to spin the flywheel
                        b.crank_passes = getattr(b, "crank_passes", 0) + 1
                        # DISENGAGE only when the ENGINE HAS CAUGHT: enough NON-SEED cells reliably produce
                        # the answer (swarm self-sustaining). Listen for the catch, THEN let go -- not a timer.
                        # (a minimum pass count too, so it cranks at least a little before checking.)
                        if b.crank_passes >= SEED_CRANK_PASSES and self._engine_caught():
                            b.is_seed_crank = False    # crank lets go; weights now free to move with swarm
                            # RATCHET FIX (2026-09-27, independently verified against this exact file):
                            # every zone's signal_map is entirely positive-valued -- no inhibitory signal
                            # exists anywhere in this substrate. A brick with no restoring force pinning
                            # it integrates a strictly one-directional stream and monotonically ratchets
                            # to STATE_MAX. The seed firmware is the population's ground-truth teacher;
                            # once it drifts, whole_correct/my_credit/prototype EMAs all smear toward a
                            # wrong target and the corruption spreads through the whole recognizer pool.
                            # The crank letting go was never meant to mean "now forget the answer" --
                            # ROM-lock it: _update_bricks already pins _seed_answer for rom_locked
                            # bricks, so this reuses existing machinery rather than adding a new one.
                            b.rom_locked = True
                    # (after disengage: no forced injection; it learns like any other cell)
        entry_bricks = [b for b in self.bricks if b.alive and b.module_id == 0]
        targets = random.sample(entry_bricks, k=min(8, len(entry_bricks)))
        for b in targets:
            b.last_call = call
            b.mem_acc += float(call[-1])
            b.think_acc += float(call[-2])
            # BUG2 FIX: this loop used to call b.receive(float(elem), ...) for every element with
            # no positional information at all -- receive() only accumulates additively, and
            # addition is commutative, so any two calls sharing the same multiset of values (in
            # any order) injected IDENTICAL signal here. Only call[-1]/call[-2] (above) carried any
            # position. For a 16-element context, 14 of 16 positions collapsed into one order-blind
            # sum -- the direct, mechanistic cause of the 99.8% response-collision rate measured by
            # sc_collision_probe.py. Fix: add a small position-dependent term so even a repeated or
            # zero-valued element contributes differently depending on where it sits in the call --
            # purely additive (not multiplicative), so it still works when elem==0.
            for i, elem in enumerate(call):
                positional_signal = float(elem)
                if BUG2_POSITION_AWARE_ENCODING:
                    positional_signal += POSITION_WEIGHT_SCALE * i
                b.receive(positional_signal, src_id=-1, delay=0)

        # 🧠 RECOGNITION: every cell computes how well THIS call matches its stored prototype.
        call_vec = [float(x) for x in call]
        for b in self.bricks:
            if not b.alive: continue
            if b.prototype is None:
                b.match_weight = 0.0
                continue
            # Euclidean distance between the current call and the cell's learned prototype pattern
            dist = math.sqrt(sum((a - p) ** 2 for a, p in zip(call_vec, b.prototype)))
            if RECOGNITION_MODE == "graded":
                b.match_weight = math.exp(-(dist * dist) / (2.0 * RBF_SIGMA * RBF_SIGMA))  # RBF kernel
            else:
                b.match_weight = dist   # store raw distance; nearest-mode picks min in readout

    def _read_response(self):
        """🗣️ WINNER-WEIGHTED readout (v4.6, GRPO-shaped). The answer is NOT a flat mean of all output
        bricks (which lets random bricks drown the seed). Each brick votes with a WEIGHT = its stability *
        fitness (committed, proven cells speak louder), and seed/ROM bricks get a strong baseline weight
        (the firmware is trusted). This is the 'high-advantage outputs dominate' rule: consensus of the
        cells that are actually competent, not the average of the noise."""
        # 🔇 only bricks that FIRED this cycle get a vote (spoke when spoken to). Silent cells don't dilute.
        out_bricks = [b for b in self.bricks if b.alive and b.module_id == (self.output_module_id)
                      and b.fired_this_cycle]
        if not out_bricks:
            return None                                         # nobody was spoken to -> no answer this cycle
        # 🗳️➡️➕ READOUT_MODE="linear": the unconstrained-combination alternative (see the global
        # flag's own comment above for the full "why"). Completely separate code path from "vote"
        # below -- "vote" mode's behavior is byte-for-byte unchanged when this flag is at its
        # default. No normalization by sum(weight), no positivity constraint -- readout_weight is
        # a real evolvable trait (mutated in _mutate_and_select(), inherited on cloning), so this
        # mode trains the SAME way everything else in this engine does: selection on a trait that
        # actually varies, not a bolted-on learning rule layered on top of a running system.
        if READOUT_MODE == "linear":
            resp = 0.0
            for b in out_bricks:
                w = b.readout_weight
                if b.id in self.seed_brick_ids:
                    w = w * 50.0 if w != 0.0 else 50.0   # firmware still speaks loudest even here
                val = b.proto_answer if (b.proto_answer is not None and b.prototype is not None) else b.predict_next()
                resp += w * val
            return resp
        # 🧠 RECOGNITION READOUT: cells vote weighted by how well they RECOGNIZE the current call.
        # graded = RBF match_weight (closer prototype = louder); nearest = only closest-prototype cell votes.
        recognizers = [b for b in out_bricks if b.prototype is not None]
        if RECOGNITION_MODE == "nearest" and recognizers:
            # winner-take-all: the single closest prototype (smallest distance) answers
            winner = min(recognizers, key=lambda b: b.match_weight)   # match_weight holds raw distance here
            return float(winner.proto_answer) if winner.proto_answer is not None else winner.predict_next()
        # seed/firmware voices DOMINATE the readout (heavy weight) so a few correct cells beat the crowd.
        num = 0.0; den = 0.0
        for b in out_bricks:
            w = (b.stability + 0.1) * (b.fitness + 0.1)
            if b.id in self.seed_brick_ids:
                w *= 50.0          # firmware speaks ~50x louder (the trusted reflex dominates)
            # 🧠 recognition gate (graded): a cell that recognizes THIS call votes louder; non-recognizers fade
            if RECOGNITION_MODE == "graded" and b.prototype is not None:
                w *= (0.05 + b.match_weight)     # match_weight in [0,1]; small floor so unrecognized still whisper
            # a recognizing cell emits ITS prototype's answer (what it learned to say to this pattern)
            val = b.proto_answer if (b.proto_answer is not None and b.prototype is not None) else b.predict_next()
            num += w * val; den += w
        return (num / den) if den > 0 else None

    def _update_bricks(self):
        """⚙️ Core cycle: SPEAK-ONLY-WHEN-SPOKEN-TO firing gate, then commit, error, zone routing."""
        tgt = getattr(self, "current_target", None)
        for b in self.bricks:
            if not b.alive: continue
            # 🔇 FIRING GATE: fire only if spoken to enough (input >= threshold) and not refractory.
            if b.refractory > 0:
                b.refractory -= 1
                b.fired_this_cycle = False
            else:
                b.fired_this_cycle = (b.input_this_cycle >= b.fire_threshold)
                if b.fired_this_cycle:
                    b.refractory = 1                 # brief silence after firing (don't speak again yet)
                    b.energy -= 0.1                  # firing costs energy (organic frugality)
            b.input_this_cycle = 0.0                 # reset: a new cycle, must be spoken to again

            # 🔧 CRANK REFRESH: while a seed cell is still CRANKING (plastic but injecting), keep its answer
            # pinned so it reliably emits the response that spins the flywheel. This was previously gated on
            # rom_locked -- making the seed plastic accidentally UNPLUGGED it (seed went mute -> TaskCorrect 0
            # from the start). Now the crank works in the plastic state, and only RELEASES on disengage.
            if getattr(b, "is_seed_crank", False) and hasattr(b, "_seed_answer"):
                b.mem = int(b._seed_answer); b.think = int(b._seed_answer)
            elif getattr(b, "teach_freeze", 0) > 0 and hasattr(b, "_teach_answer"):
                b.mem = int(b._teach_answer); b.think = int(b._teach_answer)   # steady teacher

            if b.rom_locked:
                b.age += 1
                if hasattr(b, "_seed_answer"):
                    b.mem = int(b._seed_answer); b.think = int(b._seed_answer)
                continue                              # ROM weights frozen, but it DID get its firing decision
            zone_cfg = ZONE_PARAMS[b.zone]
            # BUG5 FIX: a "frozen" teaching brick had its mem/think pinned to _teach_answer above,
            # but commit_accumulators()/update_prediction_error() ran unconditionally right after
            # and could immediately change b.mem again the same cycle -- so the "frozen" snapshot
            # could still drift, and the drifted value became the new _teach_answer at the bottom
            # of this loop. A genuinely frozen teacher holds a stable target for its whole window.
            is_teaching = BUG5_TRUE_FROZEN_TEACHER and getattr(b, "teach_freeze", 0) > 0
            if not is_teaching:
                b.commit_accumulators(zone_cfg)
                b.update_prediction_error(tgt if tgt is not None else b.mem)
            b.age += 1
            b.energy = min(30.0, b.energy + 0.25)

            # 🔒 CONSOLIDATE DISCOVERED-GOOD (Fix #1, anti-drift): a non-seed cell that stays reliably
            # correct on the TASK gets its plasticity REDUCED (harder to drift), and if it sustains high
            # correctness long enough, it ROM-LOCKS (pinned permanently). This protects DISCOVERED-good the
            # way the seed (born-good) is already protected. Without this, exploration erases what was learned.
            # 🛡️ SUCCESS -> IMMUNITY (not freezing). A sustained-correct cell becomes PROTECTED FROM
            # CULLING but stays READ-WRITE (plastic) -- it keeps turning with the flywheel, recording
            # ongoing learning. Immunity != frozen. (No ROM-lock on live learning cells.)
            if b.recent_task_score > 0.85 and IMMUNE_TEACH_ENABLED:
                b.consolidation_streak = getattr(b, "consolidation_streak", 0) + 1
                if b.consolidation_streak >= 40 and not getattr(b, "cull_immune", False):
                    b.cull_immune = True            # earned immunity: sleep won't eat it (stays read-write)
                    # 🔧 TRANSIENT FREEZE: become a STABLE clean TEACHER for a window, so neighbors imitate a
                    # steady target (restores geometric propagation) -- then RETURN to plastic (no millstone).
                    b.teach_freeze = TEACH_FREEZE_WINDOW
                    print(f" 🛡️ IMMUNE+TEACH (stable teacher {TEACH_FREEZE_WINDOW}c, then plastic): Brick {b.id} zone={b.zone} score={b.recent_task_score:.2f}")
            else:
                # BUG8 FIX: the old floor (max(0, ...)) made the `<= -60` check below unreachable
                # -- immunity was permanent once granted. Floor only applies when immunity isn't
                # being tracked for revocation (keeps a non-immune brick's streak from drifting
                # arbitrarily negative for no reason); once immune, let it go negative so sustained
                # poor performance can actually revoke protection.
                #
                # ⚠️ CORRECTION, same night, found via the bit-level rerun: `cull_immune=True` is
                # granted by FOUR different code paths, not just IMMUNE+TEACH promotion here --
                # three others (freshly-resurrected seedlings, probation-discounted clones, dead-
                # capacity replacement clones) are the ALREADY-PROVEN, already-A/B-tested
                # PROBATION_CYCLES mechanism (see its own module-level comment: "425=harm, 850=good,
                # 1700=no better... never shave it down"), with its OWN separate, correct expiry in
                # _expire_probation() keyed on a real cycle deadline, not a recent_task_score streak.
                # Applying THIS revocation logic to those bricks too was stripping probation
                # protection from brand-new, not-yet-adapted clones far too early (score<0.40 is
                # near-guaranteed for a brick that's had no time to specialize yet) -- confirmed via
                # the bit-level task's much higher resurrection/growth churn: 179 "revocations"
                # fired against only 1 real IMMUNE+TEACH promotion the entire run. Scope this fix to
                # IMMUNE+TEACH-granted immunity only; leave probationary bricks to their own
                # mechanism entirely.
                is_probationary = getattr(b, "probation", False)
                prev_streak = getattr(b, "consolidation_streak", 0)
                if BUG8_IMMUNITY_REVOCABLE and getattr(b, "cull_immune", False) and not is_probationary:
                    b.consolidation_streak = prev_streak - 1
                else:
                    b.consolidation_streak = max(0, prev_streak - 1)
                if (not is_probationary and getattr(b, "cull_immune", False)
                        and b.recent_task_score < 0.40 and b.consolidation_streak <= -60):
                    b.cull_immune = False
                    print(f" 🔓 IMMUNITY REVOKED: Brick {b.id} zone={b.zone} score={b.recent_task_score:.2f} (sustained poor performance)")
            # tick down the teaching-freeze window; while frozen, hold weights stable (clean teacher)
            if getattr(b, "teach_freeze", 0) > 0:
                b.teach_freeze -= 1
                b.plasticity = 0.05               # stable target while teaching
                b._teach_answer = b.mem           # hold the answer it's teaching
            elif getattr(b, "cull_immune", False):
                b.plasticity = max(0.4, b.plasticity)   # released back to plastic (not a millstone)

    def _apply_lateral_inhibition(self):
        """🦔 A brick that fired this cycle suppresses its same-module neighbors' ability to also
        fire soon -- no prototype comparison, no distance math, just "I spoke, so my neighbors stay
        quiet a little longer." Runs after firing decisions are made (_update_bricks), so it only
        affects FUTURE cycles' competitiveness, never undoes this cycle's already-resolved outcome.
        The only tunable number is each brick's own evolved inhibition_strength -- nothing here is
        hand-picked."""
        if not LATERAL_INHIBITION_ENABLED:
            return
        by_module = defaultdict(list)
        for b in self.bricks:
            if b.alive:
                by_module[b.module_id].append(b)
        for b in self.bricks:
            if not b.alive or not b.fired_this_cycle or b.inhibition_strength <= 0:
                continue
            for s in by_module[b.module_id]:
                if s.id == b.id or s.fired_this_cycle:
                    continue
                s.refractory += b.inhibition_strength

    def _fire_relays(self):
        """📡 Paired relay routing, phase-gated, delay-aware, WITH the SISTER-CELL SPLIT (v4.5).
        🧬 SISTER-SPLIT (the unified relay-split mechanism -- stability + imitation + clean boomerang):
           NORMAL: signal moves FORWARD, one direction, to the relay's targets. Always.
           RELIEF VALVE: ONLY when the signal is too big (source brick's prediction_error exceeds this
           relay's EVOLVABLE split_threshold) does it SPLIT:
             - the remainder continues FORWARD (weakened) to targets, as normal;
             - the EXCESS (split_ratio) is redirected -- with delay -- to a SISTER cell: a DIFFERENT brick
               in the SAME module/array as the source, NEVER the source itself and NEVER its direct feeders.
           This single act does three jobs at once, which are one job:
             1. STABILITY  -- the dangerously-big signal is bled off / dispersed before it can compound.
             2. IMITATION  -- the sister processes the redirected signal SECONDHAND -> the pattern spreads
                              to a neighbor (an array of A-cells; the signal returns to a DIFFERENT A).
             3. CLEAN      -- sister (not source), forward (not back): no tight loop ever forms; single-
                              output morphology preserved; feedback only ever returns the long way around.
           ★ This CORRECTS v4.4, which wrongly sent the split BACK to the source/feeders (the tight-loop
             echo that explodes). Sister, not source, is the whole difference between explode and clean."""
        for b in self.bricks:
            if not b.alive or b.relay_strength < 10: continue
            # BUG1 FIX: relay transmission used to be gated only on alive/relay_strength/phase --
            # never on whether the source brick actually fired in response to the current input,
            # completely decoupled from the engine's own "SPEAK-ONLY-WHEN-SPOKEN-TO" firing gate
            # (_update_bricks sets fired_this_cycle; _read_response already respects it, this
            # function never did). A relay could keep transmitting every cycle off persistent
            # internal state alone, regardless of whether the current input caused any firing --
            # a real candidate cause of attractor clustering independent of IMMUNE+TEACH.
            if BUG1_RELAY_REQUIRES_FIRING and not b.fired_this_cycle:
                continue
            for relay in b.relays:
                relay.tick()
                brick_phase = (self.current_time * 0.1) % (2 * math.pi)
                phase_diff = abs((relay.phase - brick_phase) % (2 * math.pi))
                if not (phase_diff < 0.5 or phase_diff > (2 * math.pi - 0.5)):
                    relay.suppressed = True
                    continue
                relay.usage_count += 1
                relay.suppressed = False

                # decide whether to SPLIT, based on the source brick's error vs this relay's evolvable threshold
                do_split = (b.prediction_error > relay.split_threshold)
                # MOSS/CANCER FIX: a real, substantial error occurred (2.0 is comfortably inside this
                # relay's own possible init range of 1.5-4.0, i.e. a well-calibrated relay would often
                # have caught it) but THIS relay's threshold was too high to act -- record the miss so
                # it can be penalized below, same as a split that didn't help already is.
                if not do_split and b.prediction_error > 2.0:
                    relay.missed_split_count += 1
                fwd_signal = b.relay_strength * 0.1
                if do_split:
                    relay.split_count += 1
                    relay.split_this_cycle = 1
                    sister_amount = fwd_signal * relay.split_ratio        # excess bled off to a SISTER
                    fwd_signal = fwd_signal * (1.0 - relay.split_ratio)   # remainder continues forward (weakened)
                    # find SISTER cells: same module as source, but NOT the source and NOT its direct feeders.
                    feeders = {src.id for src in self.bricks
                               if any(sy.target_id == b.id for sy in src.synapses)}
                    sisters = [x for x in self.bricks
                               if x.alive and x.module_id == b.module_id
                               and x.id != b.id and x.id not in feeders]
                    if sisters:
                        # 🐺🤝 WOLFPACK SISTER-MATCH: prefer sisters whose prototype most resembles
                        # the source's own pattern ("like-to-like", not random) -- see module const
                        # docstring. Falls back to the original random pick when there's nothing to
                        # content-match against yet, so early/proto-less bricks are unaffected.
                        chosen = None
                        if WOLFPACK_SISTER_MATCH and b.prototype is not None:
                            proto_sisters = [s for s in sisters if s.prototype is not None]
                            if proto_sisters:
                                proto_sisters.sort(key=lambda s: math.sqrt(
                                    sum((p - q) ** 2 for p, q in zip(b.prototype, s.prototype))))
                                chosen = proto_sisters[:min(2, len(proto_sisters))]
                        if chosen is None:
                            chosen = random.sample(sisters, k=min(2, len(sisters)))

                        # 🐺🚫 WOLFPACK REPULSION (2026-10-17, Jonathan's own correction to the
                        # 2026-10-01 "like-to-like" Wolfpack, which never worked): the original
                        # like-to-like version had to SEARCH the local sister pool for the closest
                        # prototype match -- real work, every split, every cycle. The reverse is
                        # cheaper and, per Jonathan, was the version that actually worked before:
                        # no search needed at all. Walk the SAME already-computed local sister pool
                        # (same module, never source, never a direct feeder -- already free). No
                        # attraction step is added here on purpose -- pulling similar prototypes
                        # together is NOT a new force this needs; it's the side effect of repulsion
                        # alone (push away everything unlike a region, and whatever's left near it
                        # has to be the similar stuff, by elimination), same logic as disk
                        # defragmentation: no single local swap needs to know the final layout. The
                        # existing EMA prototype-learning (PROTO_LEARN_RATE, in _evaluate_fitness)
                        # already does the actual merging once repulsion clears the confusion out of
                        # the way, and the existing sleep-consolidation cull already removes whatever
                        # brick ends up with nothing distinct left to earn fitness with -- no new
                        # "deletion" mechanism needed, both pieces already exist and are proven.
                        #
                        # Trigger condition, my own judgment call where Jonathan's memory of the
                        # exact rule was genuinely uncertain ("open to suggestions"): two prototypes
                        # are only pushed apart when they are CLOSE in representation space (within
                        # WOLFPACK_REPULSION_THRESHOLD -- genuinely at risk of being confused) AND
                        # their learned answers DISAGREE (different proto_answer). This targets the
                        # exact, already-measured failure mode directly: sc_collision_probe.py found
                        # 850 distinct bit-level contexts collapsing onto only 6 output values, with
                        # most of those buckets mixing BOTH possible targets together -- i.e. close
                        # prototypes that disagree on the answer. Two prototypes that are close AND
                        # AGREE are left alone; that's correct convergence, not confusion, and
                        # repelling it would actively undo real learning.
                        if WOLFPACK_REPULSION_ENABLED and b.prototype is not None and b.proto_answer is not None:
                            # 🔍 TEMPORARY DIAGNOSTIC COUNTERS (2026-10-17) -- checking whether this
                            # mechanism is engaging at all before trusting a negative result. Remove
                            # once the question is answered either way.
                            if not hasattr(self, "_repulsion_stats"):
                                self._repulsion_stats = {"gate_entered": 0, "no_sister_proto": 0,
                                                          "agree_skip": 0, "too_far_skip": 0, "fired": 0}
                            self._repulsion_stats["gate_entered"] += 1
                            for s in sisters:
                                if s.prototype is None or s.proto_answer is None:
                                    self._repulsion_stats["no_sister_proto"] += 1
                                    continue
                                if abs(s.proto_answer - b.proto_answer) < WOLFPACK_REPULSION_ANSWER_MARGIN:
                                    self._repulsion_stats["agree_skip"] += 1
                                    continue  # they agree -- not confusion, leave it alone
                                dist = math.sqrt(sum((p - q) ** 2 for p, q in zip(b.prototype, s.prototype)))
                                if dist < WOLFPACK_REPULSION_THRESHOLD:
                                    self._repulsion_stats["fired"] += 1
                                    for i in range(len(s.prototype)):
                                        push = WOLFPACK_REPULSION_RATE * (s.prototype[i] - b.prototype[i])
                                        s.prototype[i] = max(STATE_MIN, min(STATE_MAX, s.prototype[i] + push))
                                else:
                                    self._repulsion_stats["too_far_skip"] += 1
                        for sis in chosen:
                            # forward-going imitation signal to the sister, delayed (temporal spread).
                            # the sister learns the pattern secondhand; the big signal is dispersed, not looped.
                            self._deliver(sis, sister_amount, src_id=b.id, delay=relay.back_delay)

                # forward distribution (normal), with whatever remains after a split
                for t_id in relay.targets:
                    target = self.brick_lookup.get(t_id)
                    if target and target.alive:
                        self._deliver(target, fwd_signal, src_id=b.id, delay=relay.base_delay)

    def _deliver(self, target, signal: float, src_id: int, delay: int):
        """BUG6 FIX: Brick.receive() never used its own `delay` argument -- every signal applied
        synchronously regardless of the evolved back_delay/base_delay relay traits, which had zero
        real effect on timing. Real delayed delivery: delay<=0 (or the fix disabled) applies
        immediately as before; delay>0 enqueues onto self._pending_deliveries, flushed once per
        cycle in run_cycle() when delivery_cycle has arrived."""
        if not BUG6_REAL_SIGNAL_DELAY or delay <= 0:
            target.receive(signal, src_id=src_id, delay=delay)
            return
        self._pending_deliveries.append((self.current_time + delay, target.id, signal, src_id))

    def _flush_pending_deliveries(self):
        """Apply any queued relay signals whose delay has elapsed, before this cycle's own
        update/fire pass runs -- so a delayed signal actually arrives on a LATER cycle, not the
        same one it was sent on."""
        if not self._pending_deliveries:
            return
        still_pending = []
        for deliver_at, target_id, signal, src_id in self._pending_deliveries:
            if deliver_at <= self.current_time:
                target = self.brick_lookup.get(target_id)
                if target and target.alive:
                    target.receive(signal, src_id=src_id, delay=0)
            else:
                still_pending.append((deliver_at, target_id, signal, src_id))
        self._pending_deliveries = still_pending

    def _evaluate_fitness(self):
        """⚖️ WHOLE-ORGANISM CORRECTNESS drives selection (the anti-cancer / anti-moss leash).
        🔒 GOVERNANCE PRINCIPLE: reward flows from the SUBSTRATE's actual task success DOWN to the parts.
           A brick/relay thrives ONLY when the WHOLE answered the call correctly. This prevents the cancer
           failure (a part gaming local self-consistency while the whole learns nothing). Self-consistency
           (stability/energy) is kept as a SMALL secondary 'stay alive' term; TASK CORRECTNESS DOMINATES.

        Step 1: read the substrate's collective response to the current call; score it against the KNOWN target.
        Step 2: distribute that whole-organism correctness as the primary fitness signal to the parts.
        Step 3: reward relays whose SPLIT actually preceded improved correctness (so split-traits evolve
                toward learning, not toward calm)."""
        target = getattr(self, "current_target", None)
        response = self._read_response()
        # whole-organism correctness in [0,1]: 1.0 = exact, decaying with absolute error
        if target is not None and response is not None:
            err = abs(response - target)
            # normalized over the state range: exact=1.0, off by ~8 (a quarter of the 0-31 band)=0.0
            whole_correct = max(0.0, 1.0 - err / 8.0)
        else:
            whole_correct = 0.5
        # track improvement (did the whole get MORE correct than last trial?) for split-credit
        # BUG4 FIX: this used to compare against a single GLOBAL previous score, even though
        # consecutive cycles under interleaved training can present completely different, unrelated
        # task pairs -- a relay could earn split_helped credit merely because a DIFFERENT, easier
        # task happened to score higher right after it split, not because its own split caused
        # anything. Track the previous score PER TASK (keyed by the call) so "improved" means
        # "this same task scored better than the last time it was presented," not "some task did."
        if BUG4_PER_TASK_IMPROVEMENT_TRACKING and self.current_call is not None:
            if not hasattr(self, "_prev_whole_correct_by_task"):
                self._prev_whole_correct_by_task = {}
            task_key = tuple(self.current_call)
            prev = self._prev_whole_correct_by_task.get(task_key, 0.5)
            improved = whole_correct > prev
            self._prev_whole_correct_by_task[task_key] = whole_correct
        else:
            prev = getattr(self, "_prev_whole_correct", 0.5)
            improved = whole_correct > prev
            self._prev_whole_correct = whole_correct
        # windowed average so telemetry reflects the TRUE rate, not one unlucky instantaneous sample
        if not hasattr(self, "_wc_window"): self._wc_window = []
        self._wc_window.append(whole_correct)
        if len(self._wc_window) > 100: self._wc_window.pop(0)
        self._wc_avg = sum(self._wc_window) / len(self._wc_window)

        # 🏝️ GROUP-RELATIVE ADVANTAGE (GRPO): compute each output brick's OWN correctness vs target,
        # then the GROUP MEAN, so each cell can be rewarded for being ABOVE its sisters' average.
        out_bricks = [b for b in self.bricks if b.alive and b.module_id == (self.output_module_id)]
        per_correct = {}
        if target is not None and out_bricks:
            for ob in out_bricks:
                e = abs(ob.predict_next() - target)
                per_correct[ob.id] = max(0.0, 1.0 - e / 8.0)
            group_mean = sum(per_correct.values()) / len(per_correct)
        else:
            group_mean = 0.5

        # 🔗 CHAIN CREDIT (Fix #2): propagate credit BACKWARD from correct output cells through their
        # feeders, so every cell ON A WINNING PATH gets its OWN credit (not the group blend). The reward
        # for the whole correct answer reaches back and reinforces the cells that produced it -- the
        # foundation is paid rent by what's built on it. This gives each cell an INDIVIDUAL score, which is
        # exactly what consolidation (#1) needs to know WHICH cells to pin.
        chain_credit = {}
        # seed correct output cells with their own correctness; start the backward flow from them.
        frontier = {}
        for ob in out_bricks:
            c = per_correct.get(ob.id, 0.0)
            chain_credit[ob.id] = c
            if c > 0.6:                      # only CORRECT outputs propagate credit backward
                frontier[ob.id] = c
        # precompute feeder map ONCE: target_id -> list of source brick ids that feed it
        feeders_of = {}
        for src in self.bricks:
            if not src.alive: continue
            for sy in src.synapses:
                feeders_of.setdefault(sy.target_id, []).append(src.id)
        # walk backward through feeders, decaying credit each hop (closer to the answer = more credit)
        for _hop in range(self.num_modules):
            next_frontier = {}
            for bid, cred in frontier.items():
                for src_id in feeders_of.get(bid, ()):
                    passed = cred * 0.7
                    if passed > chain_credit.get(src_id, 0.0):
                        chain_credit[src_id] = passed
                        if passed > 0.3:
                            next_frontier[src_id] = passed
            frontier = next_frontier
            if not frontier: break

        for b in self.bricks:
            if not b.alive: continue
            # --- PRIMARY: whole-organism correctness (dominant term) ---
            accountability = 1.0 if b.module_id == (self.output_module_id) else 0.4
            task_term = whole_correct * accountability
            # --- GRPO ADVANTAGE: output bricks also rewarded for beating the GROUP MEAN (the island) ---
            if b.id in per_correct:
                advantage = per_correct[b.id] - group_mean        # >0 = better than sisters -> reinforce
                task_term += 0.5 * advantage                      # above-average wins, below-average suppressed

            # --- SECONDARY: stay-alive floor. Bigger early on so the network SURVIVES the learning phase
            #     (slime-mold principle: stay alive long enough to find the path). As correctness rises,
            #     the task term naturally dominates; while correctness is 0, this floor keeps bricks alive. ---
            alive_term = 0.35 * (b.stability * 0.5 + min(b.energy, 30) / 60.0)

            # 🔗 add this cell's OWN chain credit (it's on a winning path) to its task term
            my_credit = chain_credit.get(b.id, 0.0)
            task_term += 0.6 * my_credit       # winning-path cells reinforced INDIVIDUALLY

            # 🧠 PROTOTYPE LEARNING: a cell that is on a winning path for THIS call learns to RECOGNIZE it --
            # move its prototype (EMA) toward the current call, and record the answer it should emit. This is
            # how averaging BECOMES recognition: each cell specializes to the pattern it answers correctly.
            if my_credit > 0.5 and self.current_call is not None:
                cv = [float(x) for x in self.current_call]
                if b.prototype is None:
                    b.prototype = cv[:]
                    b.proto_answer = float(self.current_target) if self.current_target is not None else b.mem
                else:
                    b.prototype = [(1 - PROTO_LEARN_RATE) * p + PROTO_LEARN_RATE * c
                                   for p, c in zip(b.prototype, cv)]
                    if self.current_target is not None:
                        b.proto_answer = (1 - PROTO_LEARN_RATE) * b.proto_answer + PROTO_LEARN_RATE * float(self.current_target)

            # correctness dominates WHEN PRESENT, but the stay-alive floor prevents early mass-death.
            target_fitness = 0.65 * task_term + alive_term
            b.fitness = max(0.05, min(1.0, b.fitness * 0.92 + target_fitness * 0.08))
            # 🔗 recent_task_score blends chain-credit AND RECOGNITION CORRECTNESS. A cell that recognizes
            # the current call (prototype matches) and emits the RIGHT answer is doing its job -> it must
            # become a WINNER (copyable/immune). Without this, recognizing cells never crossed WORKING_FLOOR
            # -> "copied 0 winners" every sleep (the bug that starved both the conservation-law swap and the
            # garden's salience-ordered consolidation).
            recognizes_now = False
            recog_reward = 0.0
            if (getattr(b, "prototype", None) is not None and b.proto_answer is not None
                    and self.current_call is not None and self.current_target is not None):
                cv = [float(x) for x in self.current_call]
                dist = sum((p-c)**2 for p,c in zip(b.prototype, cv)) ** 0.5
                if dist < RBF_SIGMA:                      # this cell RECOGNIZES the current call
                    recognizes_now = True
                    ans_err = abs(b.proto_answer - float(self.current_target))
                    # BUG3 FIX: these margins directly feed recent_task_score, which is the ONLY
                    # gate for IMMUNE+TEACH promotion -- a brick that's meaningfully wrong (e.g.
                    # off by 1 of only 2 possible binary targets 0/31) used to still earn full or
                    # half "recognized correctly" credit toward becoming a protected, broadcast
                    # teacher. Tightened specifically for teacher-eligibility; the separate
                    # whole_correct graded-closeness term used for ordinary evolutionary fitness
                    # selection is untouched -- partial-credit fitness shaping is a different,
                    # more defensible use than "is this cell trustworthy enough to teach others."
                    full_margin = TEACHER_REWARD_FULL_MARGIN if BUG3_STRICT_TEACHER_REWARD else 1.5
                    half_margin = TEACHER_REWARD_HALF_MARGIN if BUG3_STRICT_TEACHER_REWARD else 3.0
                    if ans_err < full_margin:
                        recog_reward = 1.0
                    elif ans_err < half_margin:
                        recog_reward = 0.5
            if recognizes_now:
                # this cell was ASKED -> update strongly toward its performance (reward or miss)
                b.recent_task_score = b.recent_task_score * 0.7 + max(my_credit, recog_reward) * 0.3
            else:
                # a DIFFERENT task was asked -> don't punish this specialist; hold its score (tiny pull to mean)
                b.recent_task_score = b.recent_task_score * 0.99 + max(my_credit, 0.5) * 0.01

        # --- Step 3: relay split-credit. If a relay split AND the whole improved, credit its traits. ---
        for b in self.bricks:
            if not b.alive: continue
            for relay in b.relays:
                if relay.split_this_cycle and improved:
                    relay.split_helped += 1
                    relay.fitness = min(1.0, relay.fitness + 0.02)   # its split traits helped -> reward
                elif relay.split_this_cycle and not improved:
                    relay.fitness = max(0.0, relay.fitness - 0.01)   # split but no help -> mild penalty
                relay.split_this_cycle = 0  # clear -- credit for THIS cycle's action has been paid
                # MOSS/CANCER FIX: penalize INACTION when it was warranted, not just unhelpful action.
                # Slightly steeper than the "tried and it didn't help" penalty -- never trying at all
                # when the signal clearly called for it is the worse strategy, not the safer one.
                if relay.missed_split_count > 0:
                    relay.fitness = max(0.0, relay.fitness - 0.015 * relay.missed_split_count)
                    relay.missed_split_count = 0  # reset -- this window's misses have been paid for

    def _mutate_and_select(self):
        """🧬 Evolutionary NAS: mutate high-error bricks, prune low-fitness, drift zones."""
        for b in self.bricks:
            if not b.alive or b.rom_locked: continue
            zone_cfg = ZONE_PARAMS[b.zone]
            mut_rate = zone_cfg["mut"] * (b.prediction_error / 10.0)
            if random.random() < mut_rate:
                b.mem_acc += random.uniform(-VARIATION_MAGNITUDE, VARIATION_MAGNITUDE)
                b.think_acc += random.uniform(-VARIATION_MAGNITUDE, VARIATION_MAGNITUDE)
                for syn in b.synapses:
                    if random.random() < mut_rate:
                        syn.acc += random.uniform(-VARIATION_MAGNITUDE, VARIATION_MAGNITUDE)

        # 🧬 evolve relay SPLIT TRAITS (threshold/ratio/delay) under the same mutation pressure
        for b in self.bricks:
            if not b.alive or b.rom_locked: continue
            zone_cfg = ZONE_PARAMS[b.zone]
            for relay in b.relays:
                relay.mutate_traits(zone_cfg["mut"])
            # 🔇 evolve the firing threshold (find the right 'how much before I speak' per cell)
            if random.random() < zone_cfg["mut"]:
                b.fire_threshold = max(0.1, min(3.0, b.fire_threshold + random.uniform(-0.15, 0.15)))
            # 🦔 evolve lateral-inhibition strength the same way -- work or die decides whether
            # suppressing local competitors helps or hurts THIS brick's organism, nothing hand-tuned
            if random.random() < zone_cfg["mut"]:
                b.inhibition_strength = max(0.0, min(1.0, b.inhibition_strength + random.uniform(-0.15, 0.15)))
            # 🗳️➡️➕ evolve readout_weight the same way -- only matters under READOUT_MODE="linear",
            # harmless dead weight under "vote", but mutated unconditionally so a mode switch mid-
            # lineage never finds every brick frozen at its birth value with zero variation to select on.
            if random.random() < zone_cfg["mut"]:
                b.readout_weight = max(-5.0, min(5.0, b.readout_weight + random.uniform(-0.15, 0.15)))

        module_zones = defaultdict(list)
        for b in self.bricks:
            if b.alive: module_zones[b.module_id].append(b)
        for m_id, bricks in module_zones.items():
            avg_err = sum(b.prediction_error for b in bricks) / max(len(bricks), 1)
            avg_fit = sum(b.fitness for b in bricks) / max(len(bricks), 1)
            if avg_err > 5.0 and avg_fit < 0.4:
                for b in bricks:
                    if random.random() < 0.1: b.zone = "FAST"
            elif avg_err < 2.0 and avg_fit > 0.7:
                for b in bricks:
                    if random.random() < 0.1: b.zone = "SLOW"

    def _expire_probation(self):
        """Clear cull-immunity for any brick whose PROBATION_CYCLES deadline has passed. Called every
        cycle from run() (not just at sleep) so PROBATION_CYCLES is a real, cycle-precise, testable
        parameter -- see its definition for why this was made explicit and independently A/B-able."""
        for b in self.bricks:
            if b.alive and getattr(b, "probation", False) and self.current_time >= getattr(b, "probation_deadline", 0):
                b.cull_immune = False
                b.probation = False

    def _engine_caught(self):
        """🔧 Has the engine caught? True when enough NON-SEED cells reliably produce the answer, so the
        swarm can sustain it WITHOUT the seed injecting. Only then may the hand-crank disengage."""
        n = sum(1 for b in self.bricks
                if b.alive and b.id not in self.seed_brick_ids and b.recent_task_score >= 0.75)
        return n >= ENGINE_CATCH_MIN_CELLS

    def _run_sleep_dag(self):
        """
        🌙 SLEEP = GLOBAL ORGANISM MAINTENANCE PHASE (v4.10 mechanical core).
        Sleep is NOT a local timer op -- it is a whole-organism phase: normal operation is suspended and the
        organism does what it can only do when not running. MECHANICAL CORE (per the clinical build spec):
          (a) CULL THE DEFECTIVE  -- delete low-task-credit cells (never seed/ROM/high-credit; by CREDIT not
                                     internal proxies, never random).
          (b) COPY THE WINNERS    -- replicate high-task-credit cells' patterns into the freed slots, so good
                                     patterns MULTIPLY (not random injection).
          (c) TOXIN / JUNK FLUSH  -- reset half-committed accumulators + stale buffers so wake starts clean.
          (d) PROTECT THE WORKING -- do NOT re-mutate / inject-noise / reap consolidated/high-credit/seed/ROM.
        The old corrosive ops (random FAST->SLOW injection, proxy-ROM, unconditional in-sleep mutation) are
        REMOVED -- they were why TaskCorrect fell on sleep cycles.
        """
        print(" 🌙 SLEEP DAG TRIGGERED: global maintenance phase (replay-all / cull / copy / flush).")
        self.is_sleeping = True

        # PROBATION EXPIRY moved to the per-cycle main loop (see _expire_probation()) so a shorter
        # PROBATION_CYCLES value actually takes effect at that cycle count, not just "whenever the
        # next sleep happens to occur." Kept as a safety-net backstop here too in case a brick's
        # deadline was somehow never checked between sleeps.
        self._expire_probation()

        # 🔁 SLEEP REPLAY-ALL-TASKS (the catastrophic-forgetting cure): re-present EVERY known task pair and
        # run learning, so consolidation forms JOINT representations across ALL tasks (weights stay near every
        # task's manifold, not just the most recent). This is what biological sleep does -- rehearse old
        # memories interleaved so they aren't overwritten.
        REPLAY_ROUNDS = 8
        for _r in range(REPLAY_ROUNDS):
            for (call, correct) in self.TASK_PAIRS:
                self.inject_problem("replay", 1.0, forced_call=call)
                self._update_bricks()
                self._fire_relays()
                self._evaluate_fitness()
        print(f"    🔁 sleep replay: {REPLAY_ROUNDS} rounds x {len(self.TASK_PAIRS)} tasks rehearsed (joint consolidation)")
        _nsal = sum(1 for b in self.bricks if b.alive and getattr(b, "salience", 0.0) > 0.5)
        print(f"    🌿 garden: {_nsal} salient/conflicted cells (ivy-covered statues) -> consolidated first")

        living = [b for b in self.bricks if b.alive]
        # classify by TASK CREDIT (recent_task_score) -- the signal Fix #2 gave us. Protect the good.
        # v4.11 CALIBRATION: PRUNE to a healthy population, never STARVE to seed-only.
        WORKING_FLOOR = 0.55      # recognizers now climb well past this when held (not diluted by other tasks)
        ALIVE_FLOOR_FRAC = ALIVE_FLOOR_FRAC_CFG   # configurable: raise to punish LESS
        MAX_CULL_FRAC = MAX_CULL_FRAC_CFG         # configurable: lower to punish LESS
        def protected(b):
            return (b.rom_locked or getattr(b, "cull_immune", False) or getattr(b, "is_seed_crank", False)
                    or (b.id in self.seed_brick_ids) or (b.recent_task_score >= WORKING_FLOOR))

        winners = [b for b in living if (b.recent_task_score >= WORKING_FLOOR or getattr(b, "cull_immune", False))
                   and not getattr(b, "is_seed_crank", False)]

        # (a) CULL THE DEFECTIVE -- GENTLY: take the WORST cells by credit, but only a capped fraction, and
        # never drop below the alive-floor. Prune the bottom, keep the body alive to grow.
        # 🌈 DIVERSITY PRESERVATION: identify cells that UNIQUELY cover a prototype (endangered) -> immune.
        if PRESERVE_DIVERSITY:
            proto_cells = [b for b in living if b.prototype is not None]
            for b in proto_cells:
                # is there ANOTHER living cell with a close prototype? if not, b is the last of its kind.
                unique = True
                for other in proto_cells:
                    if other is b: continue
                    d = sum((p-q)**2 for p,q in zip(b.prototype, other.prototype)) ** 0.5
                    if d < 4.0:                      # someone else covers this cluster
                        unique = False; break
                b.endangered = unique                # last cell covering its prototype -> protect it
        def _endangered(b):
            return PRESERVE_DIVERSITY and getattr(b, "endangered", False)
        # ⚖️ THE CONSERVATION LAW (v4.19): SLEEP CAN ONLY REPLACE, NEVER MERELY REMOVE. A weak cell is culled
        # ONLY at the instant a better replacement is ready to take its slot -- removal+replacement is ONE
        # ATOMIC SWAP, never two steps. The number replaced is CAPPED BY THE NUMBER OF GOOD CELLS available to
        # clone from. If zero good cells are available, NOBODY dies this sleep. Population is CONSERVED exactly;
        # quality only RISES. (Not killing -- a worn-out cell is RETRAINED into a copy of a good one.)
        # 🌿 THE GARDEN: compute SALIENCE = local prototype-space DISAGREEMENT. A cell is SALIENT (a "statue",
        # the ivy-covered confusion to resolve) if another cell sits CLOSE in call-prototype space but the two
        # DISAGREE on the answer -- that is exactly the contamination region (e.g. (1,3,5) vs (5,7,9) bleed).
        # Walk this gradient: the WORST cell in the MOST-CONFLICTED region is replaced FIRST (targeted surgery,
        # not random cull). Settled cells (no nearby disagreement) fade to scenery -> left alone.
        proto_cells = [b for b in living if getattr(b, "prototype", None) is not None]
        for b in living:
            b.salience = 0.0
        for b in proto_cells:
            for other in proto_cells:
                if other is b: continue
                dcall = sum((p-q)**2 for p,q in zip(b.prototype, other.prototype)) ** 0.5
                if dcall < 8.0 and b.proto_answer is not None and other.proto_answer is not None:
                    dans = abs(b.proto_answer - other.proto_answer)
                    if dans > 1.5:
                        # close inputs, different answers = a CONFLICT. Salience grows as inputs get CLOSER
                        # while answers stay APART (the sharper the contradiction, the brighter the statue).
                        b.salience += dans / (dcall + 1.0)
        # cull candidates: the worst cells, but ORDERED BY SALIENCE (most-conflicted region first), so sleep
        # operates on the CONFUSION before anything else. Within equal salience, worst task-score first.
        cull_candidates = [b for b in living
                           if not protected(b) and not _endangered(b) and b.age > 60]
        cull_candidates.sort(key=lambda b: (-getattr(b, "salience", 0.0), b.recent_task_score))
        max_by_frac = int(len(living) * MAX_CULL_FRAC)
        min_alive = int(len(living) * ALIVE_FLOOR_FRAC)
        max_removable = max(0, len(living) - min_alive)
        # ★ the cull is now CAPPED BY len(winners): you may only replace as many as you have replacements for.
        n_swap = min(len(cull_candidates), max_by_frac, max_removable, len(winners))

        # 🌿 v4.21 ANTI-COLONIZATION census: group living proto-cells by their ANSWER-IDENTITY (rounded
        # proto_answer) so we can (b) cap clones per identity and (c) protect the minority defenders.
        def _ident(b):
            pa = getattr(b, "proto_answer", None)
            return None if pa is None else round(float(pa))
        from collections import defaultdict
        ident_counts = defaultdict(int)
        for b in living:
            if b.alive and _ident(b) is not None:
                ident_counts[_ident(b)] += 1
        # winners grouped by identity, so we can re-seed a confused cell with its OWN kind
        winners_by_ident = defaultdict(list)
        for w in winners:
            if _ident(w) is not None:
                winners_by_ident[_ident(w)].append(w)
        # the set of distinct task answers we must keep represented (the 6 true answers)
        true_answers = set(round(float(a)) for (_c, a) in self.TASK_PAIRS)
        answer_to_task = {round(float(a)): (list(c), float(a)) for (c, a) in self.TASK_PAIRS}
        MIN_DEFENDERS = 3          # never cull below this many cells of any task-answer identity
        CLONE_CAP = max(2, n_swap // max(1, len(true_answers)))   # per-identity clone cap this sleep
        clones_made = defaultdict(int)
        culled = []
        copied = 0
        # which task-answers are UNDER-represented? those most need a defender cloned (rescue the minority).
        def _under_represented_ident():
            present = [(a, ident_counts.get(a, 0)) for a in true_answers]
            present.sort(key=lambda kv: kv[1])     # fewest first
            for a, _cnt in present:
                if winners_by_ident.get(a) and clones_made[a] < CLONE_CAP:
                    return a
            return None

        actually_swapped = []
        for slot in cull_candidates[:n_swap]:
            # (c) PROTECT THE WEAKER SIDE: if this slot is one of the last MIN_DEFENDERS of its identity, SKIP
            # it -- the minority defender is not cannon fodder for a stronger neighbor.
            sid = _ident(slot)
            if sid is not None and sid in true_answers and ident_counts.get(sid, 0) <= MIN_DEFENDERS:
                continue

            # find the most UNDER-REPRESENTED true answer (fewest living defenders), regardless of winners.
            present = sorted(((a, ident_counts.get(a, 0)) for a in true_answers), key=lambda kv: kv[1])
            target_ident = None
            for a, _cnt in present:
                if clones_made[a] < CLONE_CAP:
                    target_ident = a; break
            if target_ident is None:
                continue                            # all caps hit -> nobody dies, conserve

            if winners_by_ident.get(target_ident):
                # (a) clone an existing GOOD exemplar of this identity (same-kind reinforcement)
                w = random.choice(winners_by_ident[target_ident])
                _resurrect = False
            else:
                # ★ RESURRECTION: this true answer has NO living winners (went EXTINCT) -> it can NEVER come
                # back by cloning. Re-plant its prototype straight from the TASK DEFINITION (ground truth),
                # exactly like the original seed. The garden can RESURRECT a lost prototype, not only clone.
                w = None
                _resurrect = True
            clones_made[target_ident] += 1
            if sid is not None:
                ident_counts[sid] = max(0, ident_counts[sid] - 1)
            ident_counts[target_ident] = ident_counts.get(target_ident, 0) + 1
            actually_swapped.append(slot)
            if _resurrect:
                # plant the extinct identity from ground truth and SKIP the clone-from-winner body below
                rc, ra = answer_to_task[target_ident]
                slot.prototype = [float(x) for x in rc]
                slot.proto_answer = float(ra)
                slot.mem = int(round(ra)); slot.think = int(round(ra))
                slot.mem_acc = 0.0; slot.think_acc = 0.0; slot.relay_acc = 0.0
                slot.plasticity = 1.0; slot.rom_locked = False
                slot.recent_task_score = 0.6        # give it a fighting chance to survive to next sleep
                slot.fitness = 0.6; slot.energy = 25.0; slot.consolidation_streak = 0
                slot.cull_immune = True             # protect the freshly-resurrected seedling briefly
                culled.append(slot); copied += 1
                continue
            # ATOMIC SWAP: the weak cell is OVERWRITTEN by a copy of a good cell (retrained, not killed).
            # It never goes dead -- it's reborn in place as a clone of a winner. No hole, no bleed.
            slot.mem = w.mem; slot.think = w.think
            slot.mem_acc = 0.0; slot.think_acc = 0.0; slot.relay_acc = 0.0
            slot.zone = w.zone
            slot.fire_threshold = getattr(w, "fire_threshold", 1.0)
            slot.inhibition_strength = getattr(w, "inhibition_strength", 0.5)
            slot.readout_weight = getattr(w, "readout_weight", 0.0)
            slot.plasticity = 1.0
            slot.rom_locked = False
            # DISCOUNT+PROBATION FIX (2026-09-27): the discount itself is a deliberate, legitimate
            # anti-monoculture safeguard (a naive full-inheritance clone would be indistinguishable
            # from its parent in selection terms, risking one lucky winner sweeping the population)
            # -- but WORKING_FLOOR=0.55 means a discounted clone of an 0.85-scoring winner starts at
            # ~0.42, already below the protection floor, and can be culled AGAIN before it ever gets
            # a real chance to re-prove what its parent already proved. Keep the discount; add a
            # probation window (same pattern already used for freshly-resurrected seedlings above)
            # so discounted trust and cullability are separated instead of conflated.
            slot.recent_task_score = w.recent_task_score * 0.5
            slot.fitness = w.fitness * 0.6
            slot.cull_immune = True       # protected for PROBATION_CYCLES despite the discount
            slot.probation = True         # marks this immunity as temporary -- cleared by cycle deadline
            slot.probation_deadline = self.current_time + PROBATION_CYCLES
            slot.energy = 20.0
            slot.consolidation_streak = 0
            # inherit the winner's PROTOTYPE too (so the clone recognizes what the winner recognized)
            if getattr(w, "prototype", None) is not None:
                slot.prototype = list(w.prototype); slot.proto_answer = w.proto_answer
            slot.synapses = [type(sy)(sy.target_id, sy.weight, sy.delay) for sy in w.synapses]
            # RELAY-WIPE FIX (2026-09-27): growth already clones evolved relay traits with small
            # variation when adding new capacity -- replacement was silently doing something
            # different (deleting the routing structure entirely) for the exact same "clone what
            # worked" operation. Bring both paths into alignment: clone, don't amputate.
            slot.relays = []
            for donor_relay in w.relays:
                nr = PairedRelay(source_id=slot.id, targets=list(donor_relay.targets),
                                  base_delay=donor_relay.base_delay)
                nr.split_threshold = max(0.5, min(8.0, donor_relay.split_threshold + random.gauss(0, 0.2)))
                nr.split_ratio = max(0.1, min(0.9, donor_relay.split_ratio + random.gauss(0, 0.03)))
                nr.back_delay = max(1, donor_relay.back_delay + random.choice([-1, 0, 0, 1]))
                slot.relays.append(nr)
            culled.append(slot); copied += 1
        # population is EXACTLY conserved: every cell touched was swapped in place, none left dead.
        # winners MULTIPLY into spare DEAD capacity too (not just culled slots), so good patterns grow
        if winners:
            dead_slots = [b for b in self.bricks if not b.alive and b.id not in self.seed_brick_ids][:len(winners)]
            for slot in dead_slots:
                w = random.choice(winners)
                slot.alive = True
                slot.mem = w.mem; slot.think = w.think
                slot.mem_acc = 0.0; slot.think_acc = 0.0; slot.relay_acc = 0.0
                slot.zone = w.zone
                slot.fire_threshold = getattr(w, "fire_threshold", 1.0)
                slot.inhibition_strength = getattr(w, "inhibition_strength", 0.5)
                slot.readout_weight = getattr(w, "readout_weight", 0.0)
                slot.plasticity = 1.0; slot.rom_locked = False
                # Same discount+probation and relay-inheritance fix as the swap path above -- this is
                # the SAME "clone a winner" operation, on dead capacity instead of a culled slot.
                slot.recent_task_score = w.recent_task_score * 0.5
                slot.fitness = w.fitness * 0.6; slot.energy = 20.0
                slot.cull_immune = True
                slot.probation = True
                slot.probation_deadline = self.current_time + PROBATION_CYCLES
                slot.consolidation_streak = 0
                slot.synapses = [type(sy)(sy.target_id, sy.weight, sy.delay) for sy in w.synapses]
                slot.relays = []
                for donor_relay in w.relays:
                    nr = PairedRelay(source_id=slot.id, targets=list(donor_relay.targets),
                                      base_delay=donor_relay.base_delay)
                    nr.split_threshold = max(0.5, min(8.0, donor_relay.split_threshold + random.gauss(0, 0.2)))
                    nr.split_ratio = max(0.1, min(0.9, donor_relay.split_ratio + random.gauss(0, 0.03)))
                    nr.back_delay = max(1, donor_relay.back_delay + random.choice([-1, 0, 0, 1]))
                    slot.relays.append(nr)
                copied += 1

        # (c) TOXIN / JUNK FLUSH: reset half-committed accumulators + transient buffers for ALL non-protected
        #     working cells, so wake starts clean (does NOT touch protected cells' committed state).
        for b in self.bricks:
            if not b.alive: continue
            if b.rom_locked or b.id in self.seed_brick_ids: continue
            b.mem_acc = 0.0; b.think_acc = 0.0; b.relay_acc = 0.0
            b.input_this_cycle = 0.0
            b.refractory = 0

        # (d) PROTECT THE WORKING: we did NOT call _mutate_and_select() and did NOT inject noise. Working/
        #     consolidated/seed/ROM cells are untouched. That is the whole point.

        # 🌱 RECOVERED GROWTH STEP (2026-09-27): grow AFTER cull+copy, using this sleep's own fresh
        # fitness data, and only if population is still within a bounded safety ceiling -- real
        # growth, but never unbounded. 2x initial size is a conservative starting cap, adjustable.
        n_alive = sum(1 for b in self.bricks if b.alive)
        if n_alive < INIT_BRICKS * 2:
            self._grow_network()

        # harmless bookkeeping: context reset + capacity growth + generation tick
        self.context_tokens = 0
        # keep the "day" a stable size (do NOT balloon capacity each sleep -- a day is a day)
        self.generation += 1
        self.is_sleeping = False
        self._last_sleep_cycle = self.current_time
        print(f" 💤 Sleep complete (REPLACE-ONLY: {copied} weak cells retrained into clones of winners, population conserved). Gen {self.generation} | culled {len(culled)} defective, copied {copied} "
              f"winners | {len(winners)} working cells protected | capacity {self.context_capacity}")

    def _wolfpack_pass(self):
        """🐺 WOLFPACK / "socializing" (2026-10-01) -- see the WOLFPACK_* module constants for the
        full rationale. Runs EVERY cycle (unlike sleep, which only fires when context fills): track
        which living, unprotected bricks are pinned at the state boundary; for any that have been
        pinned WOLFPACK_PIN_THRESHOLD cycles running, decompose+graft their prototype onto the
        closest-matching living brick (reinforcing a real signal instead of discarding one), then
        reset the sick brick to a fresh state. A pure reorganization of content already present in
        the population -- never adds information, never trains on anything new (Jonathan's framing:
        "a defrag disc for old mechanical hard drives... fine-tuning in the real sense of the word,
        not the conventional sense")."""
        if not WOLFPACK_ENABLED:
            return 0, 0
        living = [b for b in self.bricks if b.alive]

        def protected(b):
            return (b.rom_locked or getattr(b, "cull_immune", False) or getattr(b, "is_seed_crank", False)
                    or (b.id in self.seed_brick_ids))

        # update each living brick's pin-streak: climbs while touching the boundary, heals to 0 the
        # instant it isn't (this is a STREAK, not a cumulative scar -- a brick that recovers on its
        # own before reaching threshold is left alone, matching the "sloppy, cheap, constant" design).
        if WOLFPACK_LSL_PIN_GATE:
            # 🐺🔬 per-zone Phi_pos (healthy bricks' own zone, as of END of last cycle) vs shared
            # Phi_neg (every living brick pooled) -- see WOLFPACK_LSL_PIN_GATE's module comment.
            healthy_now = [b for b in living if b.pin_streak == 0]
            by_zone = {}
            for b in healthy_now:
                by_zone.setdefault(b.zone, []).append(b)
            zone_gauss = {}
            for zone, members in by_zone.items():
                if len(members) < 2:
                    continue
                cols = [[getattr(hb, f) for hb in members] for f in ("mem", "think", "relay_strength")]
                mean = [sum(c) / len(c) for c in cols]
                var = [sum((x - m) ** 2 for x in c) / len(c) for c, m in zip(cols, mean)]
                zone_gauss[zone] = (mean, var)

            all_cols = [[getattr(hb, f) for hb in living] for f in ("mem", "think", "relay_strength")]
            global_mean = [sum(c) / len(c) for c in all_cols]
            global_var = [sum((x - m) ** 2 for x in c) / len(c) for c, m in zip(all_cols, global_mean)]

            def pin_log_density(x, mean, var):
                floor = [max(v * WOLFPACK_GATE_VAR_FLOOR_FRAC, 1e-6) for v in global_var]
                v = [max(vi, fl) for vi, fl in zip(var, floor)]
                return -0.5 * sum((xi - mi) ** 2 / vi + math.log(2 * math.pi * vi)
                                   for xi, mi, vi in zip(x, mean, v))

            for b in living:
                state = (b.mem, b.think, b.relay_strength)
                if b.zone in zone_gauss:
                    zmean, zvar = zone_gauss[b.zone]
                    anomalous = pin_log_density(state, zmean, zvar) < pin_log_density(state, global_mean, global_var)
                else:
                    # too few healthy peers in this zone to fit Phi_pos -- fall back to the exact
                    # boundary check for just this brick rather than guessing.
                    anomalous = (b.mem >= STATE_MAX or b.think >= STATE_MAX or b.relay_strength >= STATE_MAX
                                 or b.mem <= STATE_MIN or b.think <= STATE_MIN or b.relay_strength <= STATE_MIN)
                b.pin_streak = b.pin_streak + 1 if anomalous else 0
        else:
            for b in living:
                if b.mem >= STATE_MAX or b.think >= STATE_MAX or b.relay_strength >= STATE_MAX \
                   or b.mem <= STATE_MIN or b.think <= STATE_MIN or b.relay_strength <= STATE_MIN:
                    b.pin_streak += 1
                else:
                    b.pin_streak = 0

        sick = [b for b in living if not protected(b) and b.pin_streak >= WOLFPACK_PIN_THRESHOLD]
        if not sick:
            return 0, 0
        healthy_proto = [b for b in living if b.prototype is not None and b.pin_streak == 0
                          and b not in sick]

        # 🐺🔬 Phi_neg: ONE shared reference distribution fit over every living healthy prototype,
        # refit fresh each wolfpack pass (cheap -- mean/var over whatever's currently alive, same
        # spirit as LSL's small generic reference sample). Only used when WOLFPACK_LSL_GATE is on.
        global_mean = global_var = None
        if WOLFPACK_LSL_GATE and healthy_proto:
            dims = len(healthy_proto[0].prototype)
            cols = [[hp.prototype[d] for hp in healthy_proto] for d in range(dims)]
            global_mean = [sum(c) / len(c) for c in cols]
            global_var = [sum((x - m) ** 2 for x in c) / len(c) for c, m in zip(cols, global_mean)]

        def log_gaussian_density(x, mean, var):
            floor = [max(v * WOLFPACK_GATE_VAR_FLOOR_FRAC, 1e-6) for v in (global_var or var)]
            v = [max(vi, fl) for vi, fl in zip(var, floor)]
            return -0.5 * sum((xi - mi) ** 2 / vi + math.log(2 * math.pi * vi)
                               for xi, mi, vi in zip(x, mean, v))

        def lsl_gate_accept(proto, sorted_candidates):
            """Accept iff proto is a better fit to the K nearest healthy prototypes' own local
            distribution than to the shared global one -- a margin that tightens in crowded regions
            of prototype-space and loosens in sparse ones, instead of one fixed radius for both."""
            k = min(WOLFPACK_GATE_K_NEIGHBORS, len(sorted_candidates))
            neighborhood = sorted_candidates[:k]
            dims = len(proto)
            cols = [[c.prototype[d] for c in neighborhood] for d in range(dims)]
            local_mean = [sum(c) / len(c) for c in cols]
            local_var = [sum((x - m) ** 2 for x in c) / len(c) for c, m in zip(cols, local_mean)]
            margin = (log_gaussian_density(proto, local_mean, local_var)
                      - log_gaussian_density(proto, global_mean, global_var))
            return margin > 0.0

        grafted = 0
        for b in sick:
            if b.prototype is not None and healthy_proto:
                sorted_candidates = sorted(
                    healthy_proto,
                    key=lambda other: math.sqrt(sum((p - q) ** 2 for p, q in zip(b.prototype, other.prototype))))
                best = sorted_candidates[0]
                best_d = math.sqrt(sum((p - q) ** 2 for p, q in zip(b.prototype, best.prototype)))
                if WOLFPACK_LSL_GATE:
                    accept = lsl_gate_accept(b.prototype, sorted_candidates)
                else:
                    accept = best_d <= WOLFPACK_MATCH_RADIUS
                if accept:
                    # GRAFT: nudge the healthy match's prototype toward the sick brick's (small step,
                    # reinforcement not overwrite), and give it a small fitness/credit boost -- the
                    # sick brick's salvageable signal is absorbed into a signal that's actually alive.
                    best.prototype = [(1 - WOLFPACK_GRAFT_ALPHA) * p + WOLFPACK_GRAFT_ALPHA * q
                                      for p, q in zip(best.prototype, b.prototype)]
                    best.fitness = min(1.0, best.fitness + 0.02)
                    best.recent_task_score = min(1.0, best.recent_task_score + 0.02)
                    grafted += 1
            # RESET: whether grafted or not (nothing to graft if no prototype or no close match),
            # the sick brick itself always gets cleared -- same fresh-state fields Brick.__init__
            # uses, id/pos/module_id/zone/synapses/relays left untouched (structural placement kept,
            # corrupted content cleared).
            b.mem = random.randint(0, STATE_MAX)
            b.think = random.randint(0, STATE_MAX)
            b.relay_strength = random.randint(0, STATE_MAX)
            b.mem_acc = b.think_acc = b.relay_acc = 0.0
            b.prototype = None
            b.proto_answer = None
            b.match_weight = 0.0
            b.prediction_error = 0.0
            b.consecutive_errors = 0
            b.correct_predictions = 0
            b.consolidation_streak = 0
            b.pin_streak = 0
        return len(sick), grafted

    def run_cycle(self):
        """🔄 Main execution loop: inject → update → fire → evaluate → mutate → sleep check."""
        self.current_time += 1
        self._flush_pending_deliveries()  # BUG6 FIX: apply any relay signals whose delay matured
        problems = ["interception", "noise", "memory", "pattern", "cross_module"]
        p_type = problems[self.current_time % len(problems)]
        self.inject_problem(p_type, signal=random.uniform(0.5, 2.5))

        self._update_bricks()
        self._apply_lateral_inhibition()
        self._fire_relays()
        self._evaluate_fitness()
        self._mutate_and_select()
        self._reap_dead()
        self._autosarcophagy()
        self._expire_probation()
        n_sick, n_grafted = self._wolfpack_pass()
        self._last_wolfpack = (n_sick, n_grafted)

        # 🛏️ SLEEP = how she deals with an OVERFILLED CONTEXT WINDOW. Triggered by context FULLNESS at the
        # RIGHT SCALE: the context window is LARGE (a "day" of experience), so filling it -> sleep happens
        # RARELY and adapts to LOAD (dense day fills sooner, quiet day later). Principled, not a clock.
        if self.context_tokens / self.context_capacity >= CONTEXT_THRESHOLD and not self.is_sleeping:
            self._run_sleep_dag()

        if self.current_time % 100 == 0:
            import time as _time
            _now = _time.time()
            _prev = getattr(self, "_last_print_time", _now)
            _cps = 100.0 / max(1e-6, (_now - _prev))
            self._last_print_time = _now
            self._cps = _cps
            alive_count = sum(1 for b in self.bricks if b.alive)
            rom_count = sum(1 for b in self.bricks if b.rom_locked)
            avg_fit = sum(b.fitness for b in self.bricks if b.alive) / max(alive_count, 1)
            # 🍼 TASK ACCURACY: the thing that actually matters -- is the WHOLE answering correctly?
            wc = getattr(self, "_wc_avg", 0.0)   # windowed average TaskCorrect (true rate)
            # also report average split traits so we can watch evolution tune them
            relays = [r for b in self.bricks if b.alive for r in b.relays]
            n_rel = max(len(relays), 1)
            avg_thr = sum(r.split_threshold for r in relays) / n_rel if relays else 0.0
            avg_ratio = sum(r.split_ratio for r in relays) / n_rel if relays else 0.0
            n_splits = sum(r.split_count for r in relays)
            print(f" ⏱️ Cyc {self.current_time} | Alive:{alive_count} ROM:{rom_count} | AvgFit:{avg_fit:.3f}"
                  f" | 🍼TaskCorrect:{wc:.3f} | split_thr:{avg_thr:.2f} ratio:{avg_ratio:.2f} splits:{n_splits}"
                  f" | Ctx:{self.context_tokens}/{self.context_capacity}"
                  f" | {getattr(self,'_cps',0):.0f}cyc/s")
            if self.current_time % 500 == 0 and DIAGNOSTIC_PROBE_ENABLED:
                # 🔍 SHOW ACTUAL ANSWERS: probe each task pair, print call -> answer -> correct
                # 2026-10-16/17: this probe calls _update_bricks()/_fire_relays() once per
                # TASK_PAIR -- real training machinery, not a passive read (see
                # DIAGNOSTIC_PROBE_ENABLED's comment above for the measured disturbance). Disabled
                # by default; only runs when DIAGNOSTIC_PROBE_ENABLED is explicitly set True.
                saved_context_tokens = self.context_tokens
                samples = []
                for (call, correct) in self.TASK_PAIRS:
                    self.inject_problem("probe", 1.0, forced_call=call)
                    self._update_bricks(); self._fire_relays()
                    ans = self._read_response()
                    astr = f"{ans:.1f}" if ans is not None else "silent"
                    mark = "✓" if (ans is not None and abs(ans - correct) < 1.0) else " "
                    samples.append(f"{call}->{astr}(want {correct}){mark}")
                print("    🔍 " + " | ".join(samples))
                self.context_tokens = saved_context_tokens

    def save_checkpoint(self):
        """💾 Serialize full substrate state to JSON. Atomic write survives hard kills."""
        state = {
            "bricks": [],
            "meta": {
                "generation": self.generation,
                "current_time": self.current_time,
                "context_capacity": self.context_capacity,
                "context_tokens": self.context_tokens
            }
        }
        for b in self.bricks:
            state["bricks"].append({
                "id": b.id, "pos": list(b.pos), "module_id": b.module_id,
                "mem": b.mem, "think": b.think, "relay_strength": b.relay_strength,
                "fitness": b.fitness, "zone": b.zone, "rom": b.rom_locked,
                "synapses": [{"target": s.target_id, "weight": s.weight, "delay": s.delay, "fitness": s.fitness} for s in b.synapses]
            })
        temp_path = CHECKPOINT_PATH.with_suffix(".tmp")
        with open(temp_path, "w") as f: json.dump(state, f, indent=2)
        temp_path.replace(CHECKPOINT_PATH)
        print(f" 💾 Checkpoint saved to {CHECKPOINT_PATH}")

    def load_checkpoint(self):
        """📂 Deserialize substrate state from JSON. Restores bricks, synapses, meta."""
        if not CHECKPOINT_PATH.exists():
            print(" ⚠️ No checkpoint found. Starting fresh.")
            return
        with open(CHECKPOINT_PATH, "r") as f: data = json.load(f)
        meta = data["meta"]
        self.generation = meta["generation"]
        self.current_time = meta["current_time"]
        self.context_capacity = meta["context_capacity"]
        self.context_tokens = meta["context_tokens"]
        self.bricks.clear(); self.brick_lookup.clear()
        for b_data in data["bricks"]:
            b = Brick(b_data["id"], tuple(b_data["pos"]), b_data["module_id"], b_data["zone"])
            b.mem = b_data["mem"]; b.think = b_data["think"]; b.relay_strength = b_data["relay_strength"]
            b.fitness = b_data["fitness"]; b.rom_locked = b_data["rom"]
            for s_data in b_data["synapses"]:
                b.synapses.append(Synapse(s_data["target"], s_data["weight"], s_data["delay"]))
            self.bricks.append(b); self.brick_lookup[b.id] = b
            self._max_id_tracker = max(self._max_id_tracker, b.id)
        print(f" 📂 Checkpoint loaded. Generation: {self.generation} | Bricks: {len(self.bricks)}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global RECOGNITION_MODE, MAX_CULL_FRAC_CFG, ALIVE_FLOOR_FRAC_CFG, CONTEXT_THRESHOLD, DAY_CONTEXT, PRESERVE_DIVERSITY, PROBATION_CYCLES
    parser = argparse.ArgumentParser(description="Sovereign Core v4.3 Evolutionary Substrate")
    parser.add_argument("--cycles", type=int, default=3000, help="Number of cycles to run")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--mode", type=str, default=RECOGNITION_MODE, help="recognition mode: nearest|graded")
    parser.add_argument("--cull-frac", type=float, default=MAX_CULL_FRAC_CFG, help="max cull fraction/sleep (LOWER=punish less)")
    parser.add_argument("--alive-floor", type=float, default=ALIVE_FLOOR_FRAC_CFG, help="min alive fraction (RAISE=punish less)")
    parser.add_argument("--sleep-load", type=float, default=CONTEXT_THRESHOLD, help="context load to trigger sleep (RAISE=sleep less often)")
    parser.add_argument("--day-context", type=int, default=DAY_CONTEXT, help="context window size = a 'day'; fills ~once per this many cycles -> sleep (RAISE = longer day = rarer sleep)")
    parser.add_argument("--no-diversity", action="store_true", help="disable prototype diversity preservation")
    parser.add_argument("--probation-cycles", type=int, default=PROBATION_CYCLES, help="cull-immunity window (in cycles) for discounted clones -- A/B this directly")
    parser.add_argument("--seed", type=int, default=None, help="seed the stdlib random module for reproducible/comparable A-B runs")
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    print("="*70)
    print("SOVEREIGN CORE v4.5 - v4.21b RESURRECTION: garden replants EXTINCT prototypes from ground truth (not only clones survivors)")
    print("="*70)
    print(f"Initial bricks: {INIT_BRICKS} | Context capacity: {CONTEXT_CAPACITY}")
    RECOGNITION_MODE = args.mode
    MAX_CULL_FRAC_CFG = args.cull_frac
    ALIVE_FLOOR_FRAC_CFG = args.alive_floor
    CONTEXT_THRESHOLD = args.sleep_load
    DAY_CONTEXT = args.day_context
    PRESERVE_DIVERSITY = not args.no_diversity
    PROBATION_CYCLES = args.probation_cycles
    print(f"Recognition: {RECOGNITION_MODE} | cull-frac {MAX_CULL_FRAC_CFG} | alive-floor {ALIVE_FLOOR_FRAC_CFG} | sleep-load {CONTEXT_THRESHOLD} | day-context {DAY_CONTEXT} | diversity {PRESERVE_DIVERSITY} | probation-cycles {PROBATION_CYCLES}")
    print(f"Sleep trigger: >{CONTEXT_THRESHOLD*100:.0f}% context load")
    print(f"Growth factor: +{int((GROWTH_FACTOR-1)*100)}% capacity per rebuild")
    print(f"Zones: FAST (cleanup) / SLOW (persistence) / MIRROR (simulation)")
    print(f"Sleep DAG: FAST replay → SLOW injection → ROM promotion → Drift")
    print(f"ROM threshold: ≥{ROM_CONSOLIDATION_THRESHOLD} consolidations + T≥8 + R≥7 + S≥8")
    print(f"Accumulator bridge: |acc| >= {ACCUM_THRESHOLD} → discrete commit")
    print()

    core = SovereignCore(init_bricks=INIT_BRICKS)
    if args.resume: core.load_checkpoint()

    def emergency_save(signum, frame):
        print("\n ⚠️ Interrupt signal received. Emergency checkpointing...")
        core.save_checkpoint()
        sys.exit(0)
    signal.signal(signal.SIGINT, emergency_save)
    signal.signal(signal.SIGTERM, emergency_save)

    try:
        for _ in range(args.cycles):
            core.run_cycle()
            if core.current_time % 500 == 0: core.save_checkpoint()
    except KeyboardInterrupt:
        print("\n ⛔ Interrupted. Saving state...")
    finally:
        core.save_checkpoint()
        print(" ✅ Sovereign Core v4.3 halted gracefully.")

if __name__ == "__main__":
    main()