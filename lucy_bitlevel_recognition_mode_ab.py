#!/usr/bin/env python3
"""
lucy_bitlevel_recognition_mode_ab.py -- 2026-10-18. DIGGING INTO FINDING #1 from
lucy_bitlevel_combinatorial_readout.py: SovereignCore's own native readout scored BELOW CHANCE
(train 43.8%, held-out 45.3%, chance=50%) on the real bit-level task, while a plain linear
readout on the SAME internal brick states reached 58-59%. That gap needed a real mechanism, not
a shrug -- this is that mechanism, found by reading the actual live code, not assumed.

THE SUSPECT, confirmed directly in sovereign_core.py: `RECOGNITION_MODE = "nearest"` is the real
module-level DEFAULT (line 449) -- no test script tonight ever overrides it. Under "nearest",
`_read_response()` (lines 1065-1068) takes a pure WINNER-TAKE-ALL shortcut: among firing
output-module bricks that have a learned prototype, it picks the SINGLE one with the SMALLEST
Euclidean distance between its prototype and the CURRENT call, and returns THAT brick's answer
outright -- no averaging, no robustness, no second opinion.

WHY THIS SHOULD BE SPECIFICALLY BAD on a bit-level lookup task: Euclidean distance over a raw
16-dimensional {0, STATE_MAX} bit vector treats "differs in exactly 1 bit" as a SMALL distance --
but on a genuine lookup/parity-shaped target (this task's real structure, see
`[[combinatorial_expansion_missing_ingredient]]`), the single bit that differs between two
context windows is routinely the ONE bit that determines a completely different correct answer.
Nearest-neighbor-by-raw-distance is making the exact same "similar input -> similar output"
assumption a linear readout makes, and failing for the same underlying reason -- the XOR problem,
wearing a different hat. This is a real, well-grounded HYPOTHESIS, not yet proven -- this script
is the decisive, cheap test: SovereignCore ALREADY HAS a second, built-in readout mode,
`RECOGNITION_MODE = "graded"` (RBF-weighted vote across ALL recognizing bricks, not winner-take-
all), sitting completely unused by every test tonight because nothing ever set it. Flip that ONE
existing flag, retrain under the IDENTICAL seed/task/split, and see whether below-chance becomes
above-chance. No new mechanism built -- just finally exercising code that was already there.

METHOD: train TWO separate instances of the exact same bit-level task (same 700/150 train/held-
out split as the combinatorial-readout test, same seed=42, same 8000 cycles) -- one under
RECOGNITION_MODE="nearest" (recap of the suspect default) and one under RECOGNITION_MODE="graded"
(the candidate fix) -- and compare native exact-match on train AND held-out, head to head.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False  # proven baseline -- same discipline as every test tonight


def log(*a):
    print(*a); sys.stdout.flush()


# ---------------------------------------------------------------------------------------------
# IDENTICAL split to lucy_bitlevel_combinatorial_readout.py (same seed=1234, same sizes) so this
# comparison sits on the exact same train/held-out pairs as that test, directly comparable.
# ---------------------------------------------------------------------------------------------
N_TRAIN_PAIRS = 700
N_HELDOUT_PAIRS = 150
_split_rng = random.Random(1234)
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


class RecogModeCore(sc.SovereignCore):
    TASK_PAIRS = TRAIN_PAIRS

    def exact_match_accuracy(self, pairs, n_probe=None):
        # same real probe-isolation fix as every test tonight: throwaway deepcopy + global-RNG
        # save/restore, so recapping the native readout can never mutate the live trained core.
        probe_set = pairs if n_probe is None or n_probe >= len(pairs) else random.sample(pairs, n_probe)
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in probe_set:
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone.current_target = float(target)   # BUG7-style fix: held-out calls aren't in
            # clone.TASK_PAIRS, so inject_problem()'s dict lookup would silently default target=0
            # for them -- override with the REAL target before scoring.
            clone._update_bricks(); clone._fire_relays()
            resp = clone._read_response()
            predicted = None if resp is None else (BIT_HIGH if resp >= MIDPOINT else BIT_LOW)
            if predicted == target:
                correct += 1
        random.setstate(saved_random_state)
        return correct, len(probe_set)


def run_one(mode_label, recognition_mode, cycles=8000):
    sc.RECOGNITION_MODE = recognition_mode
    log("\n" + "=" * 78)
    log(f"TRAINING under RECOGNITION_MODE = '{recognition_mode}'  ({mode_label})")
    log("=" * 78)
    random.seed(42)   # identical seed for both runs -- same training trajectory shape, only the
                       # readout mode differs, so any accuracy gap is attributable to that flag.
    core = RecogModeCore(init_bricks=sc.INIT_BRICKS)
    for cyc in range(cycles):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
            log(f"   [{recognition_mode}] cycle {core.current_time}: train (500-subsample) "
                f"{c}/{t} ({100*c/t:.1f}%)")
    train_c, train_t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
    held_c, held_t = core.exact_match_accuracy(HELDOUT_PAIRS, n_probe=None)
    log(f"   => FINAL [{recognition_mode}]: train {train_c}/{train_t} "
        f"({100*train_c/train_t:.1f}%)  held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    return train_c, train_t, held_c, held_t


def main():
    log("RECOGNITION_MODE A/B TEST -- same bit-level task, same split, same seed, one flag differs")
    log(f"{len(TRAIN_PAIRS)} train pairs, {len(HELDOUT_PAIRS)} held-out pairs. Chance = 50%.")

    nearest_train_c, nearest_train_t, nearest_held_c, nearest_held_t = run_one(
        "SUSPECT DEFAULT -- winner-take-all nearest-prototype", "nearest")
    graded_train_c, graded_train_t, graded_held_c, graded_held_t = run_one(
        "CANDIDATE FIX -- RBF-weighted vote across all recognizers", "graded")

    log("\n" + "=" * 78)
    log("VERDICT")
    log("=" * 78)
    log(f"   nearest (default): train {100*nearest_train_c/nearest_train_t:.1f}%  "
        f"held-out {100*nearest_held_c/nearest_held_t:.1f}%")
    log(f"   graded  (fix)     : train {100*graded_train_c/graded_train_t:.1f}%  "
        f"held-out {100*graded_held_c/graded_held_t:.1f}%")
    if graded_held_c / graded_held_t > nearest_held_c / nearest_held_t + 0.03:
        log("   => CONFIRMED: switching off winner-take-all nearest-prototype matching recovers "
            "real accuracy on this task. The below-chance result was this mechanism, not a "
            "capability ceiling.")
    elif nearest_held_c / nearest_held_t > graded_held_c / graded_held_t + 0.03:
        log("   => REFUTED: nearest mode was actually BETTER. The below-chance result has a "
            "different cause -- recognition-mode winner-take-all is not it.")
    else:
        log("   => INCONCLUSIVE: both modes land in the same range. The below-chance result is "
            "likely NOT explained by winner-take-all vs. graded voting alone.")


if __name__ == "__main__":
    main()
