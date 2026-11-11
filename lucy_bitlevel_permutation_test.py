#!/usr/bin/env python3
"""
lucy_bitlevel_permutation_test.py -- 2026-10-19. Settles an open question from tonight's model
reviews before any further architecture work (dendritic branches, disaster events, or a future
"wilderness" rebuild) gets built on top of it: is the 58-59% post-hoc ridge regression result
(the real signal condition B/combinatorial tests found tonight, `[[combinatorial_expansion_missing_ingredient]]`)
actually real context-to-target binding, or could the measurement methodology itself produce a
similar-looking number regardless of whether the binding is real?

This is the standard statistical tool for exactly that concern: a PERMUTATION TEST (label
randomization control). Harvest the real brick-firing features ONCE (identical proven methodology
to `lucy_bitlevel_combinatorial_readout.py`'s condition B), then fit ridge regression TWICE on the
SAME features -- once with the real targets, once with the targets randomly permuted. If the
permuted-label fit collapses to chance on held-out while the real-label fit holds its ~58-59%,
the original signal is confirmed real. If the permuted fit ALSO lands near 58-59%, that's
definitive: something about the measurement (not the substrate) was producing the number, and the
whole combinatorial-expansion/dendritic-branch line of work tonight needs to be revisited.

(DeepSeek's own proposed test, same night, was slightly different -- regenerating the corpus with
the early-fact-to-late-answer relationship deliberately scrambled at the source. That's a more
involved experiment aimed at an earlier description of a longer-range recall task. This
permutation test targets the same underlying concern -- is the measured number real or a
methodology artifact -- using the standard, well-defined statistical tool for it, on the actual
bit-level task tonight's numbers came from.)
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


class PermTestCore(sc.SovereignCore):
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

    def probe_brick_firing_vector(self, call, target, brick_id_order, sustain_cycles=SUSTAIN_CYCLES):
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        for _ in range(sustain_cycles):
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone.current_target = float(target)
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
    log("PERMUTATION TEST -- is the 58-59% ridge result real binding or a methodology artifact?")
    log(f"{len(TRAIN_PAIRS)} train / {len(HELDOUT_PAIRS)} held-out. Chance = 50%.")
    log("=" * 78)

    random.seed(42)
    core = PermTestCore(init_bricks=sc.INIT_BRICKS)
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
    log(f"\nHarvesting real brick-firing features for {n_train_probe} train + "
        f"{len(held_probe_set)} held-out pairs ({SUSTAIN_CYCLES} sustained cycles each)...")

    raw_feats = []
    for i, (call, target) in enumerate(all_probe):
        feat = core.probe_brick_firing_vector(call, target, brick_id_order)
        raw_feats.append(feat)
        if (i + 1) % 50 == 0:
            log(f"   harvested {i+1}/{len(all_probe)}...")
    raw_feats = np.array(raw_feats)
    Xb = raw_feats / (np.linalg.norm(raw_feats, axis=1, keepdims=True) + 1e-9)

    real_targets = np.array([1.0 if target >= MIDPOINT else -1.0 for _, target in all_probe])
    train_targets_real_bits = [t for _, t in train_probe_set]
    held_targets_real_bits = [t for _, t in held_probe_set]

    def run_condition(label, y):
        log(f"\n-- {label} --")
        lam, cv_mse = cv_select_lambda(Xb[:n_train_probe], y[:n_train_probe], CV_LAMBDAS,
                                        N_FOLDS, np.random.default_rng(7))
        log(f"   5-fold CV lambda = {lam} (CV MSE {cv_mse:.3f})")
        W = ridge_fit(Xb[:n_train_probe], y[:n_train_probe], lam)
        pred_tr = Xb[:n_train_probe] @ W
        pred_he = Xb[n_train_probe:] @ W
        tr_bits = [(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_tr]
        he_bits = [(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_he]
        tc, tt = score_midpoint(tr_bits, train_targets_real_bits if label == "A: REAL targets"
                                 else [(BIT_HIGH if yy > 0 else BIT_LOW) for yy in y[:n_train_probe]])
        hc, ht = score_midpoint(he_bits, held_targets_real_bits if label == "A: REAL targets"
                                 else [(BIT_HIGH if yy > 0 else BIT_LOW) for yy in y[n_train_probe:]])
        log(f"   train: {tc}/{tt} ({100*tc/tt:.1f}%)   held-out: {hc}/{ht} ({100*hc/ht:.1f}%)")
        return 100 * hc / ht

    held_real = run_condition("A: REAL targets (should reproduce ~58-59%)", real_targets)

    perm_rng = np.random.default_rng(2026)
    permuted_targets = real_targets.copy()
    perm_rng.shuffle(permuted_targets)
    held_permuted = run_condition("B: PERMUTED targets (should collapse to ~50% if signal is real)",
                                   permuted_targets)

    log("\n" + "=" * 78)
    log("VERDICT")
    log("=" * 78)
    log(f"   A (real targets):     held-out {held_real:.1f}%")
    log(f"   B (permuted targets): held-out {held_permuted:.1f}%")
    if held_permuted < held_real - 5 and held_permuted < 55:
        log("   => CONFIRMED REAL: permuting the labels destroyed the signal, as it should for a")
        log("      genuine relationship. The 58-59% result reflects real context-to-target")
        log("      structure in the substrate's internal state, not a measurement artifact.")
    elif abs(held_permuted - held_real) <= 5:
        log("   => ARTIFACT WARNING: permuted labels scored almost as well as real ones. This")
        log("      means the ~58-59% number was NOT measuring real context-to-target binding --")
        log("      something about the harvesting/fitting methodology itself is inflating the")
        log("      score regardless of the true labels. The combinatorial-expansion and")
        log("      dendritic-branch work tonight needs to be revisited in light of this.")
    else:
        log("   => AMBIGUOUS: neither a clean confirmation nor a clean artifact signature.")
        log("      Report both numbers plainly; don't force a verdict past what they show.")


if __name__ == "__main__":
    main()
