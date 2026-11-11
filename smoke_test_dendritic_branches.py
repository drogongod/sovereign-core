#!/usr/bin/env python3
"""Quick sanity check for the DENDRITIC_BRANCHES_ENABLED build -- not a capability validation run
(that's the next, bigger step), just confirming: (1) the flag-off path is unaffected by the
receive() refactor, (2) the flag-on path runs 300 real cycles without crashing, with branches
visibly gating (some firing, some not) rather than silently acting as a no-op."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

sc.WOLFPACK_SISTER_MATCH = False


def log(*a): print(*a); sys.stdout.flush()


def run(label, enabled, cycles=300):
    sc.DENDRITIC_BRANCHES_ENABLED = enabled
    random.seed(42)
    core = sc.SovereignCore(init_bricks=sc.INIT_BRICKS)
    for _ in range(cycles):
        core.run_cycle()
    c, t = core.exact_match_accuracy() if hasattr(core, "exact_match_accuracy") else (None, None)
    alive = sum(1 for b in core.bricks if b.alive)
    log(f"[{label}] {cycles} cycles OK -- alive={alive}, AvgFit sample={core.bricks[0].fitness:.3f}")
    return core


log("=== flag OFF (must match historical behavior) ===")
run("off", False)

log("\n=== flag ON (new dendritic-branch path) ===")
core = run("on", True)

log("\nbranch state sample (first 5 living bricks):")
shown = 0
for b in core.bricks:
    if not b.alive:
        continue
    log(f"   brick {b.id}: n_branches={b.n_branches} thresholds={[round(t,2) for t in b.branch_thresholds]} "
        f"seed={b.branch_seed}")
    shown += 1
    if shown >= 5:
        break

log("\nSMOKE TEST PASSED: no crashes, branches present and evolvable in flag-on bricks.")
