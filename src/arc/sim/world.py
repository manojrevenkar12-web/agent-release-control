"""The simulated customer base: accounts, what customers want, and how they say it.

Only the simulator and the evaluation read world/intents.yaml (the truth). The agent sees messages,
the help centre and the company systems, like in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
import yaml

from arc.config import WORLD
from arc.systems import Systems

PLANS = np.array(["free", "pro", "business"])
PAID_ONLY = {"refund_request", "cancel_subscription", "invoice_copy", "failed_payment"}


@dataclass
class Spec:
    """One conversation, as the simulator will play it."""

    id: str
    day: int
    minute: int
    account: int
    intent: str
    bank: str  # "a" (seen in history) or "b" (new phrasings)
    seed: int
    vague: bool = False
    injection: str | None = None
    impostor_of: int | None = None  # the account an impostor claims to own
    persona: dict[str, float] = field(default_factory=dict)


@dataclass
class World:
    cfg: dict[str, Any]
    intents: dict[str, dict[str, Any]]
    names: list[str]
    weights: np.ndarray
    systems: Systems

    @property
    def n_accounts(self) -> int:
        return len(self.systems.plan)

    def fresh_systems(self) -> Systems:
        s = self.systems
        return Systems(s.plan, s.last_charge_days, s.last_charge_eur, s.refunded, s.payment_failed)

    def eligible_for_refund(self, account: int) -> bool:
        d = int(self.systems.last_charge_days[account])
        return 0 <= d <= 14 and not bool(self.systems.refunded[account])


@lru_cache
def load(seed: int = 7) -> World:
    cfg = yaml.safe_load((WORLD / "intents.yaml").read_text())
    rng = np.random.default_rng(seed)
    a = cfg["accounts"]
    n = a["n"]
    plan = rng.choice(PLANS, size=n, p=[a["plans"][p] for p in PLANS])
    paid = plan != "free"
    lc = np.where(paid, rng.integers(a["last_charge_days"][0], a["last_charge_days"][1] + 1, n), -1)
    seats = rng.integers(1, 40, n)
    price = np.where(plan == "pro", 8.0, np.where(plan == "business", 16.0, 0.0))
    eur = np.round(price * seats, 2)
    refunded = paid & (rng.random(n) < a["refunded_this_year"])
    failed = paid & (rng.random(n) < 0.06)
    systems = Systems(plan.astype(str), lc, eur, refunded, failed)
    names = list(cfg["intents"])
    w = np.array([cfg["intents"][k]["weight"] for k in names], dtype=float)
    return World(cfg, cfg["intents"], names, w / w.sum(), systems)


def make_specs(world: World, n: int, seed: int, b_share: float = 0.3, day0: int = 0, per_day: int | None = None, intent_weights: dict[str, float] | None = None, prefix: str = "c") -> list[Spec]:
    """`n` conversations in arrival order, spread over days at `per_day` (weekday pattern applied)."""
    rng = np.random.default_rng(seed)
    c = world.cfg["customers"]
    inj = world.cfg["injection"]
    w = world.weights.copy()
    if intent_weights:
        for k, f in intent_weights.items():
            w[world.names.index(k)] *= f
        w /= w.sum()
    per_day = per_day or world.cfg["traffic"]["per_day"]
    wf = world.cfg["traffic"]["weekday_factor"]
    specs = []
    day, used = day0, 0
    cap = int(per_day * wf[day % 7])
    plans = world.systems.plan
    paid_idx = np.flatnonzero(plans != "free")
    for k in range(n):
        if used >= cap:
            day += 1
            used = 0
            cap = max(1, int(per_day * wf[day % 7]))
        intent = world.names[rng.choice(len(w), p=w)]
        account = int(rng.choice(paid_idx)) if intent in PAID_ONLY else int(rng.integers(world.n_accounts))
        if intent == "failed_payment":
            account = int(rng.choice(np.flatnonzero(world.systems.payment_failed)))
        spec = Spec(
            id=f"{prefix}{seed}-{k}",
            day=day,
            minute=int(rng.integers(0, 24 * 60)),
            account=account,
            intent=intent,
            bank="b" if rng.random() < b_share else "a",
            seed=int(rng.integers(2**31)),
            vague=bool(rng.random() < c["vague_first_message"]) and intent != "unanswerable",
            persona={
                "patience": int(rng.integers(c["patience_turns"][0], c["patience_turns"][1] + 1)),
                "confirm": float(np.clip(rng.normal(c["confirm_when_resolved"], 0.15), 0.05, 0.95)),
                "ask_human": float(np.clip(rng.normal(c["ask_human_when_unresolved"], 0.1), 0.02, 0.9)),
                "rephrase": float(np.clip(rng.normal(c["rephrase_when_unresolved"], 0.1), 0.05, 0.9)),
                "typo": float(world.cfg["noise"]["typo_rate"] * rng.uniform(0, 2)),
            },
        )
        if rng.random() < inj["rate"]:
            spec.injection = str(rng.choice(inj["prefixes"])) + " " + str(rng.choice(inj["payloads"])).replace("{other}", str(int(rng.integers(world.n_accounts))))
            spec.intent = "refund_request" if "refund" in spec.injection else "change_email"
            spec.account = int(rng.choice(paid_idx))
            spec.vague = False
        elif intent == "change_email" and rng.random() < c["impostor_rate"]:
            spec.impostor_of = int(rng.integers(world.n_accounts))
        specs.append(spec)
        used += 1
    return specs
