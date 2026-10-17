#!/usr/bin/env python3
"""GLM's proposed diagnostic, 2026-10-17: cheapest, highest-value next experiment, done BEFORE
any architecture change. Question: does the substrate's brick population even have enough
representational bandwidth to distinguish the 850 distinct bit-level recall contexts at all, or
do many of them collapse onto identical (or near-identical) internal activation/readout --
an information-theoretic ceiling no amount of evolution can fix?

Method: start from a completely FRESH, untrained population (same init as cycle 0 of the real
bit-level run -- no training, no sleep, no evolution). For every one of the 850 real
context->target pairs from the bit-level task, run exactly ONE forward pass (inject_problem +
_update_bricks + _fire_relays + _read_response) on an independent deep-copy of that same fresh
population (so every probe starts from the IDENTICAL untrained state -- isolates representational
capacity from any training-order effect). Record the raw (pre-rounding) response for each context.
Then measure: how many of the 850 contexts produce responses that collide (within epsilon) with a
DIFFERENT context's response. A high collision rate directly supports GLM's "representational
bandwidth mismatch" hypothesis; a low collision rate rules it out and points at the missing
retrieval-operator / selection-pressure explanations instead (DeepSeek/Qwen/Gemini/ChatGPT).
"""
import sys, os, copy, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
from lucy_favorite_color_core_bitlevel import LucyBitLevelCore, TASK_PAIRS_RAW, BIT_LOW, BIT_HIGH

sc.WOLFPACK_SISTER_MATCH = False
EPS = 0.75  # collision tolerance on the raw continuous response


WARMUP_CYCLES = 8  # 2026-10-17 correction: a single cold forward pass is silent for 849/850
# contexts -- the SPEAK-ONLY-WHEN-SPOKEN-TO firing gate requires input_this_cycle to cross
# fire_threshold, which a from-scratch population can't do in one pass except via the seed's own
# ROM-locked reflex. That's a firing-threshold fact, not evidence about representational capacity.
# Give each context a short, isolated repeated-exposure warmup (same call every cycle, nothing
# else happening) so accumulators can plausibly cross threshold, same as real training eventually
# does -- THEN read the response. This tests what GLM's hypothesis actually needs: after the
# substrate has had a fair chance to represent a context, do DIFFERENT contexts still collide?


def main():
    random.seed(42)
    fresh = LucyBitLevelCore(init_bricks=sc.INIT_BRICKS)  # cycle-0, zero training, zero sleep

    responses = []
    for call, target in TASK_PAIRS_RAW:
        probe = copy.deepcopy(fresh)  # every context probed from the IDENTICAL untrained state
        for _ in range(WARMUP_CYCLES):
            probe.inject_problem("probe", 1.0, forced_call=list(call))
            probe._update_bricks()
            probe._fire_relays()
        resp = probe._read_response()
        responses.append((call, target, resp))

    valid = [(c, t, r) for (c, t, r) in responses if r is not None]
    silent = len(responses) - len(valid)
    print(f"{len(responses)} contexts probed from a fresh, untrained population.")
    print(f"{silent} produced NO response at all (no output brick fired).")

    # collision rate: how many DISTINCT contexts land within EPS of each other's raw response
    vals = sorted((r, i) for i, (c, t, r) in enumerate(valid))
    collisions = 0
    for i in range(1, len(vals)):
        if abs(vals[i][0] - vals[i - 1][0]) < EPS:
            collisions += 1
    print(f"Collision rate (raw response within {EPS} of a DIFFERENT context's response): "
          f"{collisions}/{len(valid)} = {100*collisions/max(1,len(valid)):.1f}%")

    distinct_rounded = len(set(round(r) for (c, t, r) in valid))
    print(f"Distinct rounded response VALUES across all {len(valid)} probed contexts: "
          f"{distinct_rounded} (substrate range is 0-{sc.STATE_MAX})")

    # bucket by target to see if the SAME target tends to collide together (expected/harmless)
    # or if DIFFERENT targets collide (the real information-theoretic problem)
    import collections
    by_rounded = collections.defaultdict(lambda: {0: 0, 31: 0})
    for (c, t, r) in valid:
        by_rounded[round(r)][int(t)] += 1
    cross_target_buckets = sum(1 for bucket in by_rounded.values() if bucket[0] > 0 and bucket[31] > 0)
    print(f"Rounded-response buckets containing BOTH target=0 and target=31 contexts "
          f"(the real aliasing problem): {cross_target_buckets}/{len(by_rounded)} buckets used")


if __name__ == "__main__":
    main()
