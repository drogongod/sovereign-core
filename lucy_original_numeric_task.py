#!/usr/bin/env python3
"""Testing SovereignCore on its ORIGINAL, built-in task -- the one it was actually designed and
(per Jonathan) actually proven to work on, before any char-level/language task was ever tried on
it. Real code, unmodified TASK_PAIRS (sovereign_core.py:779-786): 6 fixed (a,b,c)->d triples, ALL
following the same "+2, continue the arithmetic sequence" rule -- documented in the file's own
comment as a genuine generalization test ("the seed knows ONE... the OTHERS must be learned by
GENERALIZING the +2 operation -- a memorizer... fails them, only a rule-extractor wins").

Purpose: find out whether the chance-level results on the favorite-color/char-context tasks
(v1-v4.21b, all four at 1.4-4.2%) reflect a real limit of the substrate, or whether the substrate
actually works fine on the kind of task it was built for and only struggles with language-shaped
tasks specifically -- a real, different, answerable question, per Jonathan's own hypothesis that
success here could mean this substrate is suited to bit/numeric-level modeling, not character-
level language modeling.
"""
import sys, os, argparse, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

sc.WOLFPACK_SISTER_MATCH = False  # proven baseline, same discipline as every other test tonight


class OriginalTaskCore(sc.SovereignCore):
    # TASK_PAIRS deliberately NOT overridden -- this is the real, original, built-in task.

    def exact_match_accuracy(self):
        # 2026-10-17, REAL FIX (the diagnostic-probe bug class, second instance -- found after
        # the engine's own %500 probe was fixed and Jonathan + an independent model both flagged
        # that _update_bricks()/_fire_relays() are NOT passive reads): this method called those
        # same two real-training functions once per probed pair, on `self` -- directly mutating
        # brick energy/refractory/commit_accumulators/prediction-error/IMMUNE+TEACH-eligibility
        # and relay split/usage counters + delivering real signal to sister cells, every single
        # evaluation. context_tokens snapshot/restore (the earlier fix) never touched any of
        # this. REAL fix: run the probe on a throwaway deep-copy of the whole substrate, so
        # nothing it does can touch the real run; and save/restore the GLOBAL random state around
        # it too, so the probe doesn't even perturb which pseudo-random draws come next in the
        # real run. This is now a true measurement -- zero effect on `self`, by construction.
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in clone.TASK_PAIRS:
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone._update_bricks()
            clone._fire_relays()
            resp = clone._read_response()
            if resp is not None and round(resp) == target:
                correct += 1
        random.setstate(saved_random_state)
        return correct, len(self.TASK_PAIRS)

    def generalization_check(self):
        """The real test the file's own comment describes: does it know the OPERATION (+2), or
        did it just memorize the one seeded triple? Probe held-out (a,b,c)->a+6 triples that were
        NEVER in TASK_PAIRS at all, same rule, never seen."""
        held_out = [((3, 5, 7), 9), ((30, 29, 28), 27), ((8, 10, 12), 14), ((0, 2, 4), 6)]
        # (30,29,28)->27 deliberately breaks the "+2 increasing" pattern (DEcreasing by 1) to
        # check whether it learned "+2 specifically" vs. some other spurious correlation.
        correct = 0
        for call, target in held_out:
            self.inject_problem("probe", 1.0, forced_call=list(call))
            self._update_bricks()
            self._fire_relays()
            resp = self._read_response()
            got_it = resp is not None and round(resp) == target
            correct += int(got_it)
            print(f"      held-out {call} -> {resp} (want {target})  {'OK' if got_it else 'WRONG'}")
        return correct, len(held_out)


def main():
    print("=" * 70)
    print("LUCY ON SOVEREIGNCORE -- THE ORIGINAL NUMERIC TASK (unmodified, built-in TASK_PAIRS)")
    print("=" * 70)
    print(f"TASK_PAIRS: {sc.SovereignCore.TASK_PAIRS}")
    print(f"  WOLFPACK_SISTER_MATCH = {sc.WOLFPACK_SISTER_MATCH}")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8000)
    ap.add_argument("--init-bricks", type=int, default=sc.INIT_BRICKS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--exact-check-every", type=int, default=500)
    args = ap.parse_args()

    random.seed(args.seed)
    core = OriginalTaskCore(init_bricks=args.init_bricks)
    for _ in range(args.cycles):
        core.run_cycle()
        if core.current_time % args.exact_check_every == 0:
            correct, total = core.exact_match_accuracy()
            print(f"    EXACT-MATCH probe: {correct}/{total} ({100*correct/total:.1f}%)", flush=True)

    print("\n=== GENERALIZATION CHECK (held-out +2-rule triples, NEVER in TASK_PAIRS) ===")
    gcorrect, gtotal = core.generalization_check()
    print(f"\nGeneralization: {gcorrect}/{gtotal} = {100*gcorrect/gtotal:.1f}%")
    print("Lucy-on-SovereignCore, original numeric task, halted gracefully.")


if __name__ == "__main__":
    main()
