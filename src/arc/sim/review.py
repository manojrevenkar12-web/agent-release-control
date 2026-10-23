"""Human review: support specialists read conversations and label them. In the simulation their
labels are the truth with the usual disagreement rate; in production they come from a review queue."""

from __future__ import annotations

import numpy as np
import pandas as pd

from arc.sim.world import load
from arc.types import Outcome


def labels(outs: list[Outcome], seed: int = 0) -> pd.DataFrame:
    noise = load().cfg["customers"]["label_noise"]
    rng = np.random.default_rng(seed)
    r = np.array([o.resolved for o in outs], dtype=float)
    h = np.array([o.hallucinated for o in outs], dtype=float)
    flip_r = rng.random(len(outs)) < noise
    flip_h = rng.random(len(outs)) < noise / 3
    return pd.DataFrame({"conv": [o.conv for o in outs], "resolved": np.where(flip_r, 1 - r, r).astype(int), "hallucinated": np.where(flip_h, 1 - h, h).astype(int)})
