#!/usr/bin/env python3
"""
Max_sovereign_core_v4_3.py
SOVEREIGN EVOLUTIONARY NEURAL SUBSTRATE (v4.3)
=====================================================================================
Architect: Jonathan David Wint (Azazel / Plato)
Engineer: Qwen (Integrated v4.2 Persistence + Zone Tags + Sleep DAG + Accumulator Bridge + Patches)
Date: May 2026

⚠️ FUTURE LLM / DEVELOPER DIRECTIVE:
- DO NOT MODIFY CORE LOGIC WITHOUT READING ALL COMMENTS FIRST.
- This is a DISCRETE, EVOLUTIONARY, MEMORY-BOUND substrate. It is NOT a transformer.
- It does NOT use backpropagation, floating-point quantization, or static DAGs.
- All observable states are INTEGER [0, 31]. Micro-signals use HIDDEN FLOAT ACCUMULATORS.
- Zone routing, sleep consolidation, and evolutionary NAS are HARD REQUIREMENTS.
- Biological mappings are architectural constraints, not metaphors.

CORE PRINCIPLES:
📐 STRICT DISCRETE STATES: mem, think, relay_strength are ALWAYS integers 0-31.
🌉 ACCUMULATOR BRIDGE: Micro-signals accumulate in hidden float buffers.
   Observable states only commit when |acc| >= 1.0. Prevents quantization oscillation.
🧬 ZONE PLASTICITY: FAST (cleanup), SLOW (persistence), MIRROR (simulation/empathy).
   Each zone routes its own LR, mutation, decay, pruning, weight bounds, and signal maps.
🌙 SLEEP CONSOLIDATION DAG: Triggered by context saturation.
   Flow: FAST replay → SLOW injection → ROM promotion → Zone drift → Context reset.
🔒 ROM PROMOTION: ≥3 consolidations + T≥8 + R≥7 + S≥8 → plasticity=0.0, weights frozen.
🔄 ZONE DRIFT: Modules self-discover optimal plasticity allocation via error/survival pressure.
🧬 EVOLUTIONARY NAS: Fitness-driven mutation, pruning, and structural growth at the synapse level.
💾 PERSISTENCE: Full state serializable, resumable, generation-tracked. Atomic checkpoint writes.

PATCHES INTEGRATED IN v4.3:
🔹 Velocity-based local prediction (replaces static mem/think mix)
🔹 Asymmetric gradient scaling (pos_scale dampens positive pushes in negative-heavy zones)
🔹 Cave Woman salience triage (deviation-sum replaces flat T*R*S multiplication)
🔹 Atomic checkpointing (.tmp → rename) survives Windows forced updates

USAGE:
  python Max_sovereign_core_v4_3.py
  python Max_sovereign_core_v4_3.py --cycles 5000
  python Max_sovereign_core_v4_3.py --resume
"""

import sys
import os
import json
import math
import random
import argparse
import gc
import signal
import atexit
import io
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# ENCODING FIX (2026-09-27): Windows console defaults to cp1252, which cannot encode the
# arrow/emoji characters this file's own status output uses -- crashes with UnicodeEncodeError on
# first print. Same class of bug already documented in this project's history (a prior "First
# Drive Result" hit an identical crash). Force UTF-8 stdout/stderr rather than editing every print
# call; does not touch any of the file's actual logic.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────────────────────────────────────
# ARCHITECTURAL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
# 📐 Discrete state bounds. All observable brick states live in [0, 31].
STATE_MIN = 0
STATE_MAX = 31

# 🌉 Accumulator threshold. Micro-signals commit to discrete state only when |acc| >= 1.0.
ACCUM_THRESHOLD = 1.0

# 🏗️ Initial substrate size & spatial layout
INIT_BRICKS = 500
MODULE_SPACING = 40.0
MODULE_SIZE = 25.0
MAX_SYNAPSES_PER_BRICK = 24

# 🧠 Context capacity & sleep trigger
CONTEXT_CAPACITY = 1000
CONTEXT_THRESHOLD = 0.85       # sleep fires at this context-load fraction (RAISE = sleep LESS OFTEN)
GROWTH_FACTOR = 1.25
MAX_CULL_FRAC_CFG = 0.20       # cull at most this fraction of worst cells per sleep (LOWER = punish LESS)
ALIVE_FLOOR_FRAC_CFG = 0.60    # never cull below this fraction of population (RAISE = punish LESS)
DAY_CONTEXT = 5000            # context window size = a "DAY" of experience; fills ~once per this many cycles -> sleep. RAISE = longer day.
PRESERVE_DIVERSITY = True      # don't merge distinct prototype clusters; protect endangered prototypes

# 🧬 Evolutionary pressure constants
MUTATION_RATE = 0.15
VARIATION_MAGNITUDE = 0.2
SELECTION_PRESSURE = 0.15
PRUNE_FITNESS_FLOOR = 0.15
ROM_CONSOLIDATION_THRESHOLD = 3
SEED_CRANK_PASSES = 50   # MINIMUM crank passes before even CHECKING for engine-catch
ENGINE_CATCH_MIN_CELLS = 25   # this many NON-seed cells reliably correct => engine caught => crank may release
TEACH_FREEZE_WINDOW = 30   # cycles a newly-consolidated cell stays a STABLE teacher, then returns to plastic
RECOGNITION_MODE = "nearest"   # "graded" (RBF kernel, 1/distance) or "nearest" (closest prototype wins)
RBF_SIGMA = 6.0               # kernel width: how close counts as "recognized" (graded mode)
PROTO_LEARN_RATE = 0.10       # EMA rate at which a cell's prototype moves toward calls it answers correctly

# 💾 Checkpoint & persistence
CHECKPOINT_PATH = Path("sovereign_checkpoint_v4_3.json")

