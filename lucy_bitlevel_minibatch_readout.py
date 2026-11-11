#!/usr/bin/env python3
"""
lucy_bitlevel_minibatch_readout.py -- 2026-10-18. SIXTH test digging into finding #1.

RECAP of all five prior tests, each a real refutation: recognition-mode (nearest vs graded),
repetition rate (11 vs 160 reps/pattern), learned-vs-hand-picked convex weights, unconstrained-
vs-convex combination math, and frozen-vs-churning population -- every single-example-at-a-time
online update, regardless of mechanism, landed in the same ~41-48% band. Test 5 (frozen
population) was CONFOUNDED, not a clean refutation: freezing the population also collapsed the
engine's own TaskCorrect metric to ~0.000, because prototype-learning's `chain_credit` only
propagates from correct responses -- removing evolutionary pressure broke the upstream learning
signal too, not just lin_weight's survival.

THE ONE VARIABLE NONE OF THE FIVE TESTS ISOLATED: every online variant updated its weights after
EVERY SINGLE example, with a small fixed learning rate and no batching or regularization. The
only readout that ever reached 58-59% (the external post-hoc regression,
`lucy_bitlevel_combinatorial_readout.py` condition B) was a BATCH ridge fit over 200 examples at
once. Single-example SGD with a tiny fixed step size is a well-known weak, noisy estimator
compared to a batch/regularized fit, independent of churn, expressivity class, or recognition
mode -- this is a standard, almost mundane ML fact, not a specific bug, and it hasn't been tested
directly yet tonight.

THIS TEST: identical mechanism to test 4 (unconstrained linear combination, same val selection,
same learning rate scale) -- population churn left COMPLETELY NORMAL this time (no sleep
override, avoiding test 5's confound) -- but weight updates now accumulate the gradient
`err * val` over a MINI-BATCH of BATCH_SIZE=25 real training examples, and apply the AVERAGED
update once per batch, instead of updating after every single cycle. If this closes the gap, the
answer to finding #1 is: online local learning CAN match batch regression here, it just needs
batching/averaging to denoise the single-example gradient -- a real, usable fix, not a ceiling.
If it doesn't, the real cause is still open after six tested hypotheses.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"

N_TRAIN_PAIRS = 700
N_HELDOUT_PAIRS = 150
BATCH_SIZE = 25
LIN_LR = 0.02             # larger than test 4's 0.001 -- averaging over a batch denoises the
                           # gradient, so a bigger step is safe and necessary to actually move
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]


class MinibatchReadoutCore(sc.SovereignCore):
    TASK_PAIRS = TRAIN_PAIRS

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._grad_accum = {}   # brick.id -> accumulated (err * val) across the current batch
        self._batch_count = 0

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

    def _accumulate_and_maybe_apply(self, target):
        """Accumulate this cycle's gradient into the batch buffer (keyed by brick id, since
        WHICH bricks fire varies cycle to cycle -- a brick with no accumulated entry yet starts
        at 0). Every BATCH_SIZE cycles, apply the AVERAGED update and clear the buffer -- real
        mini-batch SGD, the standard denoising fix for single-example gradient noise."""
        if target is None or not hasattr(self, "_last_vote_vals"):
            return
        err = float(target) - self._last_resp
        for b, val in self._last_vote_vals:
            self._grad_accum[b.id] = self._grad_accum.get(b.id, 0.0) + err * val
        self._batch_count += 1
        if self._batch_count >= BATCH_SIZE:
            by_id = {b.id: b for b in self.bricks if b.alive}
            for bid, grad_sum in self._grad_accum.items():
                b = by_id.get(bid)
                if b is None:
                    continue   # brick died mid-batch -- its partial gradient is simply dropped,
                                # the same way a real mini-batch drops a sample that's no longer there
                w = getattr(b, "lin_weight", 0.02)
                w += LIN_LR * (grad_sum / BATCH_SIZE)
                b.lin_weight = max(-5.0, min(5.0, w))
            self._grad_accum = {}
            self._batch_count = 0

    def run_cycle(self):
        super().run_cycle()
        self._read_response()
        self._accumulate_and_maybe_apply(getattr(self, "current_target", None))

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
    log(f"MINI-BATCH ONLINE READOUT TEST -- same unconstrained linear readout as test 4, but")
    log(f"weight updates are averaged over batches of {BATCH_SIZE} real examples instead of")
    log(f"applied per single example. Population churn left NORMAL (no sleep override).")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = MinibatchReadoutCore(init_bricks=sc.INIT_BRICKS)
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
    log(f"   mini-batch (size {BATCH_SIZE}) readout: train {train_c}/{train_t} "
        f"({100*train_c/train_t:.1f}%)  held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    log(f"   single-example online (test 4): train 47.8%  held-out 45.3%")
    log(f"   external post-hoc batch regression ceiling: held-out ~58-59%")
    held_pct = 100 * held_c / held_t
    if held_pct > 45.3 + 8:
        log("   => CONFIRMED: batching the gradient closes real ground toward the regression")
        log("      ceiling. Finding #1 explained: single-example SGD noise, not architecture,")
        log("      was the limit -- a usable, buildable fix, not a structural ceiling.")
    else:
        log("   => REFUTED: mini-batching the online update did NOT meaningfully help either.")
        log("      The real cause is still open after six tested hypotheses.")


if __name__ == "__main__":
    main()
