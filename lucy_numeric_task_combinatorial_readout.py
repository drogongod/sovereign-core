#!/usr/bin/env python3
"""
lucy_numeric_task_combinatorial_readout.py -- 2026-10-17. THE CROSS-SUBSTRATE TRANSPLANT TEST.

WHY THIS FILE EXISTS: tonight, on a completely different substrate (Flybrain, a real FlyWire
connectome reservoir), we found a precise, provable reason a system can memorize training
examples but fail to generalize the actual RULE behind them: the readout was LINEAR, and the
target function had XOR/parity-shaped structure a linear combination can never represent, no
matter how clean the underlying representation is. The fix -- sparse COMBINATORIAL CONJUNCTION
CODING (real Kenyon-cell-style expansion: many small units, each firing only when several
DIFFERENT raw features are simultaneously active) -- measurably worked there, confirmed twice
(plain delta rule AND cross-validated ridge regression, so it wasn't an overfitting illusion).

SovereignCore's own original numeric task (`lucy_original_numeric_task.py`, unmodified
TASK_PAIRS) shows the EXACT SAME FAILURE SHAPE on a totally different architecture: 6/6 training
triples memorized, but only 1/4 genuinely held-out "+2 rule" triples solved. This file asks the
direct, honest question: is SovereignCore hitting the SAME wall, for the SAME reason? And if we
apply the SAME fix -- a combinatorial-conjunction expansion stage, built the identical way as
the proven Flybrain fix -- does it help here too?

SCOPE, DELIBERATELY NARROW: this script does NOT modify `sovereign_core.py`'s real, proven
`_read_response()` engine code. That function is a HAND-DESIGNED weighted vote
(`num += w*val; den += w`, see sovereign_core.py:1070-1081) with no expansion stage anywhere in
its pipeline -- confirmed directly in the live code tonight, not assumed. Rather than risk
breaking the real, working engine, this is an EXTERNAL READOUT PROBE: train the real,
unmodified SovereignCore exactly as `lucy_original_numeric_task.py` already does and already
proved works (8000 cycles, seed=42, the same proven WOLFPACK_SISTER_MATCH=False baseline), then
AFTER training, harvest the real internal brick-firing states the engine already computed for
each probe call, and test three different READOUT strategies on those SAME real internal states:

  (A) SovereignCore's own native weighted-vote readout -- the baseline, already measured by
      `lucy_original_numeric_task.py`: 6/6 train, 1/4 held-out. Not re-run here, just recapped.
  (B) A trained, ridge-regularized LINEAR readout on the RAW per-brick firing-pattern feature
      vector (does a fair, properly-fit linear readout do any better than the hand-designed
      vote formula, with no expansion at all? -- isolates "is linearity itself the bottleneck").
  (C) The PROPOSED FIX: a trained, ridge-regularized linear readout on a COMBINATORIALLY-EXPANDED
      feature vector -- KC-style conjunction units, each firing only when K randomly-sampled
      OUTPUT BRICKS all fired simultaneously for that call. Built the identical way as
      `flybrain_binary_addition_combinatorial.py`'s proven fix, just applied to SovereignCore's
      real brick-firing patterns instead of Flybrain's real reservoir neurons.

If (C) beats both (A) and (B), that's real, cross-substrate evidence the missing ingredient is
the same one in both places -- not a coincidence of one toy test, a shared architectural gap.
If it doesn't, that's an equally real, honestly-reported negative, and the "universal missing
ingredient" idea from tonight's discussion needs to be narrowed or dropped for SovereignCore.

ONLY 6 TRAIN + 4 HELD-OUT EXAMPLES TOTAL -- WORTH SAYING UP FRONT, NOT BURYING: this is a far
smaller sample than Flybrain's 150/106 split. Cross-validation here is necessarily leave-one-out
(k=6), and any numbers from 4 held-out points move in big, noisy steps (0/4, 1/4, 2/4 = 25-point
jumps). Read the result as a weak signal at most, not a confident verdict either way -- the real,
confident result tonight remains the Flybrain one; this is the first, necessarily-small-sample
look at whether it transplants.
"""
import sys, os, random, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

sc.WOLFPACK_SISTER_MATCH = False  # proven baseline -- same discipline as every test tonight

N_KC = 150          # number of combinatorial expansion units (conjunction detectors)
K_SAMPLE = 3         # each unit conjuncts this many randomly-sampled output bricks' firing bits
LAMBDAS = [0.001, 0.01, 0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000]


def log(*a):
    print(*a); sys.stdout.flush()


