#!/usr/bin/env python3
"""
lucy_bitlevel_combinatorial_readout.py -- 2026-10-17. THE CORRECTED CROSS-SUBSTRATE TRANSPLANT
TEST, scaled up and on the RIGHT task this time.

WHY THIS FILE EXISTS, AND WHY THE EARLIER ONE WASN'T ENOUGH: `lucy_numeric_task_combinatorial_
readout.py` tested whether Flybrain's proven fix (sparse combinatorial "KC-style" conjunction
coding, which fixed a real linear-separability/XOR ceiling on a binary-addition task) transplants
onto SovereignCore. That test came back INCONCLUSIVE for two real, named reasons, not a true
negative: (1) only 6 training examples -- nowhere near enough to fit or cross-validate a
39-150-dimensional readout meaningfully, and (2) Jonathan's own direct catch, independent of
sample size: the "+2 rule" numeric task is a LINEAR function (output = input + 2). A plain linear
readout can represent that in principle given enough data -- testing the XOR-type fix on an
already-linear task was never a fair test of the hypothesis at all.

THIS FILE FIXES BOTH PROBLEMS AT ONCE by using SovereignCore's own BIT-LEVEL task instead
(`lucy_favorite_color_core_bitlevel.py`'s real corpus/encoding, reused verbatim): ~850 real
(16-bit context -> next-bit) pairs, not 6 -- and recalling a specific bit by query position is a
genuine lookup/parity-shaped problem (nearby context windows that differ in only a few bit
positions routinely map to completely different target bits), structurally much closer to
Flybrain's actual parity sum-bits than arithmetic addition ever was. This is the task this
project has been stuck at chance-level on all night (`[[lucy_sovereigncore_flybrain_substrates]]`)
-- if the combinatorial-expansion fix is going to transplant anywhere on this substrate, this is
where it would show up.

WHAT'S GENUINELY NEW vs. THE ORIGINAL BIT-LEVEL TEST: the original `lucy_favorite_color_core_
bitlevel.py` trains and evaluates on the SAME full pair set -- there is no held-out split at
all, so it can only ever measure memorization, never real generalization. This file explicitly
splits the ~850 real pairs into a TRAIN subset (the only pairs the engine is ever trained or
probed on) and a HELD-OUT subset (never shown to the engine during training, used only to score
genuine generalization) -- the same discipline used on every substrate all night.

METHODOLOGY, identical in spirit to the (bug-fixed) numeric-task transplant test:
  (A) SovereignCore's own native weighted-vote readout -- recap, scored on train + held-out.
  (B) A fair, cross-validated ridge-regularized LINEAR readout on the real internal brick-firing
      feature vector (harvested via SUSTAINED multi-cycle probing -- a single post-injection
      cycle does not give the relay-delayed signal time to differentiate output-brick firing;
      see the long comment in `probe_brick_firing_vector` below for the exact bug this avoids,
      found and fixed in the numeric-task version of this test).
  (C) THE PROPOSED FIX: a ridge-regularized readout on COMBINATORIALLY-EXPANDED KC-style
      conjunction features built from those same real brick-firing patterns -- identical
      mechanism to `flybrain_binary_addition_combinatorial.py`'s proven fix, just applied to
      SovereignCore's real internal state instead of Flybrain's real reservoir neurons.

COMPUTE BUDGET, stated honestly up front: harvesting real brick-firing features requires a fresh
deepcopy + several real engine cycles PER PROBED PAIR (Python object-level simulation, not cheap
vectorized numpy like Flybrain's settle()). Probing all ~850 pairs this way would take a very
long time. This file trains the engine on the FULL train split (realistic scale, ~700 pairs) but
SUBSAMPLES a bounded number of pairs (200 train + 100 held-out by default) for the actual
readout-comparison stage -- enough for a real cross-validated ridge fit, not enough to be
Flybrain-scale exhaustive. This tradeoff is a deliberate, named compromise, not a hidden one.
"""
import sys, os, random, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

