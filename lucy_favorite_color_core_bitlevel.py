#!/usr/bin/env python3
"""Lucy on SovereignCore, BIT-LEVEL re-encoding, 2026-10-16. Jonathan's own hypothesis, stated
directly: the substrate's real positive result was on a NUMERIC/bit-pattern task
(lucy_original_numeric_task.py: TaskCorrect 0.74-0.89, exact-match peak 66.7%), while every
character-level encoding of the SAME favorite-color recall task stayed at chance (1.4-4.2%,
TaskCorrect ~0.2-0.3). This re-encodes the identical task at the BIT level instead of the
character level: every character becomes its 8 raw bits (0/1), concatenated into one long
bit-stream, with (context_len_bits -> next_bit) pairs built the same way the char-level harness
built (context_len_chars -> next_char) pairs. Vocab is now literally {0, 1} -- as close to
SovereignCore's own proven numeric domain as this task can get while still being the same
underlying recall problem (color stated early, asked for much later).

CONTEXT_LEN_BITS=16 (2 characters), corpus of 5 examples (850 distinct pairs) -- reduced from an
original 80-bit/40-example design that proved computationally impractical (7426 pairs made the
substrate's sleep-replay phase take 20+ minutes per event). First real run at this smaller scale
gave a weak, noisy, non-sustained signal (oscillated 50.2-58.1%, chance=50%) -- real but far
short of the numeric task's strength. REAL FIX applied after Jonathan's own instinct that
something was missing: bit values were literal 0/1, an almost-infinitesimal distinction at the
very bottom of the substrate's [0, STATE_MAX] dynamic range (smaller than the accumulator-bridge
commit threshold itself, 1.0) -- rescaled to 0/STATE_MAX(31) instead, matching the real spread
(7-26) the numeric task's targets actually used.
"""
import sys, os, argparse, random, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sovereign_core as sc

sc.WOLFPACK_SISTER_MATCH = False  # proven baseline, same discipline as every test tonight

COLORS = ["blue", "red", "green", "yellow", "purple", "orange", "black", "white", "pink", "gray"]
TEMPLATES = [
    "my favorite color is {c}.",
    "{c} is my favorite color.",
    "i favor {c} above all other colors, {c} is my favorite.",
    "if you ask my favorite, i will always say {c}.",
    "everyone knows {c} is my favorite, my one true favorite color.",
]
CONTEXT_LEN_BITS = 16  # = 2 characters -- reduced from 80 after the original run proved
# impractically slow (7426 pairs, sleep-replay alone took 20+ min with no end in sight); this
# gives ~850 pairs, directly comparable in scale to the char-level test's 905 pairs.


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


def text_to_bits(text: str) -> list:
    """Every character -> its 8 raw bits, MSB first, concatenated."""
    bits = []
    for byte in text.encode("utf-8"):
        bits.extend([(byte >> i) & 1 for i in range(7, -1, -1)])
    return bits


# 2026-10-16, REAL FIX: Jonathan's own instinct ("I feel I forgot something") was right. The
# numeric task's real targets span 7-26 -- a spread of 19 across the substrate's [0, STATE_MAX]
# range, fully separated. Literal 0/1 bit values ask the substrate to resolve an almost-
# infinitesimal distinction right at the bottom of its dynamic range -- the accumulator-bridge
# threshold alone is 1.0, i.e. SMALLER than the entire gap between a 0 and a 1 target. Rescaling
# bit 0 -> 0, bit 1 -> STATE_MAX (both context AND target) gives the substrate's actual working
# range to operate in, matching the numeric task's real scale instead of fighting it.
BIT_LOW = 0
BIT_HIGH = sc.STATE_MAX  # 31


def scale_bit(b: int) -> int:
    return BIT_HIGH if b else BIT_LOW


def build_bit_task_pairs(texts, context_len_bits=CONTEXT_LEN_BITS):
    pairs = {}
    collisions = []
    for t in texts:
        bits = text_to_bits(t)
        for i in range(context_len_bits, len(bits)):
            ctx = tuple(scale_bit(b) for b in bits[i - context_len_bits:i])
            tgt = scale_bit(bits[i])
            if ctx in pairs and pairs[ctx] != tgt:
                collisions.append((ctx, pairs[ctx], tgt))
            pairs[ctx] = tgt
    return list(pairs.items()), collisions