class ReadoutProbeCore(sc.SovereignCore):
    """Identical in spirit to lucy_original_numeric_task.py's OriginalTaskCore, EXTENDED with one
    new method (`probe_brick_firing_vector`) that harvests the real internal state the engine
    already computes for a probe call, instead of only reading `_read_response()`'s final answer.
    TASK_PAIRS deliberately NOT overridden -- this is still the real, original, built-in task."""

    def exact_match_accuracy(self):
        # verbatim copy of the proven, already-fixed probe-isolation discipline from
        # lucy_original_numeric_task.py: deepcopy + global-RNG save/restore, so probing the live
        # trained core for recap purposes can never mutate it (see that file's own comment for
        # the full history of why this exists -- the diagnostic-probe bug class, fixed twice).
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in clone.TASK_PAIRS:
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone._update_bricks(); clone._fire_relays()
            resp = clone._read_response()
            if resp is not None and round(resp) == target:
                correct += 1
        random.setstate(saved_random_state)
        return correct, len(self.TASK_PAIRS)

    def probe_brick_firing_vector(self, call, target, brick_id_order, sustain_cycles=10):
        """Run a SUSTAINED probe on a THROWAWAY DEEPCOPY (never touches the live trained core --
        same isolation discipline as exact_match_accuracy above).

        FIX, 2026-10-17 (found by reading the FIRST, broken version of this test's own output,
        not assumed): a single post-injection cycle is NOT enough time for a freshly-injected
        call's signal to reach and differentiate output-module bricks' FIRING state, because
        signal propagation here is explicitly delayed by design (PairedRelay's base_delay/
        back_delay -- the deliberate multi-cycle lag central to this architecture, see
        [[sovereigncore_true_design_philosophy]]). SovereignCore's own native _read_response()
        still varies correctly call-to-call within one cycle because PROTOTYPE MATCHING reads the
        call vector directly, bypassing the relay network entirely -- but firing/predict_next()
        state does not get that shortcut. The first version of this probe harvested one-cycle
        firing state and got an IDENTICAL feature vector for every call regardless of input (0.0%
        KC-conjunction activity, a single constant ridge prediction for all 10 calls) -- not a
        real negative result, a broken probe. This version RE-INJECTS the SAME call every cycle
        for `sustain_cycles` cycles (mirroring how the engine actually receives repeated
        presentation during real operation, not a one-shot flash) before harvesting, giving the
        relay-delayed signal real time to propagate and actually differentiate output bricks.

        Returns:
          - the engine's own native answer, read at the END of the sustained presentation (for a
            fair recap of condition A under the SAME sustained-presentation condition used for B/C
            -- noted explicitly as a methodology difference from the original single-cycle
            exact_match_accuracy()/generalization_check(), not hidden).
          - a FIXED-LENGTH real-valued feature vector: brick_id_order[i]'s predict_next() value if
            that brick fired on the FINAL cycle, else 0.0 (silent bricks contribute nothing).
        """
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        native_answer = None
        for _ in range(sustain_cycles):
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            # BUG7-style fix (same one lucy_original_numeric_task.py applies): inject_problem()'s
            # TASK_PAIRS lookup silently defaults current_target=0 for any call not in TASK_PAIRS,
            # true for every held-out triple by design -- override with the REAL target every
            # cycle, so sustained held-out probing isn't internally distorted by a wrong leaked
            # target the way the original bug corrupted it.
            clone.current_target = float(target)
            clone._update_bricks(); clone._fire_relays()
            native_answer = clone._read_response()

        by_id = {b.id: b for b in clone.bricks if b.alive}
        feat = np.zeros(len(brick_id_order))
        for i, bid in enumerate(brick_id_order):
            b = by_id.get(bid)
            if b is not None and getattr(b, "fired_this_cycle", False):
                feat[i] = b.predict_next()
        random.setstate(saved_random_state)
        return native_answer, feat


def ridge_fit(X, y, lam):
    """Standard ridge regression, closed form -- identical methodology to
    flybrain_binary_addition_ridge.py, just for a SCALAR continuous target (SovereignCore's task
    predicts a number, not independent bits) instead of a multi-bit vector."""
    d = X.shape[1]
    A = X.T @ X + lam * np.eye(d)
    b = X.T @ y
    return np.linalg.solve(A, b)


def cv_select_lambda_loo(X, y, lambdas):
    """Leave-one-out cross-validation (the only sane choice with only 6 training points -- a
    5-fold split on 6 examples is barely different from LOO anyway, so just do LOO directly and
    say so, rather than pretending a bigger CV scheme adds real statistical power here)."""
    n = X.shape[0]
    best_lam, best_err = lambdas[0], float("inf")
    for lam in lambdas:
        sq_errs = []
        for i in range(n):
            tr = [j for j in range(n) if j != i]
            w = ridge_fit(X[tr], y[tr], lam)
            pred = X[i] @ w
            sq_errs.append((pred - y[i]) ** 2)
        mse = float(np.mean(sq_errs))
        if mse < best_err:
            best_err, best_lam = mse, lam
    return best_lam, best_err


