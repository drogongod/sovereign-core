#!/usr/bin/env python3
"""v3 -- same proven baseline (WOLFPACK_SISTER_MATCH=False) as v2, but fixes the structural
ambiguity found in v1/v2: CONTEXT_LEN=3 meant the context window right before the color answer
was almost always identical regardless of which color was correct (e.g. "r? " precedes every
color), so SovereignCore's own learning rule never had access to the answer-determining
information. CONTEXT_LEN=25 cuts collisions from 1135 to 224 (measured directly) -- long enough
to usually include the most recent color restatement before the query, at the real cost of a
much larger distinct-pattern count (212 -> 2174) to actually learn."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

sc.WOLFPACK_SISTER_MATCH = False

import lucy_favorite_color_core as base
base.CONTEXT_LEN = 10
base.CORPUS_TEXTS = base.make_corpus(n_examples=40, seed=0)
base.TASK_PAIRS_RAW, base.VOCAB, base.CHAR_TO_IDX, base.IDX_TO_CHAR, base.COLLISIONS = \
    base.build_task_pairs(base.CORPUS_TEXTS, context_len=base.CONTEXT_LEN)
base.LucyFavoriteColorCore.TASK_PAIRS = base.TASK_PAIRS_RAW

import argparse, random


def main():
    print("=" * 70)
    print(f"LUCY ON SOVEREIGNCORE -- v3, WIDER CONTEXT (context_len={base.CONTEXT_LEN}, fixes "
          f"the structural ambiguity bug)")
    print("=" * 70)
    print(f"{len(base.TASK_PAIRS_RAW)} distinct ({base.CONTEXT_LEN}-char-context -> next-char) "
          f"pairs, vocab size {len(base.VOCAB)}, {len(base.COLLISIONS)} residual collisions "
          f"(was 1135 at context_len=3)")
    print(f"  WOLFPACK_SISTER_MATCH = {sc.WOLFPACK_SISTER_MATCH}")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8000)
    ap.add_argument("--init-bricks", type=int, default=sc.INIT_BRICKS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pin-check-every", type=int, default=1000)
    ap.add_argument("--exact-check-every", type=int, default=1000)
    args = ap.parse_args()

    random.seed(args.seed)
    core = base.LucyFavoriteColorCore(init_bricks=args.init_bricks)
    for _ in range(args.cycles):
        core.run_cycle()
        if core.current_time % args.pin_check_every == 0:
            core.report_state_pinning()
        if core.current_time % args.exact_check_every == 0:
            correct, total = core.exact_match_accuracy()
            print(f"    EXACT-MATCH probe: {correct}/{total} ({100*correct/total:.1f}%) contexts "
                  f"answered with the exact correct next-char", flush=True)

    print("Lucy-on-SovereignCore v3 (wider context), halted gracefully.")


if __name__ == "__main__":
    main()