CORPUS_TEXTS = make_corpus(n_examples=5, seed=0)
TASK_PAIRS_RAW, COLLISIONS = build_bit_task_pairs(CORPUS_TEXTS)


class LucyBitLevelCore(sc.SovereignCore):
    TASK_PAIRS = TASK_PAIRS_RAW

    def exact_match_accuracy(self, n_probe=2000):
        """Full pair set can be large (thousands of bit-windows) -- probe a fixed random
        SUBSET each check for speed, same evaluation discipline, just sub-sampled.

        2026-10-16 fix: targets are now 0 or STATE_MAX (31), not literal 0/1 -- round(resp)
        would require resp to land EXACTLY on one of two far-apart extremes (an absurdly strict
        bar; a confused/middling resp like 15 used to round-match a 0/1 target half the time by
        luck, now matches neither). Correctness is now a MIDPOINT THRESHOLD: closer to 0 or
        closer to STATE_MAX, matching the real binary decision being asked, not exact equality."""
        # 2026-10-17, REAL FIX (same bug class as the engine's own %500 diagnostic, a SEPARATE
        # instance -- caught after Jonathan + an independent model both flagged that
        # _update_bricks()/_fire_relays() are real training machinery, not passive reads):
        # this method called those two functions on `self` once per probed pair -- directly
        # mutating brick energy/refractory/accumulators/prediction-error/IMMUNE+TEACH-eligibility
        # and relay split/usage counters + delivering real signal to sister cells, every single
        # evaluation call. Confirmed directly: with the engine's own internal diagnostic fully
        # DISABLED, the `splits` counter still spiked 9.5x (39961->117204 across cycles 500-600,
        # vs. a steady ~8000-8300/100cyc baseline everywhere else) purely from THIS method being
        # called -- the earlier context_tokens snapshot/restore never touched any of this.
        # REAL fix: run the probe on a throwaway deep-copy of the whole substrate (zero effect on
        # `self` by construction), and save/restore the GLOBAL random state too, so evaluation
        # doesn't even change which pseudo-random draws come next in the real run.
        pairs = self.TASK_PAIRS if n_probe is None or n_probe >= len(self.TASK_PAIRS) \
            else random.sample(self.TASK_PAIRS, n_probe)
        midpoint = BIT_HIGH / 2.0
        saved_random_state = random.getstate()
        clone = copy.deepcopy(self)
        correct = 0
        for call, target in pairs:
            clone.inject_problem("probe", 1.0, forced_call=list(call))
            clone._update_bricks()
            clone._fire_relays()
            resp = clone._read_response()
            predicted = None if resp is None else (BIT_HIGH if resp >= midpoint else BIT_LOW)
            if predicted == target:
                correct += 1
        random.setstate(saved_random_state)
        return correct, len(pairs)


def bits_to_text(byte_ids):
    byte_vals = []
    for i in range(0, len(byte_ids) - 7, 8):
        v = 0
        for b in byte_ids[i:i + 8]:
            v = (v << 1) | b
        byte_vals.append(v)
    return bytes(byte_vals).decode("utf-8", errors="replace")


def main():
    print("=" * 70)
    print(f"LUCY ON SOVEREIGNCORE -- BIT-LEVEL RE-ENCODING (context={CONTEXT_LEN_BITS} bits "
          f"= {CONTEXT_LEN_BITS // 8} chars)")
    print("=" * 70)
    print(f"{len(TASK_PAIRS_RAW)} distinct bit-context->next-bit pairs, "
          f"{len(COLLISIONS)} residual collisions, vocab={{0,1}}")
    print(f"  WOLFPACK_SISTER_MATCH = {sc.WOLFPACK_SISTER_MATCH}")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8000)
    ap.add_argument("--init-bricks", type=int, default=sc.INIT_BRICKS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--exact-check-every", type=int, default=500)
    args = ap.parse_args()

    random.seed(args.seed)
    core = LucyBitLevelCore(init_bricks=args.init_bricks)
    for _ in range(args.cycles):
        core.run_cycle()
        if core.current_time % args.exact_check_every == 0:
            correct, total = core.exact_match_accuracy()
            print(f"    EXACT-MATCH probe (bit-level, random 2000-subset): {correct}/{total} "
                  f"({100*correct/total:.1f}%)", flush=True)

    print("Lucy-on-SovereignCore, bit-level, halted gracefully.")


if __name__ == "__main__":
    main()
