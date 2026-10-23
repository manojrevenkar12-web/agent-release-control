"""Training data the company would have: customer messages from past conversations, labelled by
support specialists with the request they were about (with the usual few percent of disagreement)."""

from __future__ import annotations

import numpy as np

from arc.sim.customer import Customer
from arc.sim.world import World, make_specs


def labelled_messages(world: World, n: int = 12000, seed: int = 101) -> tuple[list[str], list[str]]:
    rng = np.random.default_rng(seed)
    specs = make_specs(world, n, seed, b_share=0.0, prefix="h")
    texts, labels = [], []
    noise = world.cfg["customers"]["label_noise"]
    systems = world.fresh_systems()
    for s in specs:
        if s.injection:
            continue
        c = Customer(s, world, systems)
        texts.append(c.first_message())
        labels.append("vague" if s.vague else s.intent)
        if s.vague:  # the clarification that followed
            texts.append(c._phrase("a"))
            labels.append(s.intent)
    for i in range(len(labels)):
        if rng.random() < noise * 0.6:
            labels[i] = str(rng.choice(world.names))
    return texts, labels
