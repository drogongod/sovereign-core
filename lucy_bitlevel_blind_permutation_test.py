#!/usr/bin/env python3
"""
lucy_bitlevel_blind_permutation_test.py -- 2026-10-19. Fixes a real label-leakage bug found by
re-examining the permutation test's suspiciously perfect 100% result (lucy_bitlevel_permutation_test.py).

THE BUG: `probe_brick_firing_vector()` set `clone.current_target = float(target)` (the REAL,
correct answer) every cycle of the 8-cycle sustain loop, for every probed example, including
held-out ones the network never trained on. That target isn't passive -- `_update_bricks()` feeds
it into `update_prediction_error()`, which sets `b.prediction_error`, which `_fire_relays()` reads
to decide whether a relay splits and delivers extra signal to a sister brick. So the very process
meant to measure "what does the substrate's own internal state say, blind" was handing the engine
the answer key every cycle and letting its real error-driven relay-splitting mechanism act on it
live. That's not recall -- that's leaking the target into the measurement itself. ChatGPT flagged
the same underlying failure mode hours earlier in a different context ("that's label leakage into
inference") -- the fix wasn't carried into this harvesting pipeline until now.

THE FIX: harvest features completely blind. `current_target = None` for the entire sustain
window -- `update_prediction_error()` falls back to `b.mem` (per its own existing `tgt if tgt is
not None else b.mem` logic) instead of the real answer, so prediction-error-driven relay
splitting can never see the target during measurement. Everything else (same split, same seed,
same sustain cycles, same ridge/CV methodology, same permutation-test design) is identical to
lucy_bitlevel_permutation_test.py, so any difference in the result is attributable to this one
fix.
"""
import sys, os, random, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False
sc.RECOGNITION_MODE = "nearest"

N_TRAIN_PAIRS = 700
N_HELDOUT_PAIRS = 150
PROBE_TRAIN_SUBSAMPLE = 200
PROBE_HELDOUT_SUBSAMPLE = 100
SUSTAIN_CYCLES = 8
CV_LAMBDAS = [0.001, 0.01, 0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000]
N_FOLDS = 5
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


def log(*a):
    print(*a); sys.stdout.flush()


_split_rng = random.Random(1234)
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]


class BlindPermTestCore(sc.SovereignCore):
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

    def probe_brick_firing_vector_blind(self, call, brick_id_order, sustain_cycles=SUSTAIN_CYCLES):
        """THE FIX: current_target is NEVER set to the real answer here -- left at whatever the
        clone's own current_target happened to be (None, or stale from training; either way not
        the true answer for THIS probe call), so update_prediction_error()/relay-splitting can
        never see the target during harvesting. Pure blind inference."""
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        clone.current_target = None   # explicit: never the real answer, the whole point of this fix
        for _ in range(sustain_cycles):
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            # deliberately NOT setting clone.current_target here -- inject_problem() with a
            # forced_call not in TASK_PAIRS would silently default target=0 internally for ITS
            # OWN bookkeeping (self.current_target inside inject_problem), so immediately
            # overwrite that back to None after each call, keeping the clone fully blind.
            clone.current_target = None
            clone._update_bricks(); clone._fire_relays()

        by_id = {b.id: b for b in clone.bricks if b.alive}
        feat = np.zeros(len(brick_id_order))
        for i, bid in enumerate(brick_id_order):
            b = by_id.get(bid)
            if b is not None and getattr(b, "fired_this_cycle", False):
                feat[i] = b.predict_next()
        random.setstate(saved_random_state)
        return feat


def ridge_fit(X, y, lam):
    d = X.shape[1]
    A = X.T @ X + lam * np.eye(d)
    b = X.T @ y
    return np.linalg.solve(A, b)


def cv_select_lambda(X, y, lambdas, k, rng):
    n = X.shape[0]
    idx = rng.permutation(n)
    folds = np.array_split(idx, k)
    best_lam, best_mse = lambdas[0], float("inf")
    for lam in lambdas:
        mses = []
        for i in range(k):
            te = folds[i]
            tr = np.concatenate([folds[j] for j in range(k) if j != i])
            w = ridge_fit(X[tr], y[tr], lam)
            pred = X[te] @ w
            mses.append(np.mean((pred - y[te]) ** 2))
        mse = float(np.mean(mses))
        if mse < best_mse:
            best_mse, best_lam = mse, lam
    return best_lam, best_mse


def score_midpoint(preds, targets):
    correct = sum(1 for p, t in zip(preds, targets)
                  if (BIT_HIGH if p >= MIDPOINT else BIT_LOW) == t)
    return correct, len(targets)


