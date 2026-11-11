#!/usr/bin/env python3
"""
lucy_bitlevel_unconstrained_readout.py -- 2026-10-18. FOURTH test digging into finding #1, and
an encoding sanity check run alongside it (see the standalone data-check this session that
preceded this file: only 8.0% of the real bit-level corpus's contexts are genuinely ambiguous,
and the dict's stored target agrees with 96.0% of all real occurrences -- the ~97% ceiling is
far above anything measured on any readout tonight, so the task's own ground truth is NOT the
explanation for the ~44-59% band every readout variant has landed in. Ruled out, not assumed.)

RECAP of the readout investigation: three hypotheses tested and refuted in a row tonight --
recognition-mode winner-take-all vs weighted-vote (43.8/45.3 vs 44.4/41.3), repetition rate
(11 reps/pattern vs 160 reps/pattern -- 43.8/45.3 vs 48.0/46.7), and online-LEARNED vote weights
replacing the hand-picked stability*fitness formula (41.4/43.3 -- no better). All three land in
the same ~41-48% band, while an EXTERNAL regression readout fit on the same internal brick-firing
features reached 58-59%. The thing all three refuted attempts share: they're all still a
WEIGHTED AVERAGE, `sum(w_i * val_i) / sum(w_i)` -- mathematically confined to the convex
combination of whatever the individual bricks already report, no matter how the weights `w_i`
are chosen. The external regression that worked was never constrained that way -- it fits an
UNCONSTRAINED linear combination (negative weights allowed, no sum-normalization), a strictly
more expressive function class.

THIS TEST isolates exactly that one remaining variable: same per-brick `val` selection
(proto_answer if recognized, else predict_next() -- unchanged from every earlier version), same
online per-cycle learning (unchanged from the vote-weight test), but the combination rule is now
a genuine delta-rule-trained LINEAR READOUT -- `resp = sum(w_i * val_i)`, NO division by
sum(w_i), weights free to go negative, updated by the standard LMS rule
`w_i += lr * (target - resp) * val_i` every cycle. If THIS closes the gap to ~58-59%, finding #1
is fully explained: the native readout's weighted-AVERAGE form itself was the ceiling, not the
weight values. If it doesn't, the real cause survives a fourth refutation and is still open.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"   # already shown not to matter -- held fixed for comparability

N_TRAIN_PAIRS = 700
N_HELDOUT_PAIRS = 150
LIN_LR = 0.001            # LMS learning rate -- small, because val's scale is ~0-31 (STATE_MAX)
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)   # identical split to every other bit-level test tonight
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]


class UnconstrainedReadoutCore(sc.SovereignCore):
    TASK_PAIRS = TRAIN_PAIRS

    def _read_response(self):
        """OVERRIDE: same firing-gate and val-selection logic as the real engine and every
        earlier version of this test, but the combination rule is now an UNCONSTRAINED linear
        sum -- `sum(w_i * val_i)`, no division by sum(w_i), weights free to be negative. This is
        the ONE variable this test isolates; everything else (which bricks vote, what value each
        one offers) is unchanged from the vote-weight test."""
        out_bricks = [b for b in self.bricks if b.alive and b.module_id == self.output_module_id
                      and b.fired_this_cycle]
        if not out_bricks:
            return None
        resp = 0.0
        vals = []
        for b in out_bricks:
            w = getattr(b, "lin_weight", 0.02)   # small positive init -- unconstrained but not
            # starting at 0 (which would give zero gradient signal to every weight on cycle 1)
            val = b.proto_answer if (b.proto_answer is not None and b.prototype is not None) else b.predict_next()
            resp += w * val
            vals.append((b, val))
        self._last_vote_vals = vals
        self._last_resp = resp
        return resp

    def _update_linear_weights(self, target):
        """Standard LMS delta rule: w_i += lr * (target - resp) * val_i. This is EXACTLY the
        same update rule the external ridge/delta-rule regression used tonight on Flybrain and
        in the earlier post-hoc SovereignCore probes -- just applied online, one real example at
        a time, instead of as a batch fit."""
        if target is None or not hasattr(self, "_last_vote_vals"):
            return
        err = float(target) - self._last_resp
        for b, val in self._last_vote_vals:
            w = getattr(b, "lin_weight", 0.02)
            w += LIN_LR * err * val
            b.lin_weight = max(-5.0, min(5.0, w))   # bounded only to prevent runaway divergence,
            # NOT to enforce positivity or normalization -- negative weights are the whole point.

    def run_cycle(self):
        super().run_cycle()
        # same reasoning as the vote-weight test: run_cycle() never calls _read_response() on its
        # own during normal training, so this explicit call+update is required for the linear
        # readout to receive any real learning signal at all.
        self._read_response()
        self._update_linear_weights(getattr(self, "current_target", None))

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
    log("UNCONSTRAINED LINEAR READOUT TEST -- removes the convex-weighted-average constraint")
    log("entirely (negative weights allowed, no normalization), online delta-rule trained")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = UnconstrainedReadoutCore(init_bricks=sc.INIT_BRICKS)
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
    log(f"   unconstrained linear readout: train {train_c}/{train_t} ({100*train_c/train_t:.1f}%)  "
        f"held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    log(f"   native (hand-picked weighted average): train 43.8%  held-out 45.3%")
    log(f"   learned-weight weighted average (still convex): train 41.4%  held-out 43.3%")
    log(f"   external post-hoc regression ceiling: held-out ~58-59%")
    held_pct = 100 * held_c / held_t
    if held_pct > 45.3 + 8:
        log("   => CONFIRMED: removing the convex-average constraint (not just learning the")
        log("      weights) recovers real accuracy. Finding #1 fully explained: the weighted-")
        log("      AVERAGE form itself was the ceiling, independent of weight quality.")
    else:
        log("   => REFUTED or inconclusive: the real cause survives a fourth test and is still")
        log("      open -- the expressivity-class theory does not hold up under direct test.")


if __name__ == "__main__":
    main()
