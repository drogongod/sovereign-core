#!/usr/bin/env python3
"""lucy_favorite_color_core.py -- PHASE 1, START: porting Lucy onto the real SovereignCore
substrate (not a reimplementation, not a gradient approximation -- the actual discrete,
evolutionary, non-backprop engine in sovereign_core.py, used via subclassing exactly the way
this project's own proven precedent (sovereign_core_charlm_test.py, D:\\flybrain) already
validated for a sequential/categorical task).

WHY THIS TASK SPECIFICALLY: reuses the exact "favorite color" recall task used all night in
F:\\WampYr_Mamba-3's local-learning investigation (Forward-Forward, PC-ALM, TBPTT, sister-split,
true-chain) -- same shape of problem (evidence stated early, answer asked for much later), same
evaluation discipline. This makes SovereignCore's real result DIRECTLY comparable to every other
substrate already tested tonight, and sets up the natural next experiment: sweep CONTEXT_LEN the
same way the Mamba TBPTT window was swept, to see whether this completely different (non-
gradient, evolutionary, relay-based) substrate shows the same credit-horizon shape or a
different one.

NOT a rewrite of SovereignCore -- only TASK_PAIRS and the reporting methods are new, same
discipline as sovereign_core_charlm_test.py. Text is lowercased and templates trimmed to keep
the byte vocabulary <= STATE_MAX+1=32 (SovereignCore's real, hard dynamic-range constraint --
unlike Mamba's 256-byte vocabulary, every observable brick state here is a strict integer
[0, 31], so the vocabulary itself has to fit, not just be mapped into it).
"""
import sys, os, argparse, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

COLORS = ["blue", "red", "green", "yellow", "purple", "orange", "black", "white", "pink", "gray"]
TEMPLATES = [
    "my favorite color is {c}.",
    "{c} is my favorite color.",
    "i favor {c} above all other colors, {c} is my favorite.",
    "if you ask my favorite, i will always say {c}.",
    "everyone knows {c} is my favorite, my one true favorite color.",
]
CONTEXT_LEN = 3  # matches sovereign_core_charlm_test.py's proven default; sweepable later,
# same role as WINDOW in the Mamba TBPTT investigation -- the real next experiment for this file.


def make_corpus(n_examples: int, seed: int = 0):
    """Generates real favorite-color example TEXTS (not just isolated word fragments like the
    char-LM precedent) -- the evidence-to-query DISTANCE is the whole point of this task, same
    as every other substrate tested tonight."""
    rng = random.Random(seed)
    texts = []
    for _ in range(n_examples):
        color = rng.choice(COLORS)
        n_sentences = rng.randint(3, 4)
        sentences = rng.sample(TEMPLATES, min(n_sentences, len(TEMPLATES)))
        body = " ".join(t.format(c=color) for t in sentences)
        texts.append(f"{body} what is my favorite color? {color}")
    return texts


def build_task_pairs(texts, context_len=CONTEXT_LEN):
    vocab = sorted(set(ch for t in texts for ch in t))
    assert len(vocab) <= sc.STATE_MAX + 1, (
        f"vocab size {len(vocab)} exceeds SovereignCore's real [0,{sc.STATE_MAX}] dynamic "
        f"range -- trim TEMPLATES/corpus, do not change STATE_MAX (that is a hard substrate "
        f"constant, not a tunable for this task).")
    char_to_idx = {c: i for i, c in enumerate(vocab)}
    idx_to_char = {i: c for c, i in char_to_idx.items()}
    pairs = {}
    collisions = []
    for t in texts:
        for i in range(context_len, len(t)):
            ctx = tuple(char_to_idx[c] for c in t[i - context_len:i])
            tgt = char_to_idx[t[i]]
            if ctx in pairs and pairs[ctx] != tgt:
                collisions.append((ctx, pairs[ctx], tgt))
            pairs[ctx] = tgt
    return list(pairs.items()), vocab, char_to_idx, idx_to_char, collisions


