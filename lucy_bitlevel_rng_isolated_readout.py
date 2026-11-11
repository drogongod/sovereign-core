#!/usr/bin/env python3
"""
lucy_bitlevel_rng_isolated_readout.py -- 2026-10-19. EIGHTH test digging into finding #1, but
this one fixes a REAL bug found in my own methodology for tests 3-6, not a new architectural
hypothesis.

THE BUG, found by comparing TaskCorrect trajectories across tests, not assumed: tests 3
(learned vote weight), 4 (unconstrained linear), 5 (frozen population), and 6 (mini-batch) all
override `run_cycle()` to call an EXTRA `self._read_response()` every single cycle, on top of
whatever the real engine's own run_cycle() does. `_read_response()` calls `predict_next()`,
which draws `random.uniform(-0.3, 0.3)` as its noise term -- a real, intentional part of the
design. But every EXTRA call to it consumes from the SAME global `random` module state that
drives every other probabilistic decision in the real engine (mutation, splitting, firing
thresholds, crossover) -- desynchronizing the entire rest of that cycle's, and every subsequent
cycle's, evolutionary dynamics from what an unmodified run would do. Confirmed directly: test 7
(completely unmodified core, no extra _read_response() call) shows a healthy TaskCorrect climb
(0.185 at cyc1000 -> 0.425 at cyc8000); tests 4 and 6 (extra call, no RNG isolation) show
TaskCorrect stuck at ~0.000 for THOUSANDS of cycles before limping upward late. Tests 1 and 2
never touched run_cycle() or called an extra _read_response() -- they are UNAFFECTED by this bug,
their refutations still stand. Tests 3, 4, 5, 6 do NOT -- none of those four refutations can be
trusted as measured.

THE FIX, the same discipline every probe/scoring method in this whole project already uses
(exact_match_accuracy(), probe_brick_firing_vector(), etc.): save the global random state before
the extra diagnostic/learning read, and restore it immediately after, so the extra call can
never leak into the real training's random sequence.

THIS TEST: re-run test 4's exact mechanism (unconstrained online linear combination, same LR,
same val selection) with this ONE fix applied -- isolate the extra _read_response()+weight-
update call from the live random state. If TaskCorrect now climbs normally (matching test 7's
healthy trajectory) AND held-out accuracy improves toward the ~58-59% ceiling, the bug is
confirmed as the real explanation for all four earlier "refutations." If TaskCorrect looks normal
but accuracy still doesn't improve, the RNG-contamination bug is real and fixed, but it wasn't
the explanation for the readout gap specifically -- a cleaner, still-open negative result.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"

N_TRAIN_PAIRS = 700
N_HELDOUT_PAIRS = 150
LIN_LR = 0.001
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]


class RngIsolatedReadoutCore(sc.SovereignCore):
    TASK_PAIRS = TRAIN_PAIRS

    def _read_response(self):
        out_bricks = [b for b in self.bricks if b.alive and b.module_id == self.output_module_id
                      and b.fired_this_cycle]
        if not out_bricks:
            return None
        resp = 0.0
        vals = []
        for b in out_bricks:
            w = getattr(b, "lin_weight", 0.02)
            val = b.proto_answer if (b.proto_answer is not None and b.prototype is not None) else b.predict_next()
            resp += w * val
            vals.append((b, val))
        self._last_vote_vals = vals
        self._last_resp = resp
        return resp

    def _update_linear_weights(self, target):
        if target is None or not hasattr(self, "_last_vote_vals"):
            return
        err = float(target) - self._last_resp
        for b, val in self._last_vote_vals:
            w = getattr(b, "lin_weight", 0.02)
            w += LIN_LR * err * val
            b.lin_weight = max(-5.0, min(5.0, w))

    def run_cycle(self):
        super().run_cycle()
        # THE FIX: save/restore the global random state around the extra diagnostic/learning
        # call, so _read_response()'s internal predict_next() noise draws can NEVER leak into
        # the real training's random sequence -- the same isolation discipline every probe in
        # this project already uses, just missing here in tests 3-6 until now.
        saved_random_state = random.getstate()
        self._read_response()
        self._update_linear_weights(getattr(self, "current_target", None))
        random.setstate(saved_random_state)

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
    log("RNG-ISOLATED UNCONSTRAINED READOUT -- same mechanism as test 4, but the extra")
    log("per-cycle _read_response()+weight-update call no longer leaks into the real training's")
    log("random sequence. Watch TaskCorrect below -- it should climb normally this time if the")
    log("RNG-contamination bug was real.")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = RngIsolatedReadoutCore(init_bricks=sc.INIT_BRICKS)
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
    log(f"   RNG-isolated unconstrained readout: train {train_c}/{train_t} "
        f"({100*train_c/train_t:.1f}%)  held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    log(f"   same mechanism, RNG-CONTAMINATED (test 4): train 47.8%  held-out 45.3%")
    log(f"   external post-hoc batch regression ceiling: held-out ~58-59%")
    held_pct = 100 * held_c / held_t
    if held_pct > 45.3 + 8:
        log("   => CONFIRMED: the RNG-contamination bug was the real explanation for tests 3-6's")
        log("      refutations. Fixing it recovers real accuracy toward the regression ceiling.")
    else:
        log("   => The RNG bug is real and fixed (check TaskCorrect above), but accuracy still")
        log("      did not meaningfully improve -- the real cause is still open after eight")
        log("      tested hypotheses.")


if __name__ == "__main__":
    main()