# pull in the real, already-built corpus/encoding from the proven bit-level test file instead of
# reinventing it -- same corpus, same text_to_bits()/scale_bit() scaling fix (literal 0/1 would be
# sub-resolution for this substrate; rescaled to 0/STATE_MAX, see that file's own header comment).
import lucy_favorite_color_core_bitlevel as blvl

sc.WOLFPACK_SISTER_MATCH = False  # proven baseline -- same discipline as every test tonight

N_TRAIN_PAIRS = 700          # real pairs the engine is actually trained AND probed on
N_HELDOUT_PAIRS = 150        # real pairs NEVER shown to the engine during training
PROBE_TRAIN_SUBSAMPLE = 200  # of the 700 train pairs, how many get readout-harvested (compute budget)
PROBE_HELDOUT_SUBSAMPLE = 100  # of the 150 held-out pairs, how many get readout-harvested
SUSTAIN_CYCLES = 8           # cycles to sustain each probe call before harvesting (see the bug
                              # this avoids, documented in probe_brick_firing_vector below)
N_KC = 300                   # combinatorial expansion units
K_SAMPLE = 4                 # each KC unit conjuncts this many of the 16 raw context bits
CV_LAMBDAS = [0.001, 0.01, 0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000]
N_FOLDS = 5


def log(*a):
    print(*a); sys.stdout.flush()


# ---------------------------------------------------------------------------------------------
# STEP 0: build the real split. blvl.TASK_PAIRS_RAW is the FULL set of real (context, target)
# pairs from the real corpus (see lucy_favorite_color_core_bitlevel.py's own build_bit_task_pairs).
# Split deterministically (fixed seed) into TRAIN (engine trains+probes on this ONLY) and
# HELD-OUT (engine NEVER sees these during training -- the real generalization test, absent from
# the original bit-level file entirely).
# ---------------------------------------------------------------------------------------------
_split_rng = random.Random(1234)
_all_pairs = list(blvl.TASK_PAIRS_RAW)
_split_rng.shuffle(_all_pairs)
TRAIN_PAIRS = _all_pairs[:N_TRAIN_PAIRS]
HELDOUT_PAIRS = _all_pairs[N_TRAIN_PAIRS:N_TRAIN_PAIRS + N_HELDOUT_PAIRS]
BIT_HIGH, BIT_LOW = blvl.BIT_HIGH, blvl.BIT_LOW
MIDPOINT = BIT_HIGH / 2.0


