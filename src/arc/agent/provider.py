"""Model provider: what a call costs, how long it takes and whether it fails.

`Offline` is a stand-in with the latency, error and price profile of real tiers (config/models.yaml);
incidents (slow or failing provider) can be switched on to test alarms and fallbacks. With
ARC_LLM=claude and an API key, `arc.agent.llm` makes real calls instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from arc.config import load
from arc.types import Call


@dataclass
class Incident:
    latency_factor: float = 1.0
    error_rate: float = 0.0
    tier: str | None = None  # None = all tiers


@dataclass
class Offline:
    seed: int = 0
    tiers: dict[str, Any] = field(default_factory=lambda: load("models")["tiers"])
    incident: Incident | None = None

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)

    def call(self, purpose: str, tier: str, tokens_in: int, tokens_out: int) -> Call:
        t = self.tiers[tier]
        lat = (t["latency_s"] + t["per_1k_tokens_s"] * (tokens_in + 4 * tokens_out) / 1000) * float(self.rng.lognormal(0, 0.35))
        err = t["error_rate"]
        inc = self.incident
        if inc and (inc.tier is None or inc.tier == tier):
            lat *= inc.latency_factor
            err = max(err, inc.error_rate)
        ok = bool(self.rng.random() >= err)
        cost = (tokens_in * t["price_in"] + tokens_out * t["price_out"]) / 1e6
        return Call(purpose, tier, tokens_in, tokens_out, cost, lat if ok else min(lat * 3, 30.0), ok)


def tokens(text: str) -> int:
    return max(1, len(text) // 4)
