#!/usr/bin/env python3
"""
romlock_ab_test.py -- 2026-10-19. Controlled, seeded A/B re-test of ROM_LOCK_ENABLED, per Jonathan's
explicit instruction: don't trust the old in-code comment claiming FAST->SLOW injection + proxy-ROM
caused "TaskCorrect to fall on sleep cycles," and don't silently restore it either -- re-test fresh on
the CURRENT engine. Multiple seeds, same seed used for both conditions per trial (fair comparison),
matching this project's own standing discipline (no single-seed verdicts).
"""
import random
import numpy as np
import sovereign_core as sc

N_CYCLES = 1500
SEEDS = [1, 2, 3]

def run_one(rom_lock: bool, module_gate: bool, separate_readout: bool, seed: int) -> float:
    sc.ROM_LOCK_ENABLED = rom_lock
    sc.ROM_LOCK_MODULE_GATE_ENABLED = module_gate
    sc.ROM_LOCK_SEPARATE_READOUT_ENABLED = separate_readout
    sc.INIT_BRICKS = 150
    random.seed(seed)
    np.random.seed(seed)
    core = sc.SovereignCore()
    for _ in range(N_CYCLES):
        core.run_cycle()
    return core._wc_avg if hasattr(core, "_wc_avg") else float("nan")

results = {"OFF": [], "BRICK": [], "MODULE": [], "SEPARATE": []}
for seed in SEEDS:
    off = run_one(False, False, False, seed)
    brick = run_one(True, False, False, seed)
    module = run_one(True, True, False, seed)
    separate = run_one(True, False, True, seed)
    results["OFF"].append(off)
    results["BRICK"].append(brick)
    results["MODULE"].append(module)
    results["SEPARATE"].append(separate)
    print(f"seed {seed}: off={off:.4f}  brick={brick:.4f}({brick-off:+.4f})  "
          f"module-gate={module:.4f}({module-off:+.4f})  separate-readout={separate:.4f}({separate-off:+.4f})")

mean = {k: sum(v) / len(v) for k, v in results.items()}
print(f"\nMEAN: off={mean['OFF']:.4f}  brick={mean['BRICK']:.4f}({mean['BRICK']-mean['OFF']:+.4f})  "
      f"module-gate={mean['MODULE']:.4f}({mean['MODULE']-mean['OFF']:+.4f})  "
      f"separate-readout={mean['SEPARATE']:.4f}({mean['SEPARATE']-mean['OFF']:+.4f})")

brick_deltas = [b - o for b, o in zip(results["BRICK"], results["OFF"])]
module_deltas = [m - o for m, o in zip(results["MODULE"], results["OFF"])]
sep_deltas = [s - o for s, o in zip(results["SEPARATE"], results["OFF"])]
print(f"\nbrick deltas:    {[f'{d:+.4f}' for d in brick_deltas]}  all negative: {all(d<0 for d in brick_deltas)}")
print(f"module deltas:   {[f'{d:+.4f}' for d in module_deltas]}  all negative: {all(d<0 for d in module_deltas)}")
print(f"separate deltas: {[f'{d:+.4f}' for d in sep_deltas]}  all negative: {all(d<0 for d in sep_deltas)}  "
      f"all positive: {all(d>0 for d in sep_deltas)}")

if all(d < 0 for d in brick_deltas) and all(d > 0 for d in sep_deltas):
    print("\nCONFIRMED: excluding consolidation-frozen bricks from the live readout FIXES the harm --")
    print("consistent across all seeds. Jonathan's 'it would work better separate, not part of the")
    print("thinking mesh' hypothesis is directly validated by real, controlled data on the real engine.")
elif all(d < 0 for d in brick_deltas) and all(d < 0 for d in sep_deltas):
    print(f"\nSeparate-readout does NOT fix it either -- still harmful. brick mean "
          f"{mean['BRICK']-mean['OFF']:+.4f} vs separate mean {mean['SEPARATE']-mean['OFF']:+.4f}")
else:
    print("\nMixed/inconsistent -- report raw numbers above, no clean verdict yet.")