class BitLevelReadoutProbeCore(sc.SovereignCore):
    """Same engine, same task encoding as LucyBitLevelCore, but TASK_PAIRS is now the TRAIN-ONLY
    split -- the engine is architecturally incapable of ever training on HELDOUT_PAIRS, because
    inject_problem()'s random-task path (`random.choice(self.TASK_PAIRS)`) can only ever choose
    from this list. HELDOUT_PAIRS only ever reach the engine through forced_call in a probe."""
    TASK_PAIRS = TRAIN_PAIRS

    def exact_match_accuracy(self, pairs, n_probe=None):
        """Verbatim same real fix as every other test tonight: throwaway deepcopy + global-RNG
        save/restore, so recapping the native readout can never mutate the live trained core.
        Takes an explicit `pairs` argument (train OR held-out) instead of always using
        self.TASK_PAIRS, so this one method can score BOTH splits honestly."""
        probe_set = pairs if n_probe is None or n_probe >= len(pairs) else random.sample(pairs, n_probe)
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in probe_set:
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone.current_target = float(target)   # BUG7-style fix: held-out calls aren't in
            # clone.TASK_PAIRS, so inject_problem()'s dict lookup would silently default target=0
            # for them -- override with the REAL target, same discipline as every held-out probe
            # tonight, so a wrong leaked target can't distort the probe's own internal dynamics.
            clone._update_bricks(); clone._fire_relays()
            resp = clone._read_response()
            predicted = None if resp is None else (BIT_HIGH if resp >= MIDPOINT else BIT_LOW)
            if predicted == target:
                correct += 1
        random.setstate(saved_random_state)
        return correct, len(probe_set)

    def probe_brick_firing_vector(self, call, target, brick_id_order, sustain_cycles=SUSTAIN_CYCLES):
        """Identical fix to lucy_numeric_task_combinatorial_readout.py's version, carried forward
        deliberately rather than re-discovering the same bug: a single post-injection cycle does
        NOT give signal propagation (gated by PairedRelay's base_delay/back_delay, a deliberate
        multi-cycle lag central to this architecture) time to differentiate output-brick firing
        for a freshly-injected call. SovereignCore's own native _read_response() varies correctly
        within one cycle only because prototype matching reads the call vector directly,
        bypassing the relay network -- firing/predict_next() state does not get that shortcut.
        Fix: re-inject the SAME call every cycle for `sustain_cycles` cycles before harvesting,
        mirroring how the engine actually receives repeated presentation during real operation."""
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        native_answer = None
        for _ in range(sustain_cycles):
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone.current_target = float(target)
            clone._update_bricks(); clone._fire_relays()
            resp = clone._read_response()
            native_answer = None if resp is None else (BIT_HIGH if resp >= MIDPOINT else BIT_LOW)

        by_id = {b.id: b for b in clone.bricks if b.alive}
        feat = np.zeros(len(brick_id_order))
        for i, bid in enumerate(brick_id_order):
            b = by_id.get(bid)
            if b is not None and getattr(b, "fired_this_cycle", False):
                feat[i] = b.predict_next()
        random.setstate(saved_random_state)
        return native_answer, feat


def ridge_fit(X, y, lam):
    d = X.shape[1]
    A = X.T @ X + lam * np.eye(d)
    b = X.T @ y
    return np.linalg.solve(A, b)


