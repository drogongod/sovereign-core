#!/usr/bin/env python3
"""
lucy_bitlevel_sustained_scoring_check.py -- 2026-10-18. SEVENTH test, but a different KIND of
test than the first six -- this one checks whether my own methodology has been the confound all
along, not the architecture.

THE CATCH: every one of the six readout-mechanism tests tonight (recognition mode, repetition
rate, learned weights, unconstrained combination, frozen population, mini-batching) read
`_read_response()` immediately after a SINGLE post-injection cycle -- exactly the pattern we
already found and fixed once tonight, on the numeric-task transplant test
(`lucy_numeric_task_combinatorial_readout.py`'s `probe_brick_firing_vector`): a single cycle does
not give the relay-delayed signal (PairedRelay's base_delay/back_delay) time to actually reach
and differentiate output-brick firing for a freshly-injected call. SovereignCore's own normal
training interleaves a DIFFERENT random call every single cycle -- so output-brick firing at any
given moment may still be an echo of a stale, previous call, not the one currently paired with
whatever target is being trained against. The external regression that reached 58-59% happened
to reuse the ALREADY-FIXED sustained 8-cycle harvesting method; all six online tests, and the
"native" 43.8%/45.3% baseline itself (`exact_match_accuracy()` also only runs one cycle per
probe), may have been scored under the SAME misalignment the whole time.

THIS TEST: train ONE plain, completely unmodified core (same split, same seed, same 8000
cycles -- no readout override at all). Then score its REAL NATIVE readout TWO ways on the exact
same trained state: (a) single-cycle probe (should reproduce ~43.8%/45.3%, confirming this is
really the same measurement), and (b) SUSTAINED 8-cycle probe (re-inject the SAME call 8 times
before reading, exactly like the fix already proven necessary elsewhere tonight). If (b) jumps
meaningfully above (a), the methodology bug is confirmed and all six earlier "refutations" need
to be redone under fair, sustained scoring before any of them can be trusted.
"""
import sys, os, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"

N_TRAIN_PAIRS = 700
N_HELDOUT_PAIRS = 150
SUSTAIN_CYCLES = 8
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]


class PlainCore(sc.SovereignCore):
    """COMPLETELY UNMODIFIED readout -- no override at all. Only adds the two scoring methods."""
    TASK_PAIRS = TRAIN_PAIRS

    def exact_match_single_cycle(self, pairs, n_probe=None):
        """The scoring method used all night, everywhere -- one cycle per probe."""
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

    def exact_match_sustained(self, pairs, n_probe=None, sustain_cycles=SUSTAIN_CYCLES):
        """THE FIX: re-inject the SAME call sustain_cycles times before reading, giving the
        relay-delayed signal real time to propagate -- the same fix already proven necessary on
        the numeric-task transplant test, applied here to the NATIVE readout directly."""
        probe_set = pairs if n_probe is None or n_probe >= len(pairs) else random.sample(pairs, n_probe)
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in probe_set:
            resp = None
            for _ in range(sustain_cycles):
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
    log("SUSTAINED-SCORING CHECK -- does the NATIVE readout's own accuracy jump when scored with")
    log(f"{SUSTAIN_CYCLES}-cycle sustained presentation instead of a single post-injection cycle?")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = PlainCore(init_bricks=sc.INIT_BRICKS)
    for cyc in range(8000):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_single_cycle(TRAIN_PAIRS, n_probe=500)
            log(f"   cycle {core.current_time}: train (single-cycle, 500-subsample) {c}/{t} "
                f"({100*c/t:.1f}%)")

    log("\nScoring the SAME final trained core two ways...")
    sc_train_c, sc_train_t = core.exact_match_single_cycle(TRAIN_PAIRS, n_probe=500)
    sc_held_c, sc_held_t = core.exact_match_single_cycle(HELDOUT_PAIRS, n_probe=None)
    sus_train_c, sus_train_t = core.exact_match_sustained(TRAIN_PAIRS, n_probe=500)
    sus_held_c, sus_held_t = core.exact_match_sustained(HELDOUT_PAIRS, n_probe=None)

    log("\n" + "=" * 78)
    log("VERDICT")
    log("=" * 78)
    log(f"   single-cycle (the measurement used all night): train {100*sc_train_c/sc_train_t:.1f}%  "
        f"held-out {100*sc_held_c/sc_held_t:.1f}%")
    log(f"   sustained {SUSTAIN_CYCLES}-cycle (the fix):                train "
        f"{100*sus_train_c/sus_train_t:.1f}%  held-out {100*sus_held_c/sus_held_t:.1f}%")
    sus_held_pct = 100 * sus_held_c / sus_held_t
    sc_held_pct = 100 * sc_held_c / sc_held_t
    if sus_held_pct > sc_held_pct + 8:
        log("   => CONFIRMED: single-cycle scoring was undermeasuring the native readout the")
        log("      whole night. All six readout-mechanism tests need to be redone with sustained")
        log("      presentation before their refutations can be trusted.")
    else:
        log("   => REFUTED: sustained scoring does not meaningfully change native accuracy either.")
        log("      This was not the confound -- the real cause is still open.")


if __name__ == "__main__":
    main()
