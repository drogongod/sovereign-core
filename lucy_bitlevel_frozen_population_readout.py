#!/usr/bin/env python3
"""
lucy_bitlevel_frozen_population_readout.py -- 2026-10-18. FIFTH test digging into finding #1.

RECAP: test 4 (lucy_bitlevel_unconstrained_readout.py) used the EXACT SAME mathematical form as
the external post-hoc regression that reached 58-59% held-out (unconstrained linear combination,
negative weights allowed, no normalization) -- trained ONLINE instead of as a batch fit -- and
still landed at 47.8%/45.3%, the same ~41-48% band every online readout variant has hit tonight.
That refuted "expressivity class" as the explanation, since the math was identical.

THE REAL DIFFERENCE, found by reading the engine's own cloning code directly
(sovereign_core.py's `_run_sleep_dag`, both the culled-slot-swap path and the dead-slot-fill
path): every sleep event culls and clones over a hundred bricks, explicitly copying `mem`,
`think`, `zone`, `prototype`, `proto_answer`, `synapses`, `relays` from winner to new slot -- but
NEVER `lin_weight`/`vote_weight`, because those don't exist in the real Brick class at all, only
as attributes this test's own subclass adds dynamically via getattr-with-default. Every clone
silently resets to the default weight, discarding whatever that slot's predecessor had learned.
The external post-hoc regression never faced this because it fits ALL its weights ONCE on a
single frozen snapshot, after training has already happened -- no churn during the fit itself.

THIS TEST isolates exactly that confound: run the IDENTICAL unconstrained online linear readout
mechanism from test 4, but with `_run_sleep_dag()` overridden to do ONLY its essential, harmless
bookkeeping (reset context_tokens so the engine doesn't stall) and SKIP all culling, cloning, and
growth entirely -- freezing the brick population for the whole run. If this closes the gap to
~58-59%, churn-driven weight-reset is confirmed as the real cause. If it doesn't, the theory is
wrong and the real cause is still open after five tested hypotheses.

HONEST LIMITATION, stated up front: freezing the population changes more than just "does
lin_weight survive" -- it also removes the engine's normal fitness-driven selection pressure for
the WHOLE run, so the population's overall quality may differ from a normally-evolving run for
reasons unrelated to the churn hypothesis. This is a clean test of the NARROW claim (stable
per-brick weights CAN converge, if nothing resets them), not a claim that frozen populations are
otherwise equivalent to evolving ones.
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


class FrozenPopulationReadoutCore(sc.SovereignCore):
    TASK_PAIRS = TRAIN_PAIRS

    def _run_sleep_dag(self):
        """OVERRIDE: the real _run_sleep_dag() culls/clones/grows the brick population -- the
        exact mechanism that resets lin_weight on every churned slot. Skip all of that, keep
        only the harmless bookkeeping (context reset) so the engine doesn't stall waiting for
        sleep to 'complete.' This is a deliberate, named ablation, not a bug -- freezing the
        population IS the experiment."""
        self.context_tokens = 0
        self.is_sleeping = False
        self._last_sleep_cycle = self.current_time

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
    log("FROZEN-POPULATION READOUT TEST -- same unconstrained linear readout as test 4, but")
    log("sleep-driven culling/cloning/growth is DISABLED so lin_weight is never reset mid-run")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = FrozenPopulationReadoutCore(init_bricks=sc.INIT_BRICKS)
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
    log(f"   frozen-population unconstrained readout: train {train_c}/{train_t} "
        f"({100*train_c/train_t:.1f}%)  held-out {held_c}/{held_t} ({100*held_c/held_t:.1f}%)")
    log(f"   same readout, CHURNING population (test 4): train 47.8%  held-out 45.3%")
    log(f"   external post-hoc regression ceiling: held-out ~58-59%")
    held_pct = 100 * held_c / held_t
    if held_pct > 45.3 + 8:
        log("   => CONFIRMED: freezing the population (removing weight-reset-on-clone) recovers")
        log("      real accuracy. Finding #1 fully explained: churn resetting per-brick learned")
        log("      readout weights before they can converge was the real cause all along.")
    else:
        log("   => REFUTED: freezing the population did NOT meaningfully help either. The churn")
        log("      theory does not hold up under direct test -- the real cause is still open")
        log("      after five tested hypotheses.")


if __name__ == "__main__":
    main()
