#!/usr/bin/env python3
"""
lucy_bitlevel_repetition_starvation_test.py -- 2026-10-18. DOSE-RESPONSE TEST for finding #1's
second hypothesis, after the first (recognition-mode winner-take-all vs weighted-vote) was
DIRECTLY TESTED AND REFUTED by `lucy_bitlevel_recognition_mode_ab.py` (nearest: 43.8%/45.3%,
graded: 44.4%/41.3% -- statistically the same, ruling out voting style as the cause).

THE SURVIVING LEAD: both recognition modes rely on the SAME underlying `proto_answer` values,
which only update via a slow EMA (`PROTO_LEARN_RATE`), and ONLY when a brick is already "on a
winning path" for that exact call (`my_credit > 0.5`, see sovereign_core.py ~line 1468). The
700-distinct-pattern bit-level task gives each pattern only ~8000/700 ~= 11.4 rehearsals across
the whole run -- far below the numeric task's ~1333 reps/pattern that actually worked tonight.
A plain linear regression fit AFTER training on the same raw brick-firing state reached 58-59%
(condition B, `lucy_bitlevel_combinatorial_readout.py`) -- well above the native ~44%, which
rules out "the task itself is near-chance for everyone," but is fully consistent with "the
NATIVE prototype-learning mechanism specifically needs more rehearsal per pattern than this task
gives it, while an external regression fit over many examples doesn't have that same hunger."

THE TEST: hold EVERYTHING else fixed (RECOGNITION_MODE="nearest", 8000 cycles, same corpus/
encoding) and vary ONLY how many distinct patterns the engine has to learn -- compare the
already-measured 700-pattern run (~11 reps/pattern) against a NEW run on just 50 distinct
patterns (~160 reps/pattern, the SAME total cycle budget). If repetition-starvation is the real
cause, native TRAIN accuracy on the 50-pattern run should climb well above the 700-pattern run's
43.8% -- if it doesn't, this hypothesis is refuted too, and the real cause is still open.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"  # the real default, the one we're actually explaining -- held
                                   # fixed here since the mode A/B test already ruled this out as
                                   # the variable that matters.

N_TRAIN_SMALL = 50     # ~160 reps/pattern across 8000 cycles, vs 700-pattern run's ~11 reps
N_HELDOUT_SMALL = 30   # small held-out set drawn from the same real corpus, for completeness
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)   # SAME seed as the 700-pattern split, for a fair comparison --
# this just takes a smaller slice of the SAME shuffled pool, not a differently-biased sample.
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_SMALL]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_SMALL:N_TRAIN_SMALL + N_HELDOUT_SMALL]


class RepetitionTestCore(sc.SovereignCore):
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


def main():
    log("=" * 78)
    log(f"REPETITION-STARVATION DOSE-RESPONSE TEST -- {N_TRAIN_SMALL} train pairs "
        f"(~{8000//N_TRAIN_SMALL} reps/pattern) vs the earlier 700-pair run (~11 reps/pattern)")
    log(f"RECOGNITION_MODE = 'nearest' (held fixed -- already ruled out as the variable)")
    log("=" * 78)

    random.seed(42)
    core = RepetitionTestCore(init_bricks=sc.INIT_BRICKS)
    for cyc in range(8000):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=None)
            log(f"   cycle {core.current_time}: train (full {len(TRAIN_PAIRS)}) {c}/{t} "
                f"({100*c/t:.1f}%)")

    train_c, train_t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=None)
    held_c, held_t = core.exact_match_accuracy(HELDOUT_PAIRS, n_probe=None)
    log("\n" + "=" * 78)
    log("VERDICT")
    log("=" * 78)
    log(f"   {N_TRAIN_SMALL}-pattern run (~{8000//N_TRAIN_SMALL} reps/pattern): "
        f"train {train_c}/{train_t} ({100*train_c/train_t:.1f}%)  "
        f"held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    log(f"   700-pattern run (~11 reps/pattern, measured earlier): train 43.8%  held-out 45.3%")
    if 100 * train_c / train_t > 43.8 + 10:
        log("   => CONFIRMED (direction): far fewer distinct patterns with far more rehearsal "
            "each recovers real train accuracy. The native readout's below-chance result on the "
            "700-pattern task is consistent with repetition-starved prototype learning, not a "
            "fixed capability ceiling or a recognition-mode bug.")
    else:
        log("   => REFUTED: more rehearsal per pattern did NOT meaningfully help. "
            "Repetition-starvation is not the explanation either -- the real cause is still open.")


if __name__ == "__main__":
    main()
