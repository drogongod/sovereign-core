#!/usr/bin/env python3
"""Lucy on SovereignCore v4.21b (the RESURRECTION lineage, D:\\flybrain\\Max_sovereign_core_v4_21.py)
-- Jonathan's own hint: "in flybrain the original sovereign core should still be there that
works." This is an EARLIER, distinct lineage from the v4.3 tested in v1-v3 -- no Wolfpack/
sister-match mechanism at all (confirmed: grepped the file, neither exists), but has a real
anti-extinction "RESURRECTION" pass the v4.3 lineage does not: if a true answer has NO living
winners left (went extinct), the garden/sleep pass replants it directly from ground truth instead
of only ever cloning from whichever bricks currently survive. Same favorite-color task, same
context_len=10 fix as v3 (wider context, removes the structural ambiguity bug), for direct
comparison against the v4.3 results already recorded.
"""
import sys, os, argparse, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core_v4_21 as sc

COLORS = ["blue", "red", "green", "yellow", "purple", "orange", "black", "white", "pink", "gray"]
TEMPLATES = [
    "my favorite color is {c}.",
    "{c} is my favorite color.",
    "i favor {c} above all other colors, {c} is my favorite.",
    "if you ask my favorite, i will always say {c}.",
    "everyone knows {c} is my favorite, my one true favorite color.",
]
CONTEXT_LEN = 10


def make_corpus(n_examples: int, seed: int = 0):
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
    assert len(vocab) <= sc.STATE_MAX + 1, f"vocab size {len(vocab)} exceeds [0,{sc.STATE_MAX}]"
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


class LucyV421Core(sc.SovereignCore):
    TASK_PAIRS = TASK_PAIRS_RAW

    def exact_match_accuracy(self, n_probe=None):
        # 2026-10-17, REAL FIX -- see lucy_favorite_color_core.py for the full writeup: this
        # method called _update_bricks()/_fire_relays() on `self`, real training machinery not
        # passive reads. Runs the probe on a throwaway deep-copy instead (zero effect on `self`),
        # and restores the global random state too.
        pairs = self.TASK_PAIRS if n_probe is None else self.TASK_PAIRS[:n_probe]
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in pairs:
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone._update_bricks()
            clone._fire_relays()
            resp = clone._read_response()
            if resp is not None and round(resp) == target:
                correct += 1
        random.setstate(saved_random_state)
        return correct, len(pairs)


def main():
    print("=" * 70)
    print("LUCY ON SOVEREIGNCORE v4.21b -- RESURRECTION lineage (context_len=10)")
    print("=" * 70)
    print(f"{len(TASK_PAIRS_RAW)} distinct ({CONTEXT_LEN}-char-context -> next-char) pairs, "
          f"vocab size {len(VOCAB)}, {len(COLLISIONS)} residual collisions")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8000)
    ap.add_argument("--init-bricks", type=int, default=sc.INIT_BRICKS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--exact-check-every", type=int, default=1000)
    args = ap.parse_args()

    random.seed(args.seed)
    core = LucyV421Core(init_bricks=args.init_bricks)
    for _ in range(args.cycles):
        core.run_cycle()
        if core.current_time % args.exact_check_every == 0:
            correct, total = core.exact_match_accuracy()
            print(f"    EXACT-MATCH probe: {correct}/{total} ({100*correct/total:.1f}%) contexts "
                  f"answered with the exact correct next-char", flush=True)

    print("Lucy-on-SovereignCore-v4.21b, halted gracefully.")


if __name__ == "__main__":
    main()
