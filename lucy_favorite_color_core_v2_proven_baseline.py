#!/usr/bin/env python3
"""v2 -- same as lucy_favorite_color_core.py, but forces the PROVEN baseline config: relay
split-handoff to a sister cell WITHOUT content-matching (WOLFPACK_SISTER_MATCH=False). Per
Jonathan directly (2026-10-16): the content-matched "socialization" sister-selection NEVER
actually worked for him; what worked was the plain relay handoff -- excess signal redirected to
a different brick in the same module (never source, never feeders), no "pick the most similar
one" step. Testing that exact config, not the untested refinement, for a fair first result."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

sc.WOLFPACK_SISTER_MATCH = False  # the real correction -- test the PROVEN baseline, not the
                                   # content-matching refinement that was never confirmed working

from lucy_favorite_color_core import LucyFavoriteColorCore, TASK_PAIRS_RAW, VOCAB, COLLISIONS, CONTEXT_LEN
import argparse, random


def main():
    print("=" * 70)
    print("LUCY ON SOVEREIGNCORE -- v2, PROVEN BASELINE (WOLFPACK_SISTER_MATCH=False)")
    print("=" * 70)
    print(f"{len(TASK_PAIRS_RAW)} distinct ({CONTEXT_LEN}-char-context -> next-char) pairs, "
          f"vocab size {len(VOCAB)}: {VOCAB}")
    print(f"  WOLFPACK_SISTER_MATCH = {sc.WOLFPACK_SISTER_MATCH} (forced OFF -- the proven config)")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8000)
    ap.add_argument("--init-bricks", type=int, default=sc.INIT_BRICKS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pin-check-every", type=int, default=500)
    ap.add_argument("--exact-check-every", type=int, default=500)
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

    print("Lucy-on-SovereignCore v2 (proven baseline), halted gracefully.")


if __name__ == "__main__":
    main()