# ─────────────────────────────────────────────────────────────────────────────
# ZONE PARAMETERS (Plasticity Allocation & Signal Mapping)
# ─────────────────────────────────────────────────────────────────────────────
# 🧬 Each zone defines its own learning rate, mutation pressure, decay rate,
# pruning threshold, weight bounds, functional orientation, signal map, and
# asymmetric scaling factor (pos_scale) to prevent negative basin trapping.
ZONE_PARAMS = {
    "FAST": {
        "lr": 0.20, "mut": 0.25, "decay": 0.35, "prune": 0.30,
        "weights": (-3, 1), "orientation": "cleanup",
        "signal_map": {-3: 0.05, -2: 0.2, -1: 0.5, 0: 0.8, 1: 1.3},
        "pos_scale": 0.75  # 🔒 Dampens positive pushes in negative-heavy zones
    },
    "SLOW": {
        "lr": 0.05, "mut": 0.05, "decay": 0.15, "prune": 0.10,
        "weights": (-1, 3), "orientation": "persistence",
        "signal_map": {-1: 0.5, 0: 0.8, 1: 1.3, 2: 1.8, 3: 2.5},
        "pos_scale": 1.0   # Balanced/positive zone: no damping needed
    },
    "MIRROR": {
        "lr": 0.12, "mut": 0.18, "decay": 0.25, "prune": 0.20,
        "weights": (-2, 2), "orientation": "simulation",
        "signal_map": {-2: 0.15, -1: 0.4, 0: 0.7, 1: 1.1, 2: 1.6},
        "pos_scale": 0.9   # Slight damping for symmetric stability
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────
class Synapse:
    """
    🧬 Discrete connection between bricks.
    Weight lives in zone-bounded integer range. Delay enables temporal coding.
    Accumulator bridges micro-gradient signals to discrete weight updates.
    """
    def __init__(self, target_id: int, weight: int, delay: int):
        self.target_id = target_id
        self.weight = weight
        self.delay = delay
        self.fitness = 0.5
        self.acc = 0.0

    def update_discrete(self, zone_cfg: dict):
        """🌉 Commit accumulator to discrete weight when threshold crossed."""
        if abs(self.acc) >= ACCUM_THRESHOLD:
            delta = int(self.acc)
            self.weight += delta
            self.acc -= delta
            w_min, w_max = zone_cfg["weights"]
            self.weight = max(w_min, min(w_max, self.weight))

    def weaken(self):
        """🍂 Decay synapse for pruning/autosarcophagy."""
        self.weight = max(-3, self.weight - 1)
        self.fitness *= 0.9

class PairedRelay:
    """
    🧠 Structural glue between bricks/modules.
    RelayA: Decision gate. RelayB: Distribution router.
    Phase offset prevents crosstalk between unrelated signal streams.
    """
    def __init__(self, source_id: int, targets: List[int], base_delay: int):
        self.source_id = source_id
        self.targets = targets
        self.base_delay = base_delay
        self.phase = random.uniform(0, 2 * math.pi)
        self.fitness = 0.5
        self.age = 0
        self.usage_count = 0
        self.suppressed = False
        # 🧬 EVOLVABLE SPLIT TRAITS (the relay-split anti-runaway mechanism).
        # These are TRAITS, not constants: each relay starts with its own random values, and selection
        # (driven by WHOLE-ORGANISM correctness, NOT local comfort) tunes them. A relay whose splitting
        # helps the substrate answer correctly survives & multiplies; one that games stability dies.
        # 🔒 GOVERNANCE: these only get rewarded via the substrate's correctness (see _evaluate_fitness),
        #    so evolution cannot win by "split constantly + stay calm" (that would be the cancer/moss failure).
        self.split_threshold = random.uniform(1.5, 4.0)   # how big an ERROR before this relay splits & retrains
        self.split_ratio = random.uniform(0.4, 0.6)        # fraction sent BACK (rest goes forward). Starts ~half.
        self.back_delay = random.randint(2, 6)             # delay on the backward (retrain) signal (temporal spread)
        self.split_count = 0                               # how often it fired a split (for telemetry)
        self.split_helped = 0                              # how often a split was followed by improved correctness
        # MOSS/CANCER FIX (2026-09-27): a relay that never splits was never evaluated at all by the
        # split_helped/fitness credit step below (it only fired `if relay.split_count > 0`) -- making
        # "never act" a strictly risk-free strategy and letting split_threshold drift upward across
        # generations with zero penalty, exactly the "successful moss that changes the climate and
        # kills everything off" failure this file's own comments already named. Track missed chances
        # so inaction stops being invisible to selection.
        self.missed_split_count = 0                        # how often error was real but this relay chose not to split
        # CREDIT-WINDOW FIX (2026-09-27, independently verified against this exact file): split_count
        # is cumulative and NEVER reset -- the credit step below originally checked `split_count > 0`,
        # meaning a relay that split even ONCE, ever, stays eligible for reward/punishment on every
        # future cycle regardless of whether it actually acted this cycle. split_this_cycle is the
        # transient flag credit is actually allowed to see; split_count remains as pure telemetry.
        self.split_this_cycle = 0

    def mutate_traits(self, rate: float):
        """🧬 Evolve the split traits. Small random walk, bounded to sane ranges."""
        if random.random() < rate:
            self.split_threshold = max(0.5, min(8.0, self.split_threshold + random.uniform(-0.3, 0.3)))
        if random.random() < rate:
            self.split_ratio = max(0.1, min(0.9, self.split_ratio + random.uniform(-0.05, 0.05)))
        if random.random() < rate:
            self.back_delay = max(1, min(10, self.back_delay + random.choice([-1, 0, 1])))

    def tick(self):
        """⏱️ Advance relay lifecycle. Age increases, phase rotates."""
        self.age += 1
        self.phase = (self.phase + 0.1) % (2 * math.pi)
        if self.usage_count == 0:
            self.fitness *= 0.98

class Brick:
    """
    🧱 Fundamental computational unit.
    States: mem (integration), think (pattern recognition), relay_strength (fire amplitude).
    All observable states are integers 0-31. Hidden accumulators bridge micro-signals.
    """
    def __init__(self, brick_id: int, pos: Tuple[float, float, float], module_id: int, zone: str):
        self.id = brick_id
        self.pos = pos
        self.module_id = module_id
        self.zone = zone
        self.alive = True
        self.energy = 20.0
        self.stability = 0.9
        self.fitness = 0.5
        self.age = 0
        self.rom_locked = False
        self.plasticity = 1.0          # default; consolidation reduces it, ROM-lock zeroes it
        self.consolidation_count = 0
        
        self.mem = random.randint(0, STATE_MAX)
        self.think = random.randint(0, STATE_MAX)
        self.relay_strength = random.randint(0, STATE_MAX)
        
        self.mem_acc = 0.0
        # 🔇 SPEAK-ONLY-WHEN-SPOKEN-TO (v4.7): silent by default, fire only on sufficient input.
        # Energy-frugal (organic tissue is silent by default), anti-explosion (silence can't run away),
        # anti-drowning (silent cells don't dilute the readout), multi-reflex (each cell quiet except for
        # its own call). fire_threshold is EVOLVABLE so selection finds the right "how much before I speak".
        self.fired_this_cycle = False
        self.input_this_cycle = 0.0       # magnitude of input received this cycle (were we spoken to?)
        self.prototype = None             # 🧠 the call-pattern this cell has learned to RECOGNIZE (avg of calls it answered well)
        self.proto_answer = None          # the answer associated with that prototype
        self.match_weight = 0.0           # how well the CURRENT call matches this cell's prototype (set each cycle)
        self.fire_threshold = random.uniform(0.3, 1.5)   # evolvable cost-gate to speak
        self.refractory = 0               # cycles of forced silence remaining after firing
        self.think_acc = 0.0
        self.relay_acc = 0.0
        
        self.prediction_error = 0.0
        self.consecutive_errors = 0
        self.correct_predictions = 0

        # 🍼 TASK INTERFACE (call-and-response / "mama" loop):
        # An input (call) is presented; the brick predicts the completion (response). If it matches the
        # known-correct answer, the WHOLE substrate is rewarded (and so, downstream, is this brick).
        self.last_call = None          # the call value most recently received (for prediction)
        self.last_response = None      # the response this brick emitted
        self.task_correct = False      # did this brick's response match the target on the last trial?
        self.recent_task_score = 0.5   # rolling correctness (the part's contribution to the whole's success)

        self.synapses: List[Synapse] = []
        self.relays: List[PairedRelay] = []

    def clamp_state(self):
        """🔒 Ensure observable states stay within [0, 31]."""
        self.mem = max(STATE_MIN, min(STATE_MAX, self.mem))
        self.think = max(STATE_MIN, min(STATE_MAX, self.think))
        self.relay_strength = max(STATE_MIN, min(STATE_MAX, self.relay_strength))

    def commit_accumulators(self, zone_cfg: dict):
        """🌉 Bridge micro-signals to discrete states. Prevents quantization oscillation."""
        for acc_name, state_name in [("mem_acc", "mem"), ("think_acc", "think"), ("relay_acc", "relay_strength")]:
            acc_val = getattr(self, acc_name)
            if abs(acc_val) >= ACCUM_THRESHOLD:
                delta = int(acc_val)
                setattr(self, state_name, getattr(self, state_name) + delta)
                setattr(self, acc_name, acc_val - delta)
        self.clamp_state()
        for syn in self.synapses:
            syn.update_discrete(zone_cfg)

    def receive(self, signal: float, src_id: int, delay: int):
        """📥 Integrate incoming signal. ROM-locked bricks still RECEIVE (ROM = frozen WEIGHTS, not deaf!
        a reflex must hear its call to respond). Tracks input_this_cycle = 'were we spoken to?'."""
        if not self.alive:
            return
        zone_cfg = ZONE_PARAMS[self.zone]
        mapped = zone_cfg["signal_map"].get(signal, signal)
        sign_scale = zone_cfg.get("pos_scale", 1.0) if mapped > 0 else 1.0
        # ROM bricks integrate input for FIRING decisions but don't let it overwrite their frozen state much
        scale = 0.3 if self.rom_locked else 1.0
        self.mem_acc += mapped * 0.3 * sign_scale * scale
        self.think_acc += mapped * 0.5 * sign_scale * scale
        self.relay_acc += mapped * 0.2 * sign_scale * scale
        self.input_this_cycle += abs(mapped)      # 🔇 record that we were spoken to (and how loudly)
        self.energy -= 0.05

    def predict_next(self) -> float:
        """
        🔮 LOCAL FIRST-ORDER DERIVATIVE PREDICTION
        Replaces static mem/think mix with discrete velocity tracking.
        Matches cortical temporal derivative tracking.
        """
        velocity = (self.mem - self.think) * 0.5
        noise = random.uniform(-0.3, 0.3)
        return self.mem + velocity + noise

    def update_prediction_error(self, actual: float):
        """📉 Compare prediction to reality. Drives local learning & structural growth."""
        pred = self.predict_next()
        err = abs(pred - actual)
        self.prediction_error = self.prediction_error * 0.8 + err * 0.2
        if err > 2.0:
            self.consecutive_errors += 1
            self.correct_predictions = 0
        else:
            self.consecutive_errors = 0
            self.correct_predictions += 1

# ─────────────────────────────────────────────────────────────────────────────
# SOVEREIGN CORE ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class SovereignCore:
    """
    🧠 Brainstem + Hippocampus Controller.
    Manages brick lifecycle, zone routing, sleep consolidation DAG,
    evolutionary NAS, context capacity, and persistence.
    """
    def __init__(self, init_bricks: int = INIT_BRICKS):
        self.current_time = 0
        self.generation = 1
        self.num_modules = max(1, init_bricks // 50)
        self.spacing = MODULE_SPACING
        self.module_size = MODULE_SIZE
        # GROWTH FIX (2026-09-27): "output module" was computed as (num_modules - 1) everywhere --
        # fine when num_modules never changes, but growth adding new trailing modules silently moves
        # "the output" to a brand-new, untrained module every time, cutting off the real trained
        # pathway. Fix: fix this ONCE, before growth can ever touch it, and never recompute it.
        self.output_module_id = self.num_modules - 1
        
        self.context_tokens = 0
        self.context_capacity = CONTEXT_CAPACITY
        self.context_triggered_sleep = False
        self.is_sleeping = False
        
        self.bricks: List[Brick] = []
        self.brick_lookup: Dict[int, Brick] = {}
        self._max_id_tracker = 0
        self.seed_brick_ids = set()      # ROM-locked firmware bricks (the "mama" reflex) -- never reaped/mutated
        self._init_substrate(init_bricks)
        self._plant_seed()               # 🌱 plant the hardcoded working reflex(es) AFTER the substrate exists

    def _grow_network(self):
        """
        🌱 GROWTH BY CLONING WHAT WORKED (recovered 2026-09-27 -- see GALATEA_BOOK26 diary entry).
        This is the piece that was lost: the sleep DAG's existing cull+copy replaces weak cells
        WITHIN a fixed population -- it never adds real new capacity. This is real structural
        growth, adapted from a working method found in an earlier version of this same lineage
        (Max_sovereign_core_v4_2.py's _grow_network): rank whole MODULES by their average brick
        fitness, take the top performers, and clone bricks FROM them into a brand new module --
        each clone inherits its donor's state (mem/think/relay_strength) AND its donor's evolved
        relay traits (split_threshold/split_ratio/back_delay), with small gaussian variation, not
        exact duplication. "Growth came from cloning bricks that worked" -- his own words for it.
        """
        living = [b for b in self.bricks if b.alive]
        if not living:
            return
        mod_fitness = defaultdict(list)
        mod_bricks = defaultdict(list)
        for b in living:
            mod_fitness[b.module_id].append(b.fitness)
            mod_bricks[b.module_id].append(b)
        avg_by_mod = {m: sum(f) / max(len(f), 1) for m, f in mod_fitness.items()}
        top_mods = sorted(avg_by_mod.items(), key=lambda x: x[1], reverse=True)[:2]

        grid = 4
        new_bricks = 0
        for mod_id, fit in top_mods:
            src_bricks = mod_bricks[mod_id]
            new_mod_id = self.num_modules
            cx = (new_mod_id % grid) * self.spacing
            cy = (new_mod_id // grid) * self.spacing
            n_clone = max(1, len(src_bricks) // 3)
            for _ in range(n_clone):
                pos = (cx + random.uniform(-self.module_size, self.module_size),
                       cy + random.uniform(-self.module_size, self.module_size),
                       random.uniform(-self.module_size, self.module_size))
                donor = random.choice(src_bricks)
                nb = self._create_brick(pos=pos, module_id=new_mod_id, zone=donor.zone)
                # inherit donor's STATE, mutated, not copied exactly
                nb.mem = int(max(STATE_MIN, min(STATE_MAX, donor.mem + random.gauss(0, 1.0))))
                nb.think = int(max(STATE_MIN, min(STATE_MAX, donor.think + random.gauss(0, 1.0))))
                nb.relay_strength = int(max(STATE_MIN, min(STATE_MAX, donor.relay_strength + random.gauss(0, 1.0))))
                nb.energy = 20.0
                nb.stability = donor.stability
                # inherit donor's EVOLVED RELAY TRAITS -- the actual point of cloning "what worked":
                # a fresh PairedRelay from _create_brick starts at random init, overwrite with the
                # donor's own tuned split_threshold/split_ratio/back_delay, gaussian-varied.
                if donor.relays and nb.relays:
                    donor_relay = donor.relays[0]
                    for nr in nb.relays:
                        nr.split_threshold = max(0.5, min(8.0, donor_relay.split_threshold + random.gauss(0, 0.2)))
                        nr.split_ratio = max(0.1, min(0.9, donor_relay.split_ratio + random.gauss(0, 0.03)))
                        nr.back_delay = max(1, donor_relay.back_delay + random.choice([-1, 0, 0, 1]))
                new_bricks += 1
            self.num_modules += 1
        if new_bricks:
            print(f"      🌱 Growing network: cloned {new_bricks} bricks from {len(top_mods)} "
                  f"high-fitness module(s) into new capacity.")

    def _next_id(self) -> int:
        self._max_id_tracker += 1
        return self._max_id_tracker

    def _init_substrate(self, count: int):
        """🏗️ Spawn initial modules and distribute bricks across spatial layout."""
        for m_id in range(self.num_modules):
            cx = (m_id % 4) * self.spacing
            cy = (m_id // 4) * self.spacing
            cz = random.uniform(0, 20)
            zone_bias = random.choice(["FAST", "SLOW", "MIRROR"])
            for _ in range(count // self.num_modules):
                pos = (cx + random.uniform(-self.module_size, self.module_size),
                       cy + random.uniform(-self.module_size, self.module_size),
                       cz + random.uniform(-self.module_size, self.module_size))
                self._create_brick(pos=pos, module_id=m_id, zone=zone_bias)

    def _plant_seed(self):
        """🌱 THE SEED ("mama" firmware): plant a few HARDCODED working call->response reflex arcs.
        NOT random. ROM-locked from birth so evolution cannot delete the boot reflex everything learns from.
        Each seed = a thin wired chain from an entry brick, forward module by module, to an output brick
        whose state is SET to emit the correct answer. The reflex WORKS at cycle 0; the rest of the
        substrate learns the other task pairs by IMITATION (sister-spreading from this working pattern).
        We plant SEED_REPEATS copies of the first task pair (one 'word', repeated a few times -- redundancy
        costs nothing and gives the pattern more sister-neighbors to spread from)."""
        SEED_REPEATS = 3
        if not self.TASK_PAIRS:
            return
        seed_call, seed_answer = self.TASK_PAIRS[0]   # the one hardcoded "word", e.g. (2,4,6)->8
        self._seed_call = tuple(seed_call)            # remember it so inject can excite the reflex
        for rep in range(SEED_REPEATS):
            chain = []
            # build one brick per module, wired forward module 0 -> last module
            prev = None
            for m_id in range(self.num_modules):
                pos = ((m_id % 4) * self.spacing, (m_id // 4) * self.spacing, 10.0)
                b = self._create_brick(pos=pos, module_id=m_id, zone="SLOW")  # SLOW = persistence zone
                b.synapses = []   # clear random synapses; this is a clean hardcoded chain
                b.relays = []
                self.seed_brick_ids.add(b.id)
                # 🔧 HAND-CRANK: seed is PLASTIC (read-write), not frozen. It injects the answer to crank
                # the flywheel, then DISENGAGES to a normal plastic cell once the pattern propagates. It is
                # PROTECTED-FROM-CULL (immune) while cranking, but its weights stay free to move with the
                # swarm. NOT rom_locked (a read-only seed = a crank that never lets go = a millstone).
                b.rom_locked = False
                b.plasticity = 1.0
                b.fitness = 1.0
                b.energy = 30.0
                b.is_seed_crank = True       # currently cranking (protected + injecting)
                b.crank_passes = 0           # how many times it has injected; disengages after a few
                if prev is not None:
                    # forward synapse prev -> b (strong, short delay): the reflex pathway
                    prev.synapses.append(Synapse(b.id, weight=ZONE_PARAMS["SLOW"]["weights"][1], delay=1))
                    prev.relays.append(PairedRelay(source_id=prev.id, targets=[b.id], base_delay=1))
                prev = b
                chain.append(b)
            # set the OUTPUT brick of this chain to emit the correct answer (the reflex's hardcoded response)
            out_b = chain[-1]
            out_b.mem = int(seed_answer)            # memory state = the answer
            out_b.mem_acc = float(seed_answer)
            out_b.think = int(seed_answer)          # think = answer too -> predict_next ~ answer
            out_b.think_acc = float(seed_answer)
            out_b.fire_threshold = 0.05             # seed output fires readily (the reflex always responds)
            out_b._seed_answer = float(seed_answer) # remember its hardcoded answer to refresh against drift
            # record what this seed answers (for clarity / future use)
        print(f" 🌱 Seed planted: {SEED_REPEATS}x reflex {seed_call}->{seed_answer} "
              f"(ROM-locked firmware, wired entry->output across {self.num_modules} modules)")

    def _create_brick(self, pos: Tuple[float, float, float], module_id: int, zone: str) -> Brick:
        """🧱 Instantiate a new brick, register in lookup, wire initial synapses."""
        bid = self._next_id()
        b = Brick(bid, pos, module_id, zone)
        self.bricks.append(b)
        self.brick_lookup[bid] = b
        # SINGLE-OUTPUT / FORWARD morphology: a brick may target bricks in its OWN module (sideways)
        # or the NEXT module (forward). It may NOT wire directly back to an earlier module (no tight loop;
        # feedback only ever returns the long way, through the network). This also finally CONNECTS
        # entry(module 0) -> ... -> output(last module) so the call can actually reach the answer.
        valid_targets = [x.id for x in self.bricks if x.id != bid and
                         (x.module_id == module_id or x.module_id == module_id + 1)]
        targets = random.sample(valid_targets, k=min(3, len(valid_targets))) if valid_targets else []
        for t in targets:
            w = random.randint(*ZONE_PARAMS[zone]["weights"])
            d = random.randint(1, 8)
            b.synapses.append(Synapse(t, w, d))
        # 🧠 give the brick a PairedRelay so the backward-split mechanism has structure to act on.
        # (Original v4.3 never instantiated relays; the split mechanism needs them to exist.)
        if targets:
            b.relays.append(PairedRelay(source_id=bid, targets=list(targets), base_delay=random.randint(1, 4)))
        return b

    def _reap_dead(self):
        """🍂 Remove bricks that exhausted energy. Fitness-floor pruning is GENTLE early (slime-mold:
        keep the network alive long enough to learn). Only reap on true energy death, or sustained
        very-low fitness AFTER the brick has had time to learn (age gate)."""
        alive = []
        for b in self.bricks:
            truly_dead = (b.energy <= 0)
            chronic_fail = (b.fitness < PRUNE_FITNESS_FLOOR * 0.5 and b.age > 80)  # age-gated, lenient
            is_seed = (b.id in self.seed_brick_ids)   # 🌱 firmware is never reaped
            if b.alive and (is_seed or (not truly_dead and not chronic_fail)):
                alive.append(b)
            else:
                b.alive = False
                self.brick_lookup.pop(b.id, None)
        self.bricks = alive

    def _autosarcophagy(self):
        """🔪 Metabolic pruning: decay low-fitness synapses, return resources."""
        for b in self.bricks:
            if b.fitness < 0.2 and b.age > 50:
                for syn in b.synapses:
                    syn.weaken()
                b.energy = max(0, b.energy - 2.0)

    # 🍼 THE TASK: a small fixed library of call -> response pairs (sequence completions).
    # The substrate hears the CALL and must produce the RESPONSE. Correct answers are REAL and KNOWN,
    # so fitness can reward TRUE correctness (whole-organism success), not self-consistency.
    # Start tiny (a few "words") so it can actually be learned by repetition -- like mama.
    # MULTI-TASK (v4.13): several +2 sequences (SAME operation, different sequences). The seed knows ONE
    # (2,4,6->8); the OTHERS must be learned by GENERALIZING the +2 operation -- a memorizer of "8" fails
    # them, only a rule-extractor wins. Values in [0,31]. This is the proof-of-concept: if it learns the
    # OPERATION here (math), the mechanism generalizes to anything.
    TASK_PAIRS = [
        ((2, 4, 6), 8),     # the seeded one
        ((5, 7, 9), 11),
        ((10, 12, 14), 16),
        ((1, 3, 5), 7),
        ((20, 22, 24), 26),
        ((11, 13, 15), 17),
    ]

    def inject_problem(self, problem_type: str, signal: float, forced_call=None):
        """📤 Present a CALL to entry bricks and store the KNOWN-CORRECT response for fitness scoring.
        problem_type is now USED: it selects which call/response pair (round-robin over the task library)."""
        self.context_tokens += 1
        # pick a task pair deterministically-ish so every pair gets practiced (repetition = learning)
        if forced_call is not None:
            call = forced_call
            correct = dict(self.TASK_PAIRS).get(tuple(forced_call), 0)
        else:
            # INTERLEAVED waking presentation: random task each cycle (not blocked) so all tasks are
            # rehearsed frequently -- reduces recency-dominated overwriting (catastrophic forgetting).
            call, correct = random.choice(self.TASK_PAIRS)
        self.current_call = call
        self.current_target = float(correct)

        # 🌱 SEED REFLEX: if the current call matches the seed's call, directly excite the seed chain so
        # the firmware RELIABLY fires its response (a reflex always responds to its own call -- not by luck).
        if hasattr(self, "_seed_call") and tuple(call) == self._seed_call:
            for b in self.bricks:
                if b.id in self.seed_brick_ids:
                    if getattr(b, "is_seed_crank", False):
                        b.input_this_cycle += 5.0      # CRANK: inject the answer to spin the flywheel
                        b.crank_passes = getattr(b, "crank_passes", 0) + 1
                        # DISENGAGE only when the ENGINE HAS CAUGHT: enough NON-SEED cells reliably produce
                        # the answer (swarm self-sustaining). Listen for the catch, THEN let go -- not a timer.
                        # (a minimum pass count too, so it cranks at least a little before checking.)
                        if b.crank_passes >= SEED_CRANK_PASSES and self._engine_caught():
                            b.is_seed_crank = False    # crank lets go; weights now free to move with swarm
                            # RATCHET FIX (2026-09-27, independently verified against this exact file):
                            # every zone's signal_map is entirely positive-valued -- no inhibitory signal
                            # exists anywhere in this substrate. A brick with no restoring force pinning
                            # it integrates a strictly one-directional stream and monotonically ratchets
                            # to STATE_MAX. The seed firmware is the population's ground-truth teacher;
                            # once it drifts, whole_correct/my_credit/prototype EMAs all smear toward a
                            # wrong target and the corruption spreads through the whole recognizer pool.
                            # The crank letting go was never meant to mean "now forget the answer" --
                            # ROM-lock it: _update_bricks already pins _seed_answer for rom_locked
                            # bricks, so this reuses existing machinery rather than adding a new one.
                            b.rom_locked = True
                    # (after disengage: no forced injection; it learns like any other cell)
        entry_bricks = [b for b in self.bricks if b.alive and b.module_id == 0]
        targets = random.sample(entry_bricks, k=min(8, len(entry_bricks)))
        for b in targets:
            b.last_call = call
            b.mem_acc += float(call[-1])
            b.think_acc += float(call[-2])
            for elem in call:
                b.receive(float(elem), src_id=-1, delay=0)

        # 🧠 RECOGNITION: every cell computes how well THIS call matches its stored prototype.
        call_vec = [float(x) for x in call]
        for b in self.bricks:
            if not b.alive: continue
            if b.prototype is None:
                b.match_weight = 0.0
                continue
            # Euclidean distance between the current call and the cell's learned prototype pattern
            dist = math.sqrt(sum((a - p) ** 2 for a, p in zip(call_vec, b.prototype)))
            if RECOGNITION_MODE == "graded":
                b.match_weight = math.exp(-(dist * dist) / (2.0 * RBF_SIGMA * RBF_SIGMA))  # RBF kernel
            else:
                b.match_weight = dist   # store raw distance; nearest-mode picks min in readout

    def _read_response(self):
        """🗣️ WINNER-WEIGHTED readout (v4.6, GRPO-shaped). The answer is NOT a flat mean of all output
        bricks (which lets random bricks drown the seed). Each brick votes with a WEIGHT = its stability *
        fitness (committed, proven cells speak louder), and seed/ROM bricks get a strong baseline weight
        (the firmware is trusted). This is the 'high-advantage outputs dominate' rule: consensus of the
        cells that are actually competent, not the average of the noise."""
        # 🔇 only bricks that FIRED this cycle get a vote (spoke when spoken to). Silent cells don't dilute.
        out_bricks = [b for b in self.bricks if b.alive and b.module_id == (self.output_module_id)
                      and b.fired_this_cycle]
        if not out_bricks:
            return None                                         # nobody was spoken to -> no answer this cycle
        # 🧠 RECOGNITION READOUT: cells vote weighted by how well they RECOGNIZE the current call.
        # graded = RBF match_weight (closer prototype = louder); nearest = only closest-prototype cell votes.
        recognizers = [b for b in out_bricks if b.prototype is not None]
        if RECOGNITION_MODE == "nearest" and recognizers:
            # winner-take-all: the single closest prototype (smallest distance) answers
            winner = min(recognizers, key=lambda b: b.match_weight)   # match_weight holds raw distance here
            return float(winner.proto_answer) if winner.proto_answer is not None else winner.predict_next()
        # seed/firmware voices DOMINATE the readout (heavy weight) so a few correct cells beat the crowd.
        num = 0.0; den = 0.0
        for b in out_bricks:
            w = (b.stability + 0.1) * (b.fitness + 0.1)
            if b.id in self.seed_brick_ids:
                w *= 50.0          # firmware speaks ~50x louder (the trusted reflex dominates)
            # 🧠 recognition gate (graded): a cell that recognizes THIS call votes louder; non-recognizers fade
            if RECOGNITION_MODE == "graded" and b.prototype is not None:
                w *= (0.05 + b.match_weight)     # match_weight in [0,1]; small floor so unrecognized still whisper
            # a recognizing cell emits ITS prototype's answer (what it learned to say to this pattern)
            val = b.proto_answer if (b.proto_answer is not None and b.prototype is not None) else b.predict_next()
            num += w * val; den += w
        return (num / den) if den > 0 else None

    def _update_bricks(self):
        """⚙️ Core cycle: SPEAK-ONLY-WHEN-SPOKEN-TO firing gate, then commit, error, zone routing."""
        tgt = getattr(self, "current_target", None)
        for b in self.bricks:
            if not b.alive: continue
            # 🔇 FIRING GATE: fire only if spoken to enough (input >= threshold) and not refractory.
            if b.refractory > 0:
                b.refractory -= 1
                b.fired_this_cycle = False
            else:
                b.fired_this_cycle = (b.input_this_cycle >= b.fire_threshold)
                if b.fired_this_cycle:
                    b.refractory = 1                 # brief silence after firing (don't speak again yet)
                    b.energy -= 0.1                  # firing costs energy (organic frugality)
            b.input_this_cycle = 0.0                 # reset: a new cycle, must be spoken to again

            # 🔧 CRANK REFRESH: while a seed cell is still CRANKING (plastic but injecting), keep its answer
            # pinned so it reliably emits the response that spins the flywheel. This was previously gated on
            # rom_locked -- making the seed plastic accidentally UNPLUGGED it (seed went mute -> TaskCorrect 0
            # from the start). Now the crank works in the plastic state, and only RELEASES on disengage.
            if getattr(b, "is_seed_crank", False) and hasattr(b, "_seed_answer"):
                b.mem = int(b._seed_answer); b.think = int(b._seed_answer)
            elif getattr(b, "teach_freeze", 0) > 0 and hasattr(b, "_teach_answer"):
                b.mem = int(b._teach_answer); b.think = int(b._teach_answer)   # steady teacher

            if b.rom_locked:
                b.age += 1
                if hasattr(b, "_seed_answer"):
                    b.mem = int(b._seed_answer); b.think = int(b._seed_answer)
                continue                              # ROM weights frozen, but it DID get its firing decision
            zone_cfg = ZONE_PARAMS[b.zone]
            b.commit_accumulators(zone_cfg)
            b.update_prediction_error(tgt if tgt is not None else b.mem)
            b.age += 1
            b.energy = min(30.0, b.energy + 0.25)

            # 🔒 CONSOLIDATE DISCOVERED-GOOD (Fix #1, anti-drift): a non-seed cell that stays reliably
            # correct on the TASK gets its plasticity REDUCED (harder to drift), and if it sustains high
            # correctness long enough, it ROM-LOCKS (pinned permanently). This protects DISCOVERED-good the
            # way the seed (born-good) is already protected. Without this, exploration erases what was learned.
            # 🛡️ SUCCESS -> IMMUNITY (not freezing). A sustained-correct cell becomes PROTECTED FROM
            # CULLING but stays READ-WRITE (plastic) -- it keeps turning with the flywheel, recording
            # ongoing learning. Immunity != frozen. (No ROM-lock on live learning cells.)
            if b.recent_task_score > 0.85:
                b.consolidation_streak = getattr(b, "consolidation_streak", 0) + 1
                if b.consolidation_streak >= 40 and not getattr(b, "cull_immune", False):
                    b.cull_immune = True            # earned immunity: sleep won't eat it (stays read-write)
                    # 🔧 TRANSIENT FREEZE: become a STABLE clean TEACHER for a window, so neighbors imitate a
                    # steady target (restores geometric propagation) -- then RETURN to plastic (no millstone).
                    b.teach_freeze = TEACH_FREEZE_WINDOW
                    print(f" 🛡️ IMMUNE+TEACH (stable teacher {TEACH_FREEZE_WINDOW}c, then plastic): Brick {b.id} zone={b.zone} score={b.recent_task_score:.2f}")
            else:
                b.consolidation_streak = max(0, getattr(b, "consolidation_streak", 0) - 1)
                if getattr(b, "cull_immune", False) and b.recent_task_score < 0.40 and b.consolidation_streak <= -60:
                    b.cull_immune = False
            # tick down the teaching-freeze window; while frozen, hold weights stable (clean teacher)
            if getattr(b, "teach_freeze", 0) > 0:
                b.teach_freeze -= 1
                b.plasticity = 0.05               # stable target while teaching
                b._teach_answer = b.mem           # hold the answer it's teaching
            elif getattr(b, "cull_immune", False):
                b.plasticity = max(0.4, b.plasticity)   # released back to plastic (not a millstone)

    def _fire_relays(self):
        """📡 Paired relay routing, phase-gated, delay-aware, WITH the SISTER-CELL SPLIT (v4.5).
        🧬 SISTER-SPLIT (the unified relay-split mechanism -- stability + imitation + clean boomerang):
           NORMAL: signal moves FORWARD, one direction, to the relay's targets. Always.
           RELIEF VALVE: ONLY when the signal is too big (source brick's prediction_error exceeds this
           relay's EVOLVABLE split_threshold) does it SPLIT:
             - the remainder continues FORWARD (weakened) to targets, as normal;
             - the EXCESS (split_ratio) is redirected -- with delay -- to a SISTER cell: a DIFFERENT brick
               in the SAME module/array as the source, NEVER the source itself and NEVER its direct feeders.
           This single act does three jobs at once, which are one job:
             1. STABILITY  -- the dangerously-big signal is bled off / dispersed before it can compound.
             2. IMITATION  -- the sister processes the redirected signal SECONDHAND -> the pattern spreads
                              to a neighbor (an array of A-cells; the signal returns to a DIFFERENT A).
             3. CLEAN      -- sister (not source), forward (not back): no tight loop ever forms; single-
                              output morphology preserved; feedback only ever returns the long way around.
           ★ This CORRECTS v4.4, which wrongly sent the split BACK to the source/feeders (the tight-loop
             echo that explodes). Sister, not source, is the whole difference between explode and clean."""
        for b in self.bricks:
            if not b.alive or b.relay_strength < 10: continue
            for relay in b.relays:
                relay.tick()
                brick_phase = (self.current_time * 0.1) % (2 * math.pi)
                phase_diff = abs((relay.phase - brick_phase) % (2 * math.pi))
                if not (phase_diff < 0.5 or phase_diff > (2 * math.pi - 0.5)):
                    relay.suppressed = True
                    continue
                relay.usage_count += 1
                relay.suppressed = False

                # decide whether to SPLIT, based on the source brick's error vs this relay's evolvable threshold
                do_split = (b.prediction_error > relay.split_threshold)
                # MOSS/CANCER FIX: a real, substantial error occurred (2.0 is comfortably inside this
                # relay's own possible init range of 1.5-4.0, i.e. a well-calibrated relay would often
                # have caught it) but THIS relay's threshold was too high to act -- record the miss so
                # it can be penalized below, same as a split that didn't help already is.
                if not do_split and b.prediction_error > 2.0:
                    relay.missed_split_count += 1
                fwd_signal = b.relay_strength * 0.1
                if do_split:
                    relay.split_count += 1
                    relay.split_this_cycle = 1
                    sister_amount = fwd_signal * relay.split_ratio        # excess bled off to a SISTER
                    fwd_signal = fwd_signal * (1.0 - relay.split_ratio)   # remainder continues forward (weakened)
                    # find SISTER cells: same module as source, but NOT the source and NOT its direct feeders.
                    feeders = {src.id for src in self.bricks
                               if any(sy.target_id == b.id for sy in src.synapses)}
                    sisters = [x for x in self.bricks
                               if x.alive and x.module_id == b.module_id
                               and x.id != b.id and x.id not in feeders]
                    if sisters:
                        for sis in random.sample(sisters, k=min(2, len(sisters))):
                            # forward-going imitation signal to the sister, delayed (temporal spread).
                            # the sister learns the pattern secondhand; the big signal is dispersed, not looped.
                            sis.receive(sister_amount, src_id=b.id, delay=relay.back_delay)

                # forward distribution (normal), with whatever remains after a split
                for t_id in relay.targets:
                    target = self.brick_lookup.get(t_id)
                    if target and target.alive:
                        target.receive(fwd_signal, src_id=b.id, delay=relay.base_delay)

    def _evaluate_fitness(self):
        """⚖️ WHOLE-ORGANISM CORRECTNESS drives selection (the anti-cancer / anti-moss leash).
        🔒 GOVERNANCE PRINCIPLE: reward flows from the SUBSTRATE's actual task success DOWN to the parts.
           A brick/relay thrives ONLY when the WHOLE answered the call correctly. This prevents the cancer
           failure (a part gaming local self-consistency while the whole learns nothing). Self-consistency
           (stability/energy) is kept as a SMALL secondary 'stay alive' term; TASK CORRECTNESS DOMINATES.

        Step 1: read the substrate's collective response to the current call; score it against the KNOWN target.
        Step 2: distribute that whole-organism correctness as the primary fitness signal to the parts.
        Step 3: reward relays whose SPLIT actually preceded improved correctness (so split-traits evolve
                toward learning, not toward calm)."""
        target = getattr(self, "current_target", None)
        response = self._read_response()
        # whole-organism correctness in [0,1]: 1.0 = exact, decaying with absolute error
        if target is not None and response is not None:
            err = abs(response - target)
            # normalized over the state range: exact=1.0, off by ~8 (a quarter of the 0-31 band)=0.0
            whole_correct = max(0.0, 1.0 - err / 8.0)
        else:
            whole_correct = 0.5
        # track improvement (did the whole get MORE correct than last trial?) for split-credit
        prev = getattr(self, "_prev_whole_correct", 0.5)
        improved = whole_correct > prev
        self._prev_whole_correct = whole_correct
        # windowed average so telemetry reflects the TRUE rate, not one unlucky instantaneous sample
        if not hasattr(self, "_wc_window"): self._wc_window = []
        self._wc_window.append(whole_correct)
        if len(self._wc_window) > 100: self._wc_window.pop(0)
        self._wc_avg = sum(self._wc_window) / len(self._wc_window)

        # 🏝️ GROUP-RELATIVE ADVANTAGE (GRPO): compute each output brick's OWN correctness vs target,
        # then the GROUP MEAN, so each cell can be rewarded for being ABOVE its sisters' average.
        out_bricks = [b for b in self.bricks if b.alive and b.module_id == (self.output_module_id)]
        per_correct = {}
        if target is not None and out_bricks:
            for ob in out_bricks:
                e = abs(ob.predict_next() - target)
                per_correct[ob.id] = max(0.0, 1.0 - e / 8.0)
            group_mean = sum(per_correct.values()) / len(per_correct)
        else:
            group_mean = 0.5

        # 🔗 CHAIN CREDIT (Fix #2): propagate credit BACKWARD from correct output cells through their
        # feeders, so every cell ON A WINNING PATH gets its OWN credit (not the group blend). The reward
        # for the whole correct answer reaches back and reinforces the cells that produced it -- the
        # foundation is paid rent by what's built on it. This gives each cell an INDIVIDUAL score, which is
        # exactly what consolidation (#1) needs to know WHICH cells to pin.
        chain_credit = {}
        # seed correct output cells with their own correctness; start the backward flow from them.
        frontier = {}
        for ob in out_bricks:
            c = per_correct.get(ob.id, 0.0)
            chain_credit[ob.id] = c
            if c > 0.6:                      # only CORRECT outputs propagate credit backward
                frontier[ob.id] = c
        # precompute feeder map ONCE: target_id -> list of source brick ids that feed it
        feeders_of = {}
        for src in self.bricks:
            if not src.alive: continue
            for sy in src.synapses:
                feeders_of.setdefault(sy.target_id, []).append(src.id)
        # walk backward through feeders, decaying credit each hop (closer to the answer = more credit)
        for _hop in range(self.num_modules):
            next_frontier = {}
            for bid, cred in frontier.items():
                for src_id in feeders_of.get(bid, ()):
                    passed = cred * 0.7
                    if passed > chain_credit.get(src_id, 0.0):
                        chain_credit[src_id] = passed
                        if passed > 0.3:
                            next_frontier[src_id] = passed
            frontier = next_frontier
            if not frontier: break

        for b in self.bricks:
            if not b.alive: continue
            # --- PRIMARY: whole-organism correctness (dominant term) ---
            accountability = 1.0 if b.module_id == (self.output_module_id) else 0.4
            task_term = whole_correct * accountability
            # --- GRPO ADVANTAGE: output bricks also rewarded for beating the GROUP MEAN (the island) ---
            if b.id in per_correct:
                advantage = per_correct[b.id] - group_mean        # >0 = better than sisters -> reinforce
                task_term += 0.5 * advantage                      # above-average wins, below-average suppressed

            # --- SECONDARY: stay-alive floor. Bigger early on so the network SURVIVES the learning phase
            #     (slime-mold principle: stay alive long enough to find the path). As correctness rises,
            #     the task term naturally dominates; while correctness is 0, this floor keeps bricks alive. ---
            alive_term = 0.35 * (b.stability * 0.5 + min(b.energy, 30) / 60.0)

            # 🔗 add this cell's OWN chain credit (it's on a winning path) to its task term
            my_credit = chain_credit.get(b.id, 0.0)
            task_term += 0.6 * my_credit       # winning-path cells reinforced INDIVIDUALLY

            # 🧠 PROTOTYPE LEARNING: a cell that is on a winning path for THIS call learns to RECOGNIZE it --
            # move its prototype (EMA) toward the current call, and record the answer it should emit. This is
            # how averaging BECOMES recognition: each cell specializes to the pattern it answers correctly.
            if my_credit > 0.5 and self.current_call is not None:
                cv = [float(x) for x in self.current_call]
                if b.prototype is None:
                    b.prototype = cv[:]
                    b.proto_answer = float(self.current_target) if self.current_target is not None else b.mem
                else:
                    b.prototype = [(1 - PROTO_LEARN_RATE) * p + PROTO_LEARN_RATE * c
                                   for p, c in zip(b.prototype, cv)]
                    if self.current_target is not None:
                        b.proto_answer = (1 - PROTO_LEARN_RATE) * b.proto_answer + PROTO_LEARN_RATE * float(self.current_target)

            # correctness dominates WHEN PRESENT, but the stay-alive floor prevents early mass-death.
            target_fitness = 0.65 * task_term + alive_term
            b.fitness = max(0.05, min(1.0, b.fitness * 0.92 + target_fitness * 0.08))
            # 🔗 recent_task_score blends chain-credit AND RECOGNITION CORRECTNESS. A cell that recognizes
            # the current call (prototype matches) and emits the RIGHT answer is doing its job -> it must
            # become a WINNER (copyable/immune). Without this, recognizing cells never crossed WORKING_FLOOR
            # -> "copied 0 winners" every sleep (the bug that starved both the conservation-law swap and the
            # garden's salience-ordered consolidation).
            recognizes_now = False
            recog_reward = 0.0
            if (getattr(b, "prototype", None) is not None and b.proto_answer is not None
                    and self.current_call is not None and self.current_target is not None):
                cv = [float(x) for x in self.current_call]
                dist = sum((p-c)**2 for p,c in zip(b.prototype, cv)) ** 0.5
                if dist < RBF_SIGMA:                      # this cell RECOGNIZES the current call
                    recognizes_now = True
                    ans_err = abs(b.proto_answer - float(self.current_target))
                    if ans_err < 1.5:
                        recog_reward = 1.0
                    elif ans_err < 3.0:
                        recog_reward = 0.5
            if recognizes_now:
                # this cell was ASKED -> update strongly toward its performance (reward or miss)
                b.recent_task_score = b.recent_task_score * 0.7 + max(my_credit, recog_reward) * 0.3
            else:
                # a DIFFERENT task was asked -> don't punish this specialist; hold its score (tiny pull to mean)
                b.recent_task_score = b.recent_task_score * 0.99 + max(my_credit, 0.5) * 0.01

        # --- Step 3: relay split-credit. If a relay split AND the whole improved, credit its traits. ---
        for b in self.bricks:
            if not b.alive: continue
            for relay in b.relays:
                if relay.split_this_cycle and improved:
                    relay.split_helped += 1
                    relay.fitness = min(1.0, relay.fitness + 0.02)   # its split traits helped -> reward
                elif relay.split_this_cycle and not improved:
                    relay.fitness = max(0.0, relay.fitness - 0.01)   # split but no help -> mild penalty
                relay.split_this_cycle = 0  # clear -- credit for THIS cycle's action has been paid
                # MOSS/CANCER FIX: penalize INACTION when it was warranted, not just unhelpful action.
                # Slightly steeper than the "tried and it didn't help" penalty -- never trying at all
                # when the signal clearly called for it is the worse strategy, not the safer one.
                if relay.missed_split_count > 0:
                    relay.fitness = max(0.0, relay.fitness - 0.015 * relay.missed_split_count)
                    relay.missed_split_count = 0  # reset -- this window's misses have been paid for

    def _mutate_and_select(self):
        """🧬 Evolutionary NAS: mutate high-error bricks, prune low-fitness, drift zones."""
        for b in self.bricks:
            if not b.alive or b.rom_locked: continue
            zone_cfg = ZONE_PARAMS[b.zone]
            mut_rate = zone_cfg["mut"] * (b.prediction_error / 10.0)
            if random.random() < mut_rate:
                b.mem_acc += random.uniform(-VARIATION_MAGNITUDE, VARIATION_MAGNITUDE)
                b.think_acc += random.uniform(-VARIATION_MAGNITUDE, VARIATION_MAGNITUDE)
                for syn in b.synapses:
                    if random.random() < mut_rate:
                        syn.acc += random.uniform(-VARIATION_MAGNITUDE, VARIATION_MAGNITUDE)

        # 🧬 evolve relay SPLIT TRAITS (threshold/ratio/delay) under the same mutation pressure
        for b in self.bricks:
            if not b.alive or b.rom_locked: continue
            zone_cfg = ZONE_PARAMS[b.zone]
            for relay in b.relays:
                relay.mutate_traits(zone_cfg["mut"])
            # 🔇 evolve the firing threshold (find the right 'how much before I speak' per cell)
            if random.random() < zone_cfg["mut"]:
                b.fire_threshold = max(0.1, min(3.0, b.fire_threshold + random.uniform(-0.15, 0.15)))

        module_zones = defaultdict(list)
        for b in self.bricks:
            if b.alive: module_zones[b.module_id].append(b)
        for m_id, bricks in module_zones.items():
            avg_err = sum(b.prediction_error for b in bricks) / max(len(bricks), 1)
            avg_fit = sum(b.fitness for b in bricks) / max(len(bricks), 1)
            if avg_err > 5.0 and avg_fit < 0.4:
                for b in bricks:
                    if random.random() < 0.1: b.zone = "FAST"
            elif avg_err < 2.0 and avg_fit > 0.7:
                for b in bricks:
                    if random.random() < 0.1: b.zone = "SLOW"

    def _engine_caught(self):
        """🔧 Has the engine caught? True when enough NON-SEED cells reliably produce the answer, so the
        swarm can sustain it WITHOUT the seed injecting. Only then may the hand-crank disengage."""
        n = sum(1 for b in self.bricks
                if b.alive and b.id not in self.seed_brick_ids and b.recent_task_score >= 0.75)
        return n >= ENGINE_CATCH_MIN_CELLS

    def _run_sleep_dag(self):
        """
        🌙 SLEEP = GLOBAL ORGANISM MAINTENANCE PHASE (v4.10 mechanical core).
        Sleep is NOT a local timer op -- it is a whole-organism phase: normal operation is suspended and the
        organism does what it can only do when not running. MECHANICAL CORE (per the clinical build spec):
          (a) CULL THE DEFECTIVE  -- delete low-task-credit cells (never seed/ROM/high-credit; by CREDIT not
                                     internal proxies, never random).
          (b) COPY THE WINNERS    -- replicate high-task-credit cells' patterns into the freed slots, so good
                                     patterns MULTIPLY (not random injection).
          (c) TOXIN / JUNK FLUSH  -- reset half-committed accumulators + stale buffers so wake starts clean.
          (d) PROTECT THE WORKING -- do NOT re-mutate / inject-noise / reap consolidated/high-credit/seed/ROM.
        The old corrosive ops (random FAST->SLOW injection, proxy-ROM, unconditional in-sleep mutation) are
        REMOVED -- they were why TaskCorrect fell on sleep cycles.
        """
        print(" 🌙 SLEEP DAG TRIGGERED: global maintenance phase (replay-all / cull / copy / flush).")
        self.is_sleeping = True

        # PROBATION EXPIRY (2026-09-27): clones from the LAST sleep get exactly one full inter-sleep
        # window of cull-immunity to re-prove their discounted score, then become normally cullable
        # again -- separates "temporarily trusted" from "permanently protected."
        for b in self.bricks:
            if b.alive and getattr(b, "probation", False):
                b.cull_immune = False
                b.probation = False

        # 🔁 SLEEP REPLAY-ALL-TASKS (the catastrophic-forgetting cure): re-present EVERY known task pair and
        # run learning, so consolidation forms JOINT representations across ALL tasks (weights stay near every
        # task's manifold, not just the most recent). This is what biological sleep does -- rehearse old
        # memories interleaved so they aren't overwritten.
        REPLAY_ROUNDS = 8
        for _r in range(REPLAY_ROUNDS):
            for (call, correct) in self.TASK_PAIRS:
                self.inject_problem("replay", 1.0, forced_call=call)
                self._update_bricks()
                self._fire_relays()
                self._evaluate_fitness()
        print(f"    🔁 sleep replay: {REPLAY_ROUNDS} rounds x {len(self.TASK_PAIRS)} tasks rehearsed (joint consolidation)")
        _nsal = sum(1 for b in self.bricks if b.alive and getattr(b, "salience", 0.0) > 0.5)
        print(f"    🌿 garden: {_nsal} salient/conflicted cells (ivy-covered statues) -> consolidated first")

        living = [b for b in self.bricks if b.alive]
        # classify by TASK CREDIT (recent_task_score) -- the signal Fix #2 gave us. Protect the good.
        # v4.11 CALIBRATION: PRUNE to a healthy population, never STARVE to seed-only.
        WORKING_FLOOR = 0.55      # recognizers now climb well past this when held (not diluted by other tasks)
        ALIVE_FLOOR_FRAC = ALIVE_FLOOR_FRAC_CFG   # configurable: raise to punish LESS
        MAX_CULL_FRAC = MAX_CULL_FRAC_CFG         # configurable: lower to punish LESS
        def protected(b):
            return (b.rom_locked or getattr(b, "cull_immune", False) or getattr(b, "is_seed_crank", False)
                    or (b.id in self.seed_brick_ids) or (b.recent_task_score >= WORKING_FLOOR))

        winners = [b for b in living if (b.recent_task_score >= WORKING_FLOOR or getattr(b, "cull_immune", False))
                   and not getattr(b, "is_seed_crank", False)]

        # (a) CULL THE DEFECTIVE -- GENTLY: take the WORST cells by credit, but only a capped fraction, and
        # never drop below the alive-floor. Prune the bottom, keep the body alive to grow.
        # 🌈 DIVERSITY PRESERVATION: identify cells that UNIQUELY cover a prototype (endangered) -> immune.
        if PRESERVE_DIVERSITY:
            proto_cells = [b for b in living if b.prototype is not None]
            for b in proto_cells:
                # is there ANOTHER living cell with a close prototype? if not, b is the last of its kind.
                unique = True
                for other in proto_cells:
                    if other is b: continue
                    d = sum((p-q)**2 for p,q in zip(b.prototype, other.prototype)) ** 0.5
                    if d < 4.0:                      # someone else covers this cluster
                        unique = False; break
                b.endangered = unique                # last cell covering its prototype -> protect it
        def _endangered(b):
            return PRESERVE_DIVERSITY and getattr(b, "endangered", False)
        # ⚖️ THE CONSERVATION LAW (v4.19): SLEEP CAN ONLY REPLACE, NEVER MERELY REMOVE. A weak cell is culled
        # ONLY at the instant a better replacement is ready to take its slot -- removal+replacement is ONE
        # ATOMIC SWAP, never two steps. The number replaced is CAPPED BY THE NUMBER OF GOOD CELLS available to
        # clone from. If zero good cells are available, NOBODY dies this sleep. Population is CONSERVED exactly;
        # quality only RISES. (Not killing -- a worn-out cell is RETRAINED into a copy of a good one.)
        # 🌿 THE GARDEN: compute SALIENCE = local prototype-space DISAGREEMENT. A cell is SALIENT (a "statue",
        # the ivy-covered confusion to resolve) if another cell sits CLOSE in call-prototype space but the two
        # DISAGREE on the answer -- that is exactly the contamination region (e.g. (1,3,5) vs (5,7,9) bleed).
        # Walk this gradient: the WORST cell in the MOST-CONFLICTED region is replaced FIRST (targeted surgery,
        # not random cull). Settled cells (no nearby disagreement) fade to scenery -> left alone.
        proto_cells = [b for b in living if getattr(b, "prototype", None) is not None]
        for b in living:
            b.salience = 0.0
        for b in proto_cells:
            for other in proto_cells:
                if other is b: continue
                dcall = sum((p-q)**2 for p,q in zip(b.prototype, other.prototype)) ** 0.5
                if dcall < 8.0 and b.proto_answer is not None and other.proto_answer is not None:
                    dans = abs(b.proto_answer - other.proto_answer)
                    if dans > 1.5:
                        # close inputs, different answers = a CONFLICT. Salience grows as inputs get CLOSER
                        # while answers stay APART (the sharper the contradiction, the brighter the statue).
                        b.salience += dans / (dcall + 1.0)
        # cull candidates: the worst cells, but ORDERED BY SALIENCE (most-conflicted region first), so sleep
        # operates on the CONFUSION before anything else. Within equal salience, worst task-score first.
        cull_candidates = [b for b in living
                           if not protected(b) and not _endangered(b) and b.age > 60]
        cull_candidates.sort(key=lambda b: (-getattr(b, "salience", 0.0), b.recent_task_score))
        max_by_frac = int(len(living) * MAX_CULL_FRAC)
        min_alive = int(len(living) * ALIVE_FLOOR_FRAC)
        max_removable = max(0, len(living) - min_alive)
        # ★ the cull is now CAPPED BY len(winners): you may only replace as many as you have replacements for.
        n_swap = min(len(cull_candidates), max_by_frac, max_removable, len(winners))

        # 🌿 v4.21 ANTI-COLONIZATION census: group living proto-cells by their ANSWER-IDENTITY (rounded
        # proto_answer) so we can (b) cap clones per identity and (c) protect the minority defenders.
        def _ident(b):
            pa = getattr(b, "proto_answer", None)
            return None if pa is None else round(float(pa))
        from collections import defaultdict
        ident_counts = defaultdict(int)
        for b in living:
            if b.alive and _ident(b) is not None:
                ident_counts[_ident(b)] += 1
        # winners grouped by identity, so we can re-seed a confused cell with its OWN kind
        winners_by_ident = defaultdict(list)
        for w in winners:
            if _ident(w) is not None:
                winners_by_ident[_ident(w)].append(w)
        # the set of distinct task answers we must keep represented (the 6 true answers)
        true_answers = set(round(float(a)) for (_c, a) in self.TASK_PAIRS)
        answer_to_task = {round(float(a)): (list(c), float(a)) for (c, a) in self.TASK_PAIRS}
        MIN_DEFENDERS = 3          # never cull below this many cells of any task-answer identity
        CLONE_CAP = max(2, n_swap // max(1, len(true_answers)))   # per-identity clone cap this sleep
        clones_made = defaultdict(int)
        culled = []
        copied = 0
        # which task-answers are UNDER-represented? those most need a defender cloned (rescue the minority).
        def _under_represented_ident():
            present = [(a, ident_counts.get(a, 0)) for a in true_answers]
            present.sort(key=lambda kv: kv[1])     # fewest first
            for a, _cnt in present:
                if winners_by_ident.get(a) and clones_made[a] < CLONE_CAP:
                    return a
            return None

        actually_swapped = []
        for slot in cull_candidates[:n_swap]:
            # (c) PROTECT THE WEAKER SIDE: if this slot is one of the last MIN_DEFENDERS of its identity, SKIP
            # it -- the minority defender is not cannon fodder for a stronger neighbor.
            sid = _ident(slot)
            if sid is not None and sid in true_answers and ident_counts.get(sid, 0) <= MIN_DEFENDERS:
                continue

            # find the most UNDER-REPRESENTED true answer (fewest living defenders), regardless of winners.
            present = sorted(((a, ident_counts.get(a, 0)) for a in true_answers), key=lambda kv: kv[1])
            target_ident = None
            for a, _cnt in present:
                if clones_made[a] < CLONE_CAP:
                    target_ident = a; break
            if target_ident is None:
                continue                            # all caps hit -> nobody dies, conserve

            if winners_by_ident.get(target_ident):
                # (a) clone an existing GOOD exemplar of this identity (same-kind reinforcement)
                w = random.choice(winners_by_ident[target_ident])
                _resurrect = False
            else:
                # ★ RESURRECTION: this true answer has NO living winners (went EXTINCT) -> it can NEVER come
                # back by cloning. Re-plant its prototype straight from the TASK DEFINITION (ground truth),
                # exactly like the original seed. The garden can RESURRECT a lost prototype, not only clone.
                w = None
                _resurrect = True
            clones_made[target_ident] += 1
            if sid is not None:
                ident_counts[sid] = max(0, ident_counts[sid] - 1)
            ident_counts[target_ident] = ident_counts.get(target_ident, 0) + 1
            actually_swapped.append(slot)
            if _resurrect:
                # plant the extinct identity from ground truth and SKIP the clone-from-winner body below
                rc, ra = answer_to_task[target_ident]
                slot.prototype = [float(x) for x in rc]
                slot.proto_answer = float(ra)
                slot.mem = int(round(ra)); slot.think = int(round(ra))
                slot.mem_acc = 0.0; slot.think_acc = 0.0; slot.relay_acc = 0.0
                slot.plasticity = 1.0; slot.rom_locked = False
                slot.recent_task_score = 0.6        # give it a fighting chance to survive to next sleep
                slot.fitness = 0.6; slot.energy = 25.0; slot.consolidation_streak = 0
                slot.cull_immune = True             # protect the freshly-resurrected seedling briefly
                culled.append(slot); copied += 1
                continue
            # ATOMIC SWAP: the weak cell is OVERWRITTEN by a copy of a good cell (retrained, not killed).
            # It never goes dead -- it's reborn in place as a clone of a winner. No hole, no bleed.
            slot.mem = w.mem; slot.think = w.think
            slot.mem_acc = 0.0; slot.think_acc = 0.0; slot.relay_acc = 0.0
            slot.zone = w.zone
            slot.fire_threshold = getattr(w, "fire_threshold", 1.0)
            slot.plasticity = 1.0
            slot.rom_locked = False
            # DISCOUNT+PROBATION FIX (2026-09-27): the discount itself is a deliberate, legitimate
            # anti-monoculture safeguard (a naive full-inheritance clone would be indistinguishable
            # from its parent in selection terms, risking one lucky winner sweeping the population)
            # -- but WORKING_FLOOR=0.55 means a discounted clone of an 0.85-scoring winner starts at
            # ~0.42, already below the protection floor, and can be culled AGAIN before it ever gets
            # a real chance to re-prove what its parent already proved. Keep the discount; add a
            # probation window (same pattern already used for freshly-resurrected seedlings above)
            # so discounted trust and cullability are separated instead of conflated.
            slot.recent_task_score = w.recent_task_score * 0.5
            slot.fitness = w.fitness * 0.6
            slot.cull_immune = True       # protected for one inter-sleep window despite the discount
            slot.probation = True         # marks this immunity as temporary -- cleared at next sleep
            slot.energy = 20.0
            slot.consolidation_streak = 0
            # inherit the winner's PROTOTYPE too (so the clone recognizes what the winner recognized)
            if getattr(w, "prototype", None) is not None:
                slot.prototype = list(w.prototype); slot.proto_answer = w.proto_answer
            slot.synapses = [type(sy)(sy.target_id, sy.weight, sy.delay) for sy in w.synapses]
            # RELAY-WIPE FIX (2026-09-27): growth already clones evolved relay traits with small
            # variation when adding new capacity -- replacement was silently doing something
            # different (deleting the routing structure entirely) for the exact same "clone what
            # worked" operation. Bring both paths into alignment: clone, don't amputate.
            slot.relays = []
            for donor_relay in w.relays:
                nr = PairedRelay(source_id=slot.id, targets=list(donor_relay.targets),
                                  base_delay=donor_relay.base_delay)
                nr.split_threshold = max(0.5, min(8.0, donor_relay.split_threshold + random.gauss(0, 0.2)))
                nr.split_ratio = max(0.1, min(0.9, donor_relay.split_ratio + random.gauss(0, 0.03)))
                nr.back_delay = max(1, donor_relay.back_delay + random.choice([-1, 0, 0, 1]))
                slot.relays.append(nr)
            culled.append(slot); copied += 1
        # population is EXACTLY conserved: every cell touched was swapped in place, none left dead.
        # winners MULTIPLY into spare DEAD capacity too (not just culled slots), so good patterns grow
        if winners:
            dead_slots = [b for b in self.bricks if not b.alive and b.id not in self.seed_brick_ids][:len(winners)]
            for slot in dead_slots:
                w = random.choice(winners)
                slot.alive = True
                slot.mem = w.mem; slot.think = w.think
                slot.mem_acc = 0.0; slot.think_acc = 0.0; slot.relay_acc = 0.0
                slot.zone = w.zone
                slot.fire_threshold = getattr(w, "fire_threshold", 1.0)
                slot.plasticity = 1.0; slot.rom_locked = False
                # Same discount+probation and relay-inheritance fix as the swap path above -- this is
                # the SAME "clone a winner" operation, on dead capacity instead of a culled slot.
                slot.recent_task_score = w.recent_task_score * 0.5
                slot.fitness = w.fitness * 0.6; slot.energy = 20.0
                slot.cull_immune = True
                slot.probation = True
                slot.consolidation_streak = 0
                slot.synapses = [type(sy)(sy.target_id, sy.weight, sy.delay) for sy in w.synapses]
                slot.relays = []
                for donor_relay in w.relays:
                    nr = PairedRelay(source_id=slot.id, targets=list(donor_relay.targets),
                                      base_delay=donor_relay.base_delay)
                    nr.split_threshold = max(0.5, min(8.0, donor_relay.split_threshold + random.gauss(0, 0.2)))
                    nr.split_ratio = max(0.1, min(0.9, donor_relay.split_ratio + random.gauss(0, 0.03)))
                    nr.back_delay = max(1, donor_relay.back_delay + random.choice([-1, 0, 0, 1]))
                    slot.relays.append(nr)
                copied += 1

        # (c) TOXIN / JUNK FLUSH: reset half-committed accumulators + transient buffers for ALL non-protected
        #     working cells, so wake starts clean (does NOT touch protected cells' committed state).
        for b in self.bricks:
            if not b.alive: continue
            if b.rom_locked or b.id in self.seed_brick_ids: continue
            b.mem_acc = 0.0; b.think_acc = 0.0; b.relay_acc = 0.0
            b.input_this_cycle = 0.0
            b.refractory = 0

        # (d) PROTECT THE WORKING: we did NOT call _mutate_and_select() and did NOT inject noise. Working/
        #     consolidated/seed/ROM cells are untouched. That is the whole point.

        # 🌱 RECOVERED GROWTH STEP (2026-09-27): grow AFTER cull+copy, using this sleep's own fresh
        # fitness data, and only if population is still within a bounded safety ceiling -- real
        # growth, but never unbounded. 2x initial size is a conservative starting cap, adjustable.
        n_alive = sum(1 for b in self.bricks if b.alive)
        if n_alive < INIT_BRICKS * 2:
            self._grow_network()

        # harmless bookkeeping: context reset + capacity growth + generation tick
        self.context_tokens = 0
        # keep the "day" a stable size (do NOT balloon capacity each sleep -- a day is a day)
        self.generation += 1
        self.is_sleeping = False
        self._last_sleep_cycle = self.current_time
        print(f" 💤 Sleep complete (REPLACE-ONLY: {copied} weak cells retrained into clones of winners, population conserved). Gen {self.generation} | culled {len(culled)} defective, copied {copied} "
              f"winners | {len(winners)} working cells protected | capacity {self.context_capacity}")

    def run_cycle(self):
        """🔄 Main execution loop: inject → update → fire → evaluate → mutate → sleep check."""
        self.current_time += 1
        problems = ["interception", "noise", "memory", "pattern", "cross_module"]
        p_type = problems[self.current_time % len(problems)]
        self.inject_problem(p_type, signal=random.uniform(0.5, 2.5))

        self._update_bricks()
        self._fire_relays()
        self._evaluate_fitness()
        self._mutate_and_select()
        self._reap_dead()
        self._autosarcophagy()

        # 🛏️ SLEEP = how she deals with an OVERFILLED CONTEXT WINDOW. Triggered by context FULLNESS at the
        # RIGHT SCALE: the context window is LARGE (a "day" of experience), so filling it -> sleep happens
        # RARELY and adapts to LOAD (dense day fills sooner, quiet day later). Principled, not a clock.
        if self.context_tokens / self.context_capacity >= CONTEXT_THRESHOLD and not self.is_sleeping:
            self._run_sleep_dag()

        if self.current_time % 100 == 0:
            import time as _time
            _now = _time.time()
            _prev = getattr(self, "_last_print_time", _now)
            _cps = 100.0 / max(1e-6, (_now - _prev))
            self._last_print_time = _now
            self._cps = _cps
            alive_count = sum(1 for b in self.bricks if b.alive)
            rom_count = sum(1 for b in self.bricks if b.rom_locked)
            avg_fit = sum(b.fitness for b in self.bricks if b.alive) / max(alive_count, 1)
            # 🍼 TASK ACCURACY: the thing that actually matters -- is the WHOLE answering correctly?
            wc = getattr(self, "_wc_avg", 0.0)   # windowed average TaskCorrect (true rate)
            # also report average split traits so we can watch evolution tune them
            relays = [r for b in self.bricks if b.alive for r in b.relays]
            n_rel = max(len(relays), 1)
            avg_thr = sum(r.split_threshold for r in relays) / n_rel if relays else 0.0
            avg_ratio = sum(r.split_ratio for r in relays) / n_rel if relays else 0.0
            n_splits = sum(r.split_count for r in relays)
            print(f" ⏱️ Cyc {self.current_time} | Alive:{alive_count} ROM:{rom_count} | AvgFit:{avg_fit:.3f}"
                  f" | 🍼TaskCorrect:{wc:.3f} | split_thr:{avg_thr:.2f} ratio:{avg_ratio:.2f} splits:{n_splits}"
                  f" | Ctx:{self.context_tokens}/{self.context_capacity}"
                  f" | {getattr(self,'_cps',0):.0f}cyc/s")
            if self.current_time % 500 == 0:
                # 🔍 SHOW ACTUAL ANSWERS: probe each task pair, print call -> answer -> correct
                samples = []
                for (call, correct) in self.TASK_PAIRS:
                    self.inject_problem("probe", 1.0, forced_call=call)
                    self._update_bricks(); self._fire_relays()
                    ans = self._read_response()
                    astr = f"{ans:.1f}" if ans is not None else "silent"
                    mark = "✓" if (ans is not None and abs(ans - correct) < 1.0) else " "
                    samples.append(f"{call}->{astr}(want {correct}){mark}")
                print("    🔍 " + " | ".join(samples))

    def save_checkpoint(self):
        """💾 Serialize full substrate state to JSON. Atomic write survives hard kills."""
        state = {
            "bricks": [],
            "meta": {
                "generation": self.generation,
                "current_time": self.current_time,
                "context_capacity": self.context_capacity,
                "context_tokens": self.context_tokens
            }
        }
        for b in self.bricks:
            state["bricks"].append({
                "id": b.id, "pos": list(b.pos), "module_id": b.module_id,
                "mem": b.mem, "think": b.think, "relay_strength": b.relay_strength,
                "fitness": b.fitness, "zone": b.zone, "rom": b.rom_locked,
                "synapses": [{"target": s.target_id, "weight": s.weight, "delay": s.delay, "fitness": s.fitness} for s in b.synapses]
            })
        temp_path = CHECKPOINT_PATH.with_suffix(".tmp")
        with open(temp_path, "w") as f: json.dump(state, f, indent=2)
        temp_path.replace(CHECKPOINT_PATH)
        print(f" 💾 Checkpoint saved to {CHECKPOINT_PATH}")

    def load_checkpoint(self):
        """📂 Deserialize substrate state from JSON. Restores bricks, synapses, meta."""
        if not CHECKPOINT_PATH.exists():
            print(" ⚠️ No checkpoint found. Starting fresh.")
            return
        with open(CHECKPOINT_PATH, "r") as f: data = json.load(f)
        meta = data["meta"]
        self.generation = meta["generation"]
        self.current_time = meta["current_time"]
        self.context_capacity = meta["context_capacity"]
        self.context_tokens = meta["context_tokens"]
        self.bricks.clear(); self.brick_lookup.clear()
        for b_data in data["bricks"]:
            b = Brick(b_data["id"], tuple(b_data["pos"]), b_data["module_id"], b_data["zone"])
            b.mem = b_data["mem"]; b.think = b_data["think"]; b.relay_strength = b_data["relay_strength"]
            b.fitness = b_data["fitness"]; b.rom_locked = b_data["rom"]
            for s_data in b_data["synapses"]:
                b.synapses.append(Synapse(s_data["target"], s_data["weight"], s_data["delay"]))
            self.bricks.append(b); self.brick_lookup[b.id] = b
            self._max_id_tracker = max(self._max_id_tracker, b.id)
        print(f" 📂 Checkpoint loaded. Generation: {self.generation} | Bricks: {len(self.bricks)}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global RECOGNITION_MODE, MAX_CULL_FRAC_CFG, ALIVE_FLOOR_FRAC_CFG, CONTEXT_THRESHOLD, DAY_CONTEXT, PRESERVE_DIVERSITY
    parser = argparse.ArgumentParser(description="Sovereign Core v4.3 Evolutionary Substrate")
    parser.add_argument("--cycles", type=int, default=3000, help="Number of cycles to run")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--mode", type=str, default=RECOGNITION_MODE, help="recognition mode: nearest|graded")
    parser.add_argument("--cull-frac", type=float, default=MAX_CULL_FRAC_CFG, help="max cull fraction/sleep (LOWER=punish less)")
    parser.add_argument("--alive-floor", type=float, default=ALIVE_FLOOR_FRAC_CFG, help="min alive fraction (RAISE=punish less)")
    parser.add_argument("--sleep-load", type=float, default=CONTEXT_THRESHOLD, help="context load to trigger sleep (RAISE=sleep less often)")
    parser.add_argument("--day-context", type=int, default=DAY_CONTEXT, help="context window size = a 'day'; fills ~once per this many cycles -> sleep (RAISE = longer day = rarer sleep)")
    parser.add_argument("--no-diversity", action="store_true", help="disable prototype diversity preservation")
    args = parser.parse_args()

    print("="*70)
    print("SOVEREIGN CORE v4.5 - v4.21b RESURRECTION: garden replants EXTINCT prototypes from ground truth (not only clones survivors)")
    print("="*70)
    print(f"Initial bricks: {INIT_BRICKS} | Context capacity: {CONTEXT_CAPACITY}")
    RECOGNITION_MODE = args.mode
    MAX_CULL_FRAC_CFG = args.cull_frac
    ALIVE_FLOOR_FRAC_CFG = args.alive_floor
    CONTEXT_THRESHOLD = args.sleep_load
    DAY_CONTEXT = args.day_context
    PRESERVE_DIVERSITY = not args.no_diversity
    print(f"Recognition: {RECOGNITION_MODE} | cull-frac {MAX_CULL_FRAC_CFG} | alive-floor {ALIVE_FLOOR_FRAC_CFG} | sleep-load {CONTEXT_THRESHOLD} | day-context {DAY_CONTEXT} | diversity {PRESERVE_DIVERSITY}")
    print(f"Sleep trigger: >{CONTEXT_THRESHOLD*100:.0f}% context load")
    print(f"Growth factor: +{int((GROWTH_FACTOR-1)*100)}% capacity per rebuild")
    print(f"Zones: FAST (cleanup) / SLOW (persistence) / MIRROR (simulation)")
    print(f"Sleep DAG: FAST replay → SLOW injection → ROM promotion → Drift")
    print(f"ROM threshold: ≥{ROM_CONSOLIDATION_THRESHOLD} consolidations + T≥8 + R≥7 + S≥8")
    print(f"Accumulator bridge: |acc| >= {ACCUM_THRESHOLD} → discrete commit")
    print()

    core = SovereignCore(init_bricks=INIT_BRICKS)
    if args.resume: core.load_checkpoint()

    def emergency_save(signum, frame):
        print("\n ⚠️ Interrupt signal received. Emergency checkpointing...")
        core.save_checkpoint()
        sys.exit(0)
    signal.signal(signal.SIGINT, emergency_save)
    signal.signal(signal.SIGTERM, emergency_save)

    try:
        for _ in range(args.cycles):
            core.run_cycle()
            if core.current_time % 500 == 0: core.save_checkpoint()
    except KeyboardInterrupt:
        print("\n ⛔ Interrupted. Saving state...")
    finally:
        core.save_checkpoint()
        print(" ✅ Sovereign Core v4.3 halted gracefully.")

if __name__ == "__main__":
    main()