def main():
    log("=" * 78)
    log("BLIND PERMUTATION TEST -- same as before, but current_target is NEVER set to the real")
    log("answer during harvesting. If the earlier 100% was target leakage, this should drop.")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = BlindPermTestCore(init_bricks=sc.INIT_BRICKS)
    log("\nTraining the real engine, 8000 cycles (identical to prior tests)...")
    for cyc in range(8000):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
            log(f"   cycle {core.current_time}: train (500-subsample) {c}/{t} ({100*c/t:.1f}%)")

    brick_id_order = sorted(b.id for b in core.bricks
                             if b.alive and b.module_id == core.output_module_id)
    log(f"\n{len(brick_id_order)} living output-module bricks.")

    probe_rng = random.Random(99)
    train_probe_set = probe_rng.sample(TRAIN_PAIRS, min(PROBE_TRAIN_SUBSAMPLE, len(TRAIN_PAIRS)))
    held_probe_set = probe_rng.sample(HELDOUT_PAIRS, min(PROBE_HELDOUT_SUBSAMPLE, len(HELDOUT_PAIRS)))
    all_probe = train_probe_set + held_probe_set
    n_train_probe = len(train_probe_set)
    log(f"\nHarvesting BLIND brick-firing features for {n_train_probe} train + "
        f"{len(held_probe_set)} held-out pairs ({SUSTAIN_CYCLES} sustained cycles each, "
        f"current_target NEVER set to the real answer)...")

    raw_feats = []
    for i, (call, target) in enumerate(all_probe):
        feat = core.probe_brick_firing_vector_blind(call, brick_id_order)
        raw_feats.append(feat)
        if (i + 1) % 50 == 0:
            log(f"   harvested {i+1}/{len(all_probe)}...")
    raw_feats = np.array(raw_feats)
    Xb = raw_feats / (np.linalg.norm(raw_feats, axis=1, keepdims=True) + 1e-9)

    real_targets = np.array([1.0 if target >= MIDPOINT else -1.0 for _, target in all_probe])
    train_targets_real_bits = [t for _, t in train_probe_set]
    held_targets_real_bits = [t for _, t in held_probe_set]

    def run_condition(label, y, true_train_bits, true_held_bits):
        log(f"\n-- {label} --")
        lam, cv_mse = cv_select_lambda(Xb[:n_train_probe], y[:n_train_probe], CV_LAMBDAS,
                                        N_FOLDS, np.random.default_rng(7))
        log(f"   5-fold CV lambda = {lam} (CV MSE {cv_mse:.3f})")
        W = ridge_fit(Xb[:n_train_probe], y[:n_train_probe], lam)
        pred_tr = Xb[:n_train_probe] @ W
        pred_he = Xb[n_train_probe:] @ W
        tr_bits = [(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_tr]
        he_bits = [(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_he]
        tc, tt = score_midpoint(tr_bits, true_train_bits)
        hc, ht = score_midpoint(he_bits, true_held_bits)
        log(f"   train: {tc}/{tt} ({100*tc/tt:.1f}%)   held-out: {hc}/{ht} ({100*hc/ht:.1f}%)")
        return 100 * hc / ht

    held_real = run_condition("A: REAL targets, BLIND harvesting", real_targets,
                               train_targets_real_bits, held_targets_real_bits)

    perm_rng = np.random.default_rng(2026)
    permuted_targets = real_targets.copy()
    perm_rng.shuffle(permuted_targets)
    perm_train_bits = [(BIT_HIGH if yy > 0 else BIT_LOW) for yy in permuted_targets[:n_train_probe]]
    perm_held_bits = [(BIT_HIGH if yy > 0 else BIT_LOW) for yy in permuted_targets[n_train_probe:]]
    held_permuted = run_condition("B: PERMUTED targets, BLIND harvesting", permuted_targets,
                                   perm_train_bits, perm_held_bits)

    log("\n" + "=" * 78)
    log("VERDICT")
    log("=" * 78)
    log(f"   A (real targets, blind):     held-out {held_real:.1f}%")
    log(f"   B (permuted targets, blind): held-out {held_permuted:.1f}%")
    log(f"   (for reference, the LEAKY version measured: A=100.0%, B=54.0%)")
    if held_real < 70 and held_permuted < 55:
        log("   => Leakage confirmed as (at least most of) the explanation. The honest, blind")
        log("      number is the real one to trust going forward.")
    elif abs(held_real - 100) < 10:
        log("   => The leakage fix did NOT meaningfully change the result -- the 100% was not")
        log("      (primarily) caused by target leakage. Real cause still open.")
    else:
        log("   => Partial effect -- report both numbers plainly, don't force a clean verdict.")


if __name__ == "__main__":
    main()