CORPUS_TEXTS = make_corpus(n_examples=40, seed=0)
TASK_PAIRS_RAW, VOCAB, CHAR_TO_IDX, IDX_TO_CHAR, COLLISIONS = build_task_pairs(CORPUS_TEXTS)


class LucyFavoriteColorCore(sc.SovereignCore):
    TASK_PAIRS = TASK_PAIRS_RAW

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.wolfpack_sick_total = 0
        self.wolfpack_grafted_total = 0
        self.wolfpack_reset_total = 0

    def run_cycle(self):
        super().run_cycle()
        n_sick, n_grafted = getattr(self, "_last_wolfpack", (0, 0))
        self.wolfpack_sick_total += n_sick
        self.wolfpack_grafted_total += n_grafted
        self.wolfpack_reset_total += n_sick

    def report_state_pinning(self):
        living = [b for b in self.bricks if b.alive]
        if not living:
            return
        n = len(living)
        at_max = sum(1 for b in living
                     if b.mem >= sc.STATE_MAX or b.think >= sc.STATE_MAX or b.relay_strength >= sc.STATE_MAX)
        at_min = sum(1 for b in living
                     if b.mem <= sc.STATE_MIN and b.think <= sc.STATE_MIN and b.relay_strength <= sc.STATE_MIN)
        print(f"    state-pin check: {at_max}/{n} ({100*at_max/n:.1f}%) at STATE_MAX, "
              f"{at_min}/{n} ({100*at_min/n:.1f}%) at STATE_MIN  |  wolfpack totals: "
              f"{self.wolfpack_sick_total} sick, {self.wolfpack_grafted_total} grafted, "
              f"{self.wolfpack_reset_total} reset")

    def exact_match_accuracy(self, n_probe=None):
        """Same discipline as the whole night's work: exact match, not the substrate's own
        graded partial-credit scoring (meaningless for arbitrary character indices)."""
        pairs = self.TASK_PAIRS if n_probe is None else self.TASK_PAIRS[:n_probe]
        correct = 0
        for call, target in pairs:
            self.inject_problem("probe", 1.0, forced_call=list(call))
            self._update_bricks()
            self._fire_relays()
            resp = self._read_response()
            if resp is not None and round(resp) == target:
                correct += 1
        return correct, len(pairs)


def main():
    print("=" * 70)
    print("LUCY ON SOVEREIGNCORE -- PHASE 1, START (favorite-color recall task)")
    print("=" * 70)
    print(f"{len(TASK_PAIRS_RAW)} distinct ({CONTEXT_LEN}-char-context -> next-char) pairs, "
          f"vocab size {len(VOCAB)} (SovereignCore's hard limit: {sc.STATE_MAX + 1}): {VOCAB}")
    if COLLISIONS:
        print(f"  NOTE: {len(COLLISIONS)} genuinely ambiguous contexts (same {CONTEXT_LEN}-char "
              f"window precedes different next-chars) -- kept last-seen, real ambiguity not hidden.")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8000)
    ap.add_argument("--init-bricks", type=int, default=sc.INIT_BRICKS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pin-check-every", type=int, default=1000)
    ap.add_argument("--exact-check-every", type=int, default=1000)
    args = ap.parse_args()

    random.seed(args.seed)

    core = LucyFavoriteColorCore(init_bricks=args.init_bricks)
    for _ in range(args.cycles):
        core.run_cycle()
        if core.current_time % args.pin_check_every == 0:
            core.report_state_pinning()
        if core.current_time % args.exact_check_every == 0:
            correct, total = core.exact_match_accuracy()
            print(f"    EXACT-MATCH probe: {correct}/{total} ({100*correct/total:.1f}%) contexts "
                  f"answered with the exact correct next-char", flush=True)

    print("Lucy-on-SovereignCore, phase 1 start, halted gracefully.")


if __name__ == "__main__":
    main()
