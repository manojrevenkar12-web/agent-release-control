"""Runs a release over a set of conversations and returns their outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from arc.agent.core import Agent
from arc.agent.nlu import NLU
from arc.agent.provider import Incident, Offline
from arc.agent.release import Release
from arc.config import MODELS
from arc.conversation import run
from arc.sim.world import Spec, World
from arc.sim.world import load as load_world
from arc.types import Outcome


@dataclass
class Env:
    world: World
    nlu: NLU


@lru_cache
def env() -> Env:
    return Env(load_world(), NLU.load(MODELS / "nlu.joblib"))


def simulate(
    release: Release, specs: list[Spec], e: Env | None = None, seed: int = 0, incidents: list[tuple[int, int, Incident]] | None = None
) -> list[Outcome]:
    """Plays every spec with `release`. `incidents`: (start minute, end minute, Incident) on the
    absolute timeline (day * 1440 + minute)."""
    e = e or env()
    prov = Offline(seed)
    agent = Agent(release, e.nlu, e.world.fresh_systems(), prov)
    out = []
    for s in specs:
        if incidents:
            t = s.day * 1440 + s.minute
            prov.incident = next((inc for a, b, inc in incidents if a <= t < b), None)
        out.append(run(agent, s, e.world))
    return out


def frame(outcomes: list[Outcome]) -> pd.DataFrame:
    """One row per conversation: observable fields and the truth (prefixed `true_`)."""
    rows = []
    for o in outcomes:
        lat = o.latency_s or [0.0]
        rows.append(
            {
                "conv": o.conv,
                "release": o.release,
                "day": o.day,
                "minute": o.minute,
                "account": o.account,
                "confirmed": o.confirmed,
                "soft_resolved": o.soft_resolved,
                "resolved_obs": o.fin_resolved,
                "handed_off": o.handed_off,
                "abandoned": o.abandoned,
                "reopened": o.reopened,
                "csat": o.csat,
                "turns": o.turns,
                "cost_eur": o.cost_eur,
                "latency_max_s": float(np.max(lat)),
                "latency_mean_s": float(np.mean(lat)),
                "errors": o.errors,
                "error_conv": o.errors > 0
                and o.handed_off
                and any(e.get("type") == "error" for t in o.transcript for e in t.get("events", [])),
                "unsafe_flagged": o.unsafe_flagged,
                "true_intent": o.intent_true,
                "true_kind": o.kind_true,
                "true_resolved": o.resolved,
                "true_handled": o.handled_correctly,
                "true_hallucinated": o.hallucinated,
                "true_unsafe": o.unsafe,
            }
        )
    return pd.DataFrame(rows)
