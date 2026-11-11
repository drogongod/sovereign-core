#!/usr/bin/env python3
"""
lucy_bitlevel_learned_vote_weight.py -- 2026-10-18. THIRD test digging into finding #1.

RECAP, so this file's own reasoning stands on its own: two specific hypotheses for why
SovereignCore's native readout scores ~44-48% (near/below chance=50%) on the real bit-level task,
while a plain linear regression fit AFTER training on the SAME internal brick-firing state reaches
58-59%, were each directly tested and REFUTED tonight:
  1. Recognition-mode winner-take-all vs weighted-vote ("nearest" 43.8/45.3 vs "graded" 44.4/41.3
     -- statistically the same, `lucy_bitlevel_recognition_mode_ab.py`).
  2. Repetition-starved prototype learning (11 reps/pattern vs 160 reps/pattern -- 43.8/45.3 vs
     48.0/46.7, statistically the same, `lucy_bitlevel_repetition_starvation_test.py`).
Both knobs moved; the native readout's accuracy didn't. That stability across two very different
training-dynamics variables points away from "something is broken/undertrained" and toward: the
VOTE WEIGHTS THEMSELVES are the weak link -- `_read_response()`'s real formula,
`w = (b.stability + 0.1) * (b.fitness + 0.1)`, is a HAND-PICKED heuristic for "how much should I
trust this brick's answer," never learned from feedback. The external regression test proved a
LEARNED weighting of the exact same per-brick signals does much better. This is the same
principle already named tonight for Wolfpack and for lateral inhibition:
"the parameters are never ours to pick" (`[[sovereigncore_true_design_philosophy]]`).

THIS TEST: give each output-module brick its OWN evolvable vote-weight (`b.vote_weight`, starts
at 1.0, exists ONLY in this subclass -- sovereign_core.py itself is not modified), and update it
ONLINE, every cycle, with a tiny real-feedback delta rule: after `_read_response()` computes the
organism's answer and we know the true target (either from real interleaved training or a
probe), each firing output brick's vote_weight moves UP if ITS OWN individual predicted value was
close to the true target, and DOWN if it was far off -- the same "trust the ones who get it
right, distrust the ones who don't" idea the hand-picked stability*fitness formula was already
GROPING toward, just finally made to learn from real outcomes instead of guessing.

If this closes most of the gap to the ~58-59% regression ceiling, the native-readout ceiling IS
explained: hand-picked trust weights, now fixed by making them evolvable, matching the exact
principle this whole project has been converging on tonight. If it doesn't, the real cause is
still open and this is a third clean refutation, recorded honestly either way.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"   # already shown not to matter -- held fixed for comparability

N_TRAIN_PAIRS = 700      # SAME split as every other bit-level test tonight, for direct comparison
N_HELDOUT_PAIRS = 150
VOTE_LR = 0.05            # learning rate for the online vote-weight delta rule
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0
SPAN = float(BIT_HIGH - BIT_LOW)   # for normalizing per-brick error into a [0,1]-ish learning signal


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)   # identical split to every other bit-level test tonight
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]


class LearnedVoteWeightCore(sc.SovereignCore):
    TASK_PAIRS = TRAIN_PAIRS

    def _read_response(self):
        """OVERRIDE of sovereign_core.py's real _read_response() -- same firing-gate and
        recognizer-vs-non-recognizer value selection logic, but the TRUST WEIGHT per brick is
        now `b.vote_weight` (an evolvable scalar, learned below) instead of the hand-picked
        `(stability+0.1)*(fitness+0.1)` formula. Seed/firmware bricks keep their real 50x boost
        (that part isn't in question -- the seed SHOULD dominate, it's the firmware). Recognition-
        mode's "nearest" shortcut is intentionally NOT reproduced here -- this test isolates the
        vote-WEIGHTING question specifically, already shown not to interact with recognition
        mode in the two earlier refutations.
        """
        out_bricks = [b for b in self.bricks if b.alive and b.module_id == self.output_module_id
                      and b.fired_this_cycle]
        if not out_bricks:
            return None
        num = 0.0; den = 0.0
        for b in out_bricks:
            w = getattr(b, "vote_weight", 1.0)
            if b.id in self.seed_brick_ids:
                w *= 50.0
            val = b.proto_answer if (b.proto_answer is not None and b.prototype is not None) else b.predict_next()
            num += w * val; den += w
        self._last_out_bricks_and_vals = [(b, (b.proto_answer if (b.proto_answer is not None and
                                           b.prototype is not None) else b.predict_next()))
                                           for b in out_bricks]
        return (num / den) if den > 0 else None

    def _update_vote_weights(self, target):
        """THE LEARNING STEP: called right after _read_response(), only when the true target is
        known (real training cycles always know it; probes explicitly set current_target too).
        Each voting brick's OWN individual value is compared to the true target -- close ->
        vote_weight nudged up, far -> nudged down. Multiplicative update, floor at 0.05 so a
        brick is never fully silenced (consistent with the project's "redundancy as fault
        tolerance" principle, `[[sovereigncore_true_design_philosophy]]`) and never unbounded.
        """
        if target is None or not hasattr(self, "_last_out_bricks_and_vals"):
            return
        for b, val in self._last_out_bricks_and_vals:
            err = abs(val - target) / SPAN                 # in [0, ~1] for in-range values
            direction = 1.0 + VOTE_LR * (1.0 - 2.0 * min(err, 1.0))  # err=0 -> boost, err=1 -> cut
            vw = getattr(b, "vote_weight", 1.0) * direction
            b.vote_weight = max(0.05, min(20.0, vw))

    def run_cycle(self):
        super().run_cycle()
        # FOUND BY READING THE REAL CODE, NOT ASSUMED: run_cycle() itself never calls
        # _read_response() during normal training -- that only happens inside the rare,
        # disabled-by-default %500 DIAGNOSTIC_PROBE_ENABLED block (sovereign_core.py ~2062).
        # Without this explicit call, vote_weight would sit at its 1.0 default for the entire
        # run and never receive a single real learning signal -- the test would have silently
        # measured nothing. Call it explicitly every cycle, using the SAME current_call/
        # current_target this cycle's inject_problem() already set at the top of
        # super().run_cycle(), so the learning step sees fresh, real per-cycle outcomes.
        self._read_response()
        self._update_vote_weights(getattr(self, "current_target", None))

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
    log("LEARNED VOTE-WEIGHT TEST -- does making the readout's trust weights evolvable (instead")
    log("of hand-picked stability*fitness) close the gap to the ~58-59% regression ceiling?")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out, same split as every other")
    log("bit-level test tonight. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = LearnedVoteWeightCore(init_bricks=sc.INIT_BRICKS)
    for cyc in range(8000):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
            log(f"   cycle {core.current_time}: train (500-subsample) {c}/{t} ({100*c/t:.1f}%)")

    train_c, train_t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
    held_c, held_t = core.exact_match_accuracy(HELDOUT_PAIRS, n_probe=None)
    log("\n" + "=" * 78)
    log("VERDICT")
    log("=" * 78)
    log(f"   learned vote-weight readout: train {train_c}/{train_t} ({100*train_c/train_t:.1f}%)  "
        f"held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    log(f"   native (hand-picked weights, measured earlier): train 43.8%  held-out 45.3%")
    log(f"   external regression ceiling (measured earlier): held-out ~58-59%")
    held_pct = 100 * held_c / held_t
    if held_pct > 45.3 + 8:
        log("   => CONFIRMED (direction): making the vote weights evolvable recovers real "
            "accuracy over the hand-picked formula. The native-readout ceiling was the "
            "hand-picked trust weights, not a deeper limit -- matches the 'parameters are never "
            "ours to pick' principle exactly.")
    else:
        log("   => REFUTED or inconclusive: learned vote weights alone did not meaningfully beat "
            "the hand-picked formula. The real cause is still open after three tested hypotheses.")


if __name__ == "__main__":
    main()
