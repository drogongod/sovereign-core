#!/usr/bin/env python3
"""
rom_lock_depth_tradeoff_test.py -- 2026-10-19. Informed by the REAL deepseek-ai/Engram paper (verified,
see deepseek_engram_real_paper_confirmed.md): "relieves early layers from static pattern reconstruction,
preserving effective depth for complex reasoning" -- a capacity/depth opportunity-cost claim, not "stale
memory corrupts the live answer" (already tested and NOT confirmed, ROM_LOCK_SEPARATE_READOUT_ENABLED).

This tests the sharper, Engram-matched hypothesis: does ROM-locking trade SIMPLE/memorized performance
against COMPLEX/generalized performance, using the engine's OWN existing task split -- no new task needed.
TASK_PAIRS[0] = (2,4,6)->8 is the SEEDED call (the firmware reflex answers it directly, closer to pure
memorization). TASK_PAIRS[1:] are NON-SEED calls requiring genuine +2 RULE GENERALIZATION (the seed never
saw these specific sequences) -- closer to "complex reasoning" in Engram's sense. If Jonathan's hypothesis
and Engram's finding both hold, ROM-locking capacity should cost generalization performance more than (or
differently from) simple seeded-call performance -- a real crossover, not uniform harm.
"""
import random
import numpy as np
import sovereign_core as sc

N_CYCLES = 1500
SEEDS = [1, 2, 3]


def run_one(rom_lock: bool, seed: int):
    sc.ROM_LOCK_ENABLED = rom_lock
    sc.ROM_LOCK_MODULE_GATE_ENABLED = False
    sc.ROM_LOCK_SEPARATE_READOUT_ENABLED = False
    sc.INIT_BRICKS = 150
    random.seed(seed)
    np.random.seed(seed)
    core = sc.SovereignCore()
    seed_call = core._seed_call if hasattr(core, "_seed_call") else tuple(sc.TASK_PAIRS[0][0])
    seed_scores, nonseed_scores = [], []
    for _ in range(N_CYCLES):
        core.run_cycle()
        call = getattr(core, "current_call", None)
        wc_window = getattr(core, "_wc_window", None)
        if call is None or not wc_window:
            continue
        last_score = wc_window[-1]
        if tuple(call) == tuple(seed_call):
            seed_scores.append(last_score)
        else:
            nonseed_scores.append(last_score)
    seed_acc = float(np.mean(seed_scores)) if seed_scores else float("nan")
    nonseed_acc = float(np.mean(nonseed_scores)) if nonseed_scores else float("nan")
    return seed_acc, nonseed_acc


results = {"OFF": {"seed": [], "nonseed": []}, "ON": {"seed": [], "nonseed": []}}
for seed in SEEDS:
    off_seed, off_nonseed = run_one(False, seed)
    on_seed, on_nonseed = run_one(True, seed)
    results["OFF"]["seed"].append(off_seed)
    results["OFF"]["nonseed"].append(off_nonseed)
    results["ON"]["seed"].append(on_seed)
    results["ON"]["nonseed"].append(on_nonseed)
    print(f"seed {seed}: OFF  seeded-call(simple)={off_seed:.4f}  nonseed-calls(generalized)={off_nonseed:.4f}")
    print(f"         ON   seeded-call(simple)={on_seed:.4f}  nonseed-calls(generalized)={on_nonseed:.4f}")
    print(f"         delta seeded={on_seed-off_seed:+.4f}   delta nonseed={on_nonseed-off_nonseed:+.4f}")

mean = lambda k1, k2: float(np.mean(results[k1][k2]))
print("\n" + "=" * 70)
print("MEANS across 3 seeds")
print("=" * 70)
print(f"seeded-call(simple):      OFF={mean('OFF','seed'):.4f}  ON={mean('ON','seed'):.4f}  "
      f"delta={mean('ON','seed')-mean('OFF','seed'):+.4f}")
print(f"nonseed-calls(generalize): OFF={mean('OFF','nonseed'):.4f}  ON={mean('ON','nonseed'):.4f}  "
      f"delta={mean('ON','nonseed')-mean('OFF','nonseed'):+.4f}")

seed_delta = mean('ON', 'seed') - mean('OFF', 'seed')
nonseed_delta = mean('ON', 'nonseed') - mean('OFF', 'nonseed')
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
if seed_delta > 0.01 and nonseed_delta < -0.01:
    print("CONFIRMED CROSSOVER: ROM_LOCK helps the simple/memorized seeded call while hurting the")
    print("harder/generalized non-seed calls -- a real trade-off, matching both Jonathan's hypothesis")
    print("and the real deepseek-ai/Engram finding (capacity devoted to static memory costs capacity")
    print("available for harder generalization/reasoning).")
elif seed_delta < -0.01 and nonseed_delta < -0.01:
    print("Both categories hurt by ROM_LOCK -- no crossover, harm looks uniform rather than a real")
    print("simple-vs-complex trade-off. Does not match the Engram-style hypothesis as tested.")
elif abs(seed_delta) <= 0.01 and abs(nonseed_delta) <= 0.01:
    print("No meaningful effect on either category at this scale -- inconclusive, may need more cycles")
    print("or a harder generalization task than the existing +2 sequences provide.")
else:
    print(f"Partial/mixed pattern -- seeded delta {seed_delta:+.4f}, nonseed delta {nonseed_delta:+.4f}.")
    print("Reporting honestly rather than forcing a clean verdict.")
