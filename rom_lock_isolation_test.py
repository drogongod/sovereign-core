#!/usr/bin/env python3
"""
rom_lock_isolation_test.py -- 2026-10-19. ROM_LOCK_ENABLED bundled two mechanisms that were never tested
apart: FAST->SLOW signal injection (ROM_LOCK_INJECTION_ENABLED) and the freeze/consolidation bookkeeping
itself (ROM_LOCK_FREEZE_ENABLED). All 4 tests so far (brick-level, module-gate, readout-separation,
depth-tradeoff) used them bundled together. This isolates which one (if either alone, or only the
combination) actually drives the measured harm. Same controlled methodology: 3 seeds, same seed both
conditions per trial.
"""
import random
import numpy as np
import sovereign_core as sc

N_CYCLES = 1500
SEEDS = [1, 2, 3]


def run_one(freeze: bool, inject: bool, seed: int) -> float:
    sc.ROM_LOCK_FREEZE_ENABLED = freeze
    sc.ROM_LOCK_INJECTION_ENABLED = inject
    sc.ROM_LOCK_MODULE_GATE_ENABLED = False
    sc.ROM_LOCK_SEPARATE_READOUT_ENABLED = False
    sc.INIT_BRICKS = 150
    random.seed(seed)
    np.random.seed(seed)
    core = sc.SovereignCore()
    for _ in range(N_CYCLES):
        core.run_cycle()
    return core._wc_avg if hasattr(core, "_wc_avg") else float("nan")


CONDITIONS = [
    ("OFF (neither)",        False, False),
    ("FREEZE ONLY",          True,  False),
    ("INJECTION ONLY",       False, True),
    ("BOTH (orig ROM_LOCK)", True,  True),
]

results = {name: [] for name, _, _ in CONDITIONS}
for seed in SEEDS:
    row = []
    for name, freeze, inject in CONDITIONS:
        val = run_one(freeze, inject, seed)
        results[name].append(val)
        row.append(f"{name}={val:.4f}")
    print(f"seed {seed}: " + "  ".join(row))

print("\n" + "=" * 70)
print("MEANS across 3 seeds")
print("=" * 70)
off_mean = float(np.mean(results["OFF (neither)"]))
for name, _, _ in CONDITIONS:
    m = float(np.mean(results[name]))
    print(f"{name:24s}: {m:.4f}  (delta vs OFF: {m - off_mean:+.4f})")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
freeze_deltas = [f - o for f, o in zip(results["FREEZE ONLY"], results["OFF (neither)"])]
inject_deltas = [i - o for i, o in zip(results["INJECTION ONLY"], results["OFF (neither)"])]
both_deltas = [b - o for b, o in zip(results["BOTH (orig ROM_LOCK)"], results["OFF (neither)"])]
print(f"freeze-only deltas:    {[f'{d:+.4f}' for d in freeze_deltas]}  all negative: {all(d<0 for d in freeze_deltas)}")
print(f"injection-only deltas: {[f'{d:+.4f}' for d in inject_deltas]}  all negative: {all(d<0 for d in inject_deltas)}")
print(f"both deltas:           {[f'{d:+.4f}' for d in both_deltas]}  all negative: {all(d<0 for d in both_deltas)}")

freeze_harmful = all(d < 0 for d in freeze_deltas)
inject_harmful = all(d < 0 for d in inject_deltas)
if freeze_harmful and not inject_harmful:
    print("\nCONFIRMED: the FREEZE/consolidation bookkeeping is the harmful piece -- injection alone is")
    print("not (consistently) harmful. The harm comes from freezing bricks, not from signal injection.")
elif inject_harmful and not freeze_harmful:
    print("\nCONFIRMED: the FAST->SLOW INJECTION is the harmful piece -- freeze bookkeeping alone is not")
    print("(consistently) harmful. The harm comes from injecting signal, not from the freeze mechanism.")
elif freeze_harmful and inject_harmful:
    print("\nBOTH pieces are independently harmful -- the harm is not concentrated in either alone, it is")
    print("a property of each mechanism separately, not just their combination.")
else:
    print("\nNeither piece alone is consistently harmful -- reporting raw numbers, the harm may require")
    print("the SPECIFIC COMBINATION/interaction of both, or be inconsistent at this scale.")