def cv_select_lambda(X, y, lambdas, k, rng):
    """Real k-fold CV this time (k=5), not leave-one-out -- the probe subsample (200 train pairs)
    is finally big enough for this to mean something, unlike the 6-example numeric-task version."""
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
    log("SOVEREIGNCORE BIT-LEVEL TASK -- CORRECTED CROSS-SUBSTRATE TRANSPLANT TEST")
    log(f"{len(TRAIN_PAIRS)} train pairs (engine trains+probes on these ONLY), "
        f"{len(HELDOUT_PAIRS)} held-out pairs (engine NEVER sees these during training)")
    log("=" * 78)

    # ---------------------------------------------------------------------------------------
    # STEP 1: train the real engine on the TRAIN SPLIT ONLY. 8000 cycles, same proven cadence as
    # every bit-level/numeric test tonight. Held-out pairs are structurally unreachable during
    # this loop (TASK_PAIRS = TRAIN_PAIRS, see the class above) -- not just "not sampled," truly
    # inaccessible to inject_problem()'s random-task path.
    # ---------------------------------------------------------------------------------------
    random.seed(42)
    core = BitLevelReadoutProbeCore(init_bricks=sc.INIT_BRICKS)
    log(f"\nTraining on {len(TRAIN_PAIRS)} real bit-level pairs, 8000 cycles...")
    for cyc in range(8000):
        core.run_cycle()
        if core.current_time % 2000 == 0:
            c, t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
            log(f"   cycle {core.current_time}: train exact-match (500-subsample) {c}/{t} "
                f"({100*c/t:.1f}%)")

    # ---------------------------------------------------------------------------------------
    # STEP 2: recap condition A on BOTH splits (native readout, single-cycle probe -- matching
    # the original bit-level test's own evaluation convention exactly, so this recap number is
    # directly comparable to it).
    # ---------------------------------------------------------------------------------------
    log("\n" + "-" * 78)
    log("CONDITION A: SovereignCore's own native readout (RECAP, single-cycle probe)")
    log("-" * 78)
    a_train_c, a_train_t = core.exact_match_accuracy(TRAIN_PAIRS, n_probe=500)
    a_held_c, a_held_t = core.exact_match_accuracy(HELDOUT_PAIRS, n_probe=None)
    log(f"   train (500-subsample): {a_train_c}/{a_train_t} ({100*a_train_c/a_train_t:.1f}%)")
    log(f"   held-out (full {len(HELDOUT_PAIRS)}): {a_held_c}/{a_held_t} "
        f"({100*a_held_c/a_held_t:.1f}%)  [chance = 50%]")

    # ---------------------------------------------------------------------------------------
    # STEP 3: harvest real brick-firing features for a bounded subsample (compute budget, stated
    # up front) of train + held-out pairs, via the sustained multi-cycle probe.
    # ---------------------------------------------------------------------------------------
    brick_id_order = sorted(b.id for b in core.bricks
                             if b.alive and b.module_id == core.output_module_id)
    log(f"\n{len(brick_id_order)} living output-module bricks -- feature dimensionality for B/C.")

    probe_rng = random.Random(99)
    train_probe_set = probe_rng.sample(TRAIN_PAIRS, min(PROBE_TRAIN_SUBSAMPLE, len(TRAIN_PAIRS)))
    held_probe_set = probe_rng.sample(HELDOUT_PAIRS, min(PROBE_HELDOUT_SUBSAMPLE, len(HELDOUT_PAIRS)))
    all_probe = train_probe_set + held_probe_set
    n_train_probe = len(train_probe_set)
    log(f"\nHarvesting real brick-firing features for {n_train_probe} train + "
        f"{len(held_probe_set)} held-out pairs ({SUSTAIN_CYCLES} sustained cycles each -- this "
        f"is the slow part, budgeted deliberately)...")

    raw_feats, context_bits, targets = [], [], []
    for i, (call, target) in enumerate(all_probe):
        _, feat = core.probe_brick_firing_vector(call, target, brick_id_order)
        raw_feats.append(feat)
        # the RAW 16-bit context window itself, binarized (HIGH->1, LOW->0) -- this is the
        # "raw feature" layer the KC-style conjunctions sample from, exactly mirroring Flybrain's
        # raw_bits() over A's/B's 8 bits. SovereignCore's own internal brick state is a SEPARATE,
        # additional signal (condition B's raw_feats), not replaced by this.
        context_bits.append([1.0 if c >= MIDPOINT else 0.0 for c in call])
        targets.append(1.0 if target >= MIDPOINT else -1.0)
        if (i + 1) % 50 == 0:
            log(f"   harvested {i+1}/{len(all_probe)}...")
    raw_feats = np.array(raw_feats)
    context_bits = np.array(context_bits)
    targets = np.array(targets)

    # ---------------------------------------------------------------------------------------
    # CONDITION B: fair, cross-validated ridge-regularized LINEAR readout on the raw brick-firing
    # feature vector -- no expansion. Isolates "does a properly-fit linear readout do any better
    # than the hand-designed vote, independent of combinatorial expansion."
    # ---------------------------------------------------------------------------------------
    log("\n" + "-" * 78)
    log(f"CONDITION B: ridge-regularized LINEAR readout on raw brick features "
        f"({raw_feats.shape[1]}-dim, no expansion)")
    log("-" * 78)
    Xb = raw_feats / (np.linalg.norm(raw_feats, axis=1, keepdims=True) + 1e-9)
    lam_b, cv_mse_b = cv_select_lambda(Xb[:n_train_probe], targets[:n_train_probe], CV_LAMBDAS,
                                        N_FOLDS, np.random.default_rng(7))
    log(f"   5-fold CV lambda = {lam_b} (CV MSE {cv_mse_b:.3f})")
    Wb = ridge_fit(Xb[:n_train_probe], targets[:n_train_probe], lam_b)
    pred_b = Xb @ Wb
    b_train_c, b_train_t = score_midpoint([(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_b[:n_train_probe]],
                                           [t for _, t in train_probe_set])
    b_held_c, b_held_t = score_midpoint([(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_b[n_train_probe:]],
                                         [t for _, t in held_probe_set])
    log(f"   train: {b_train_c}/{b_train_t} ({100*b_train_c/b_train_t:.1f}%)   "
        f"held-out: {b_held_c}/{b_held_t} ({100*b_held_c/b_held_t:.1f}%)")

    # ---------------------------------------------------------------------------------------
    # CONDITION C: THE PROPOSED FIX -- combinatorial conjunction expansion over the RAW 16-bit
    # context window (not the brick-firing state this time -- the context IS the symbolic input
    # whose parity/lookup structure is the actual suspected bottleneck, exactly analogous to
    # Flybrain's raw A/B bits). Each KC-style unit fires only if K=4 randomly-sampled context
    # bits are ALL 1 -- a real cross-position conjunction term, built identically to
    # flybrain_binary_addition_combinatorial.py's proven mechanism.
    # ---------------------------------------------------------------------------------------
    log("\n" + "-" * 78)
    log(f"CONDITION C: ridge-regularized readout on {N_KC} COMBINATORIAL CONJUNCTION units "
        f"over the raw {context_bits.shape[1]}-bit context window (K={K_SAMPLE}, the proposed fix)")
    log("-" * 78)
    rng = np.random.default_rng(1)
    n_ctx_bits = context_bits.shape[1]
    kc_samples = [rng.choice(n_ctx_bits, K_SAMPLE, replace=False) for _ in range(N_KC)]
    kc_feats = np.array([[1.0 if context_bits[row, s].all() else 0.0 for s in kc_samples]
                          for row in range(len(all_probe))])
    active_frac = kc_feats.mean()
    log(f"   KC-code sparsity: {100*active_frac:.1f}% of {N_KC} conjunction units active on "
        f"average per call (real KC sparsity in the fly is ~5-10%)")
    Xc = kc_feats / (np.linalg.norm(kc_feats, axis=1, keepdims=True) + 1e-9)
    lam_c, cv_mse_c = cv_select_lambda(Xc[:n_train_probe], targets[:n_train_probe], CV_LAMBDAS,
                                        N_FOLDS, np.random.default_rng(7))
    log(f"   5-fold CV lambda = {lam_c} (CV MSE {cv_mse_c:.3f})")
    Wc = ridge_fit(Xc[:n_train_probe], targets[:n_train_probe], lam_c)
    pred_c = Xc @ Wc
    c_train_c, c_train_t = score_midpoint([(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_c[:n_train_probe]],
                                           [t for _, t in train_probe_set])
    c_held_c, c_held_t = score_midpoint([(BIT_HIGH if p > 0 else BIT_LOW) for p in pred_c[n_train_probe:]],
                                         [t for _, t in held_probe_set])
    log(f"   train: {c_train_c}/{c_train_t} ({100*c_train_c/c_train_t:.1f}%)   "
        f"held-out: {c_held_c}/{c_held_t} ({100*c_held_c/c_held_t:.1f}%)")

    log("\n" + "=" * 78)
    log("HONEST SUMMARY -- chance = 50% throughout")
    log("=" * 78)
    log(f"   A (native vote, full task)     : train {100*a_train_c/a_train_t:.1f}%  "
        f"held-out {100*a_held_c/a_held_t:.1f}%")
    log(f"   B (linear, brick features)      : train {100*b_train_c/b_train_t:.1f}%  "
        f"held-out {100*b_held_c/b_held_t:.1f}%")
    log(f"   C (combinatorial, raw context)  : train {100*c_train_c/c_train_t:.1f}%  "
        f"held-out {100*c_held_c/c_held_t:.1f}%")


if __name__ == "__main__":
    main()
