#!/usr/bin/env python3
"""
lucy_bitlevel_readout_mode_linear_test.py -- 2026-10-19. NINTH test, but the first fair one: the
real, first-class READOUT_MODE="linear" engine option (sovereign_core.py, committed 953a9aa),
trained completely normally from scratch for the full 8000 cycles -- no override, no bolt-on, no
extra per-cycle calls. This is the test every one of the eight prior attempts should have been:
let the WHOLE population evolve under the new readout honestly, the same way RECOGNITION_MODE's
two real options always have, instead of hijacking _evaluate_fitness()'s own training signal.

Compares native READOUT_MODE="vote" (the original, measured all night at ~44% train / ~45%
held-out) against READOUT_MODE="linear" (the new evolvable unconstrained combination), same
split, same seed, same 8000 cycles, same scoring.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"

N_TRAIN_PAIRS = 700
N_HELDOUT_PAIRS = 150
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]


class ModeTestCore(sc.SovereignCore):
    TASK_PAIRS = TRAIN_PAIRS

    def exact_match_accuracy(self, pairs, n_probe=None):
        probe_set = pairs if n_probe is None or n_probe >= len(pairs) else random.sample(pairs, n_probe)
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in probe_set:
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone.current_target = float(target)
            clone._update_bricks(); clone._fire_relays()
            resp = clone._read_response()
            predicted = None if resp is None else (BIT_HIGH if resp >= MIDPOINT else BIT_LOW)
            if predicted == target:
                correct += 1
        random.setstate(saved_random_state)
        return correct, len(probe_set)


def run_one(mode):
    sc.READOUT_MODE = mode
    log("\n" + "=" * 78)
    log(f"TRAINING under READOUT_MODE = '{mode}'")
    log("=" * 78)
    random.seed(42)
    core = ModeTestCore(init_bricks=sc.INIT_BRICKS)
    for cyc in range(8000):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
            log(f"   [{mode}] cycle {core.current_time}: train (500-subsample) {c}/{t} ({100*c/t:.1f}%)")
    train_c, train_t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
    held_c, held_t = core.exact_match_accuracy(HELDOUT_PAIRS, n_probe=None)
    log(f"   => FINAL [{mode}]: train {train_c}/{train_t} ({100*train_c/train_t:.1f}%)  "
        f"held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    return train_c, train_t, held_c, held_t


def main():
    log("READOUT_MODE A/B -- the real, first-class engine option, trained from scratch, fair")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")

    vote_r = run_one("vote")
    linear_r = run_one("linear")

    log("\n" + "=" * 78)
    log("VERDICT")
    log("=" * 78)
    log(f"   vote (original):   train {100*vote_r[0]/vote_r[1]:.1f}%  held-out {100*vote_r[2]/vote_r[3]:.1f}%")
    log(f"   linear (new, evolvable): train {100*linear_r[0]/linear_r[1]:.1f}%  held-out {100*linear_r[2]/linear_r[3]:.1f}%")
    log(f"   external post-hoc regression ceiling (for reference): held-out ~58-59%")


if __name__ == "__main__":
    main()