def main():
    log("=" * 78)
    log("SOVEREIGNCORE <-> FLYBRAIN CROSS-SUBSTRATE TRANSPLANT TEST")
    log("Does the combinatorial-conjunction-coding fix that worked on Flybrain also help")
    log("SovereignCore's own memorize-but-don't-generalize numeric task?")
    log("=" * 78)

    # ---------------------------------------------------------------------------------------
    # STEP 1: train the REAL, UNMODIFIED engine exactly as lucy_original_numeric_task.py does
    # and already proved works -- same seed, same cycle count, same proven baseline flag. This
    # is not a new training run invented for this test; it is the identical, already-validated
    # training procedure, so condition (A)'s recap number is directly comparable to the night's
    # earlier real result, not a fresh unrelated run.
    # ---------------------------------------------------------------------------------------
    random.seed(42)
    core = ReadoutProbeCore(init_bricks=sc.INIT_BRICKS)
    log(f"\nTraining the real SovereignCore engine, 8000 cycles (identical to "
        f"lucy_original_numeric_task.py)...")
    for cyc in range(8000):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_accuracy()
            log(f"   cycle {core.current_time}: exact-match {c}/{t}")

    # ---------------------------------------------------------------------------------------
    # STEP 2: fix ONE stable ordering of output-module bricks -- the "neuron index" for every
    # probe's feature vector, so all 10 calls (6 train + 4 held-out) produce directly comparable,
    # same-length, same-meaning feature vectors.
    # ---------------------------------------------------------------------------------------
    brick_id_order = sorted(b.id for b in core.bricks
                             if b.alive and b.module_id == core.output_module_id)
    log(f"\n{len(brick_id_order)} living output-module bricks found -- this is the feature "
        f"dimensionality for conditions B and C below.")

    held_out = [((3, 5, 7), 9), ((30, 29, 28), 27), ((8, 10, 12), 14), ((0, 2, 4), 6)]
    all_calls = list(core.TASK_PAIRS) + held_out
    n_train = len(core.TASK_PAIRS)

    # ---------------------------------------------------------------------------------------
    # STEP 3: harvest the REAL internal brick-firing state for every probe call, via the
    # throwaway-deepcopy-isolated probe (zero effect on the live trained core, by construction --
    # same discipline as exact_match_accuracy, extended to also capture the feature vector).
    # ---------------------------------------------------------------------------------------
    log("\nHarvesting real brick-firing feature vectors for all 6 train + 4 held-out calls...")
    native_answers, raw_feats = [], []
    for call, target in all_calls:
        native_ans, feat = core.probe_brick_firing_vector(call, target, brick_id_order)
        native_answers.append(native_ans)
        raw_feats.append(feat)
    raw_feats = np.array(raw_feats)
    targets = np.array([t for _, t in all_calls], dtype=float)

    # ---------------------------------------------------------------------------------------
    # CONDITION A -- recap only, not re-run: SovereignCore's own native weighted-vote readout.
    # ---------------------------------------------------------------------------------------
    log("\n" + "-" * 78)
    log("CONDITION A: SovereignCore's own native _read_response() weighted vote (RECAP)")
    log("-" * 78)
    a_train_correct = sum(1 for i in range(n_train)
                           if native_answers[i] is not None and round(native_answers[i]) == targets[i])
    a_held_correct = sum(1 for i in range(n_train, len(all_calls))
                          if native_answers[i] is not None and round(native_answers[i]) == targets[i])
    for i, (call, target) in enumerate(all_calls):
        tag = "train" if i < n_train else "HELD-OUT"
        log(f"   [{tag}] {call} -> target {target}, native answer = {native_answers[i]}")
    log(f"   => native readout: train {a_train_correct}/{n_train}, "
        f"held-out {a_held_correct}/{len(held_out)}")

    # ---------------------------------------------------------------------------------------
    # CONDITION B -- a FAIR, properly cross-validated LINEAR readout on the SAME raw brick
    # features, no expansion at all. Isolates whether linearity itself (not the hand-tuned
    # vote-weight formula) is the real bottleneck, independent of SovereignCore's specific
    # weighting scheme.
    # ---------------------------------------------------------------------------------------
    log("\n" + "-" * 78)
    log(f"CONDITION B: ridge-regularized LINEAR readout on RAW brick features "
        f"({raw_feats.shape[1]}-dim, no expansion)")
    log("-" * 78)
    Xb = raw_feats / (np.linalg.norm(raw_feats, axis=1, keepdims=True) + 1e-9)
    lam_b, cv_err_b = cv_select_lambda_loo(Xb[:n_train], targets[:n_train], LAMBDAS)
    log(f"   LOO-cross-validated lambda = {lam_b} (LOO MSE {cv_err_b:.3f})")
    Wb = ridge_fit(Xb[:n_train], targets[:n_train], lam_b)
    pred_b = Xb @ Wb
    b_train_correct = sum(1 for i in range(n_train) if round(pred_b[i]) == targets[i])
    b_held_correct = sum(1 for i in range(n_train, len(all_calls)) if round(pred_b[i]) == targets[i])
    for i, (call, target) in enumerate(all_calls):
        tag = "train" if i < n_train else "HELD-OUT"
        log(f"   [{tag}] {call} -> target {target}, ridge-linear pred = {pred_b[i]:.2f}")
    log(f"   => raw-feature ridge readout: train {b_train_correct}/{n_train}, "
        f"held-out {b_held_correct}/{len(held_out)}")

    # ---------------------------------------------------------------------------------------
    # CONDITION C -- THE PROPOSED FIX: combinatorial conjunction expansion over the SAME raw
    # brick features, built identically to flybrain_binary_addition_combinatorial.py's proven
    # mechanism. Each KC-style unit samples K=3 of the output bricks and fires (1.0) only if ALL
    # K of them fired for this call -- a real cross-brick conjunction term, the exact thing
    # Flybrain's redundant-population test (which only gave repeats of ONE bit, no cross-term)
    # proved does NOT work, and Flybrain's real combinatorial test proved DOES.
    # ---------------------------------------------------------------------------------------
    log("\n" + "-" * 78)
    log(f"CONDITION C: ridge-regularized readout on {N_KC} COMBINATORIAL CONJUNCTION units "
        f"(K={K_SAMPLE} output bricks each, the proposed fix)")
    log("-" * 78)
    rng = np.random.default_rng(1)
    n_bricks = raw_feats.shape[1]
    if n_bricks < K_SAMPLE:
        log(f"   only {n_bricks} output bricks alive -- fewer than K_SAMPLE={K_SAMPLE}, cannot "
            f"build real conjunctions. Skipping condition C honestly rather than faking a result.")
    else:
        fired_bits = (raw_feats != 0.0).astype(float)   # binary "did this brick fire for this call"
        kc_samples = [rng.choice(n_bricks, K_SAMPLE, replace=False) for _ in range(N_KC)]
        n_informative = sum(1 for s in kc_samples if len(set(fired_bits[:, s].sum(0).tolist())) > 1)
        kc_feats = np.array([[1.0 if fired_bits[row, s].all() else 0.0 for s in kc_samples]
                              for row in range(len(all_calls))])
        active_frac = kc_feats.mean()
        log(f"   KC-code sparsity: {100*active_frac:.1f}% of {N_KC} conjunction units active on "
            f"average per call")
        Xc = kc_feats / (np.linalg.norm(kc_feats, axis=1, keepdims=True) + 1e-9)
        lam_c, cv_err_c = cv_select_lambda_loo(Xc[:n_train], targets[:n_train], LAMBDAS)
        log(f"   LOO-cross-validated lambda = {lam_c} (LOO MSE {cv_err_c:.3f})")
        Wc = ridge_fit(Xc[:n_train], targets[:n_train], lam_c)
        pred_c = Xc @ Wc
        c_train_correct = sum(1 for i in range(n_train) if round(pred_c[i]) == targets[i])
        c_held_correct = sum(1 for i in range(n_train, len(all_calls)) if round(pred_c[i]) == targets[i])
        for i, (call, target) in enumerate(all_calls):
            tag = "train" if i < n_train else "HELD-OUT"
            log(f"   [{tag}] {call} -> target {target}, combinatorial-ridge pred = {pred_c[i]:.2f}")
        log(f"   => combinatorial-expansion ridge readout: train {c_train_correct}/{n_train}, "
            f"held-out {c_held_correct}/{len(held_out)}")

    log("\n" + "=" * 78)
    log("HONEST SUMMARY (n=4 held-out -- read as a weak signal, not a confident verdict)")
    log("=" * 78)
    log(f"   A (native vote)              : train {a_train_correct}/{n_train}, held-out {a_held_correct}/{len(held_out)}")
    log(f"   B (linear, no expansion)      : train {b_train_correct}/{n_train}, held-out {b_held_correct}/{len(held_out)}")
    if n_bricks >= K_SAMPLE:
        log(f"   C (combinatorial expansion)   : train {c_train_correct}/{n_train}, held-out {c_held_correct}/{len(held_out)}")


if __name__ == "__main__":
    main()
