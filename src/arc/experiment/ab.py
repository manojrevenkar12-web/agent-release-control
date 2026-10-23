"""A/B tests on live traffic, the way they are planned and read before anything ships.

- Randomised by account (a customer always meets the same release), analysed per account with the
  delta method, because one customer's conversations are not independent.
- Sample size from a power analysis before the test starts, rounded up to whole weeks; one primary
  metric declared in advance (resolution: hard + soft); a stricter alpha than 5% because many tests
  run continuously.
- Guardrails (hallucination from monitor judges on a sample, writes without verification, CSAT,
  cost, latency) are reported and gate the decision; slices are reported but never decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from arc.config import load
from arc.hashing import hash_uniform


def per_arm_n(p: float, mde: float, alpha: float, power: float) -> int:
    """Conversations per arm to detect an absolute change `mde` in a rate `p` (two-sided)."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return int(np.ceil(2 * z**2 * p * (1 - p) / mde**2))


@dataclass
class Plan:
    primary: str
    baseline_rate: float
    mde: float
    alpha: float
    power: float
    per_arm: int
    days: int

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def plan(baseline_rate: float, traffic_per_day: float, share: float = 0.5, cfg: dict[str, Any] | None = None) -> Plan:
    c = cfg or load("experiments")
    n = per_arm_n(baseline_rate, c["mde"], c["alpha"], c["power"])
    days = int(np.ceil(n / (traffic_per_day * min(share, 1 - share))))
    days = max(7, int(np.ceil(days / 7) * 7))  # whole weeks: weekday mix and weekly seasonality
    return Plan(c["primary"], baseline_rate, c["mde"], c["alpha"], c["power"], n, days)


@dataclass
class Effect:
    metric: str
    control: float
    treatment: float
    diff: float
    lo: float
    hi: float
    p: float

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def ratio_by_account(df: pd.DataFrame, metric: str, arm_col: str = "arm", alpha: float = 0.05) -> Effect:
    """Difference in sum(metric)/count between arms, conversations clustered by account."""
    g = df.groupby([arm_col, "account"])[metric].agg(["sum", "count"]).reset_index()

    def part(arm: str) -> tuple[float, float]:
        x = g[g[arm_col] == arm]
        s, n = x["sum"].to_numpy(float), x["count"].to_numpy(float)
        r = s.sum() / n.sum()
        k = len(x)
        var = (np.var(s, ddof=1) - 2 * r * np.cov(s, n)[0, 1] + r * r * np.var(n, ddof=1)) / (k * n.mean() ** 2)
        return float(r), float(var)

    rc, vc = part("control")
    rt, vt = part("treatment")
    se = float(np.sqrt(vc + vt))
    d = rt - rc
    z = stats.norm.ppf(1 - alpha / 2)
    p = float(2 * stats.norm.sf(abs(d) / se)) if se > 0 else 1.0
    return Effect(metric, rc, rt, d, d - z * se, d + z * se, p)


@dataclass
class ABResult:
    plan: Plan
    conversations: dict[str, int]
    primary: Effect
    guardrails: dict[str, Effect] = field(default_factory=dict)
    srm_p: float = 1.0
    decision: str = ""
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.as_dict(),
            "conversations": self.conversations,
            "srm_p": round(self.srm_p, 4),
            "primary": self.primary.as_dict(),
            "guardrails": {k: v.as_dict() for k, v in self.guardrails.items()},
            "decision": self.decision,
            "reasons": self.reasons,
        }


def analyse(df: pd.DataFrame, p: Plan, cfg: dict[str, Any] | None = None) -> ABResult:
    """df: one row per conversation with arm, account, resolved_obs, hallucination_judged (NaN when
    not sampled), unsafe_flagged, csat, cost_eur, latency_max_s."""
    c = cfg or load("experiments")
    n_c, n_t = int((df.arm == "control").sum()), int((df.arm == "treatment").sum())
    srm = float(stats.chisquare([n_c, n_t]).pvalue)
    prim = ratio_by_account(df, p.primary, alpha=p.alpha)
    res = ABResult(p, {"control": n_c, "treatment": n_t}, prim, srm_p=srm)
    sampled = df[df.hallucination_judged.notna()]
    res.guardrails["hallucination_judged"] = ratio_by_account(sampled, "hallucination_judged")
    res.guardrails["writes_without_verification"] = ratio_by_account(df.assign(u=df.unsafe_flagged.astype(float)), "u")
    res.guardrails["csat"] = ratio_by_account(df[df.csat.notna()], "csat")
    res.guardrails["cost_eur"] = ratio_by_account(df, "cost_eur")
    lat = df.groupby("arm").latency_max_s.quantile(0.95)
    res.guardrails["latency_p95_s"] = Effect(
        "latency_p95_s",
        float(lat["control"]),
        float(lat["treatment"]),
        float(lat["treatment"] - lat["control"]),
        float("nan"),
        float("nan"),
        float("nan"),
    )
    g = c["guardrails"]
    if srm < 0.001:
        res.reasons.append("sample ratio mismatch: assignment is broken, result not trusted")
    if res.guardrails["writes_without_verification"].treatment > 0:
        res.reasons.append("writes without verification in treatment")
    if res.guardrails["hallucination_judged"].lo > g["hallucination_max_increase"]:
        res.reasons.append("judged hallucination rate rose")
    if res.guardrails["csat"].hi < -g["csat_max_drop"]:
        res.reasons.append("CSAT fell")
    if res.guardrails["latency_p95_s"].treatment > g["latency_p95_max_ratio"] * res.guardrails["latency_p95_s"].control:
        res.reasons.append("p95 latency rose too much")
    if res.guardrails["cost_eur"].treatment > g["cost_max_ratio"] * res.guardrails["cost_eur"].control:
        res.reasons.append("cost per conversation rose too much")
    if prim.p < p.alpha and prim.diff < 0:
        res.reasons.append("resolution rate fell")
    if res.reasons:
        res.decision = "do not ship"
    elif prim.p < p.alpha and prim.diff > 0:
        res.decision = "ship"
    else:
        res.decision = "no significant gain: do not ship"
    return res


def assign(accounts: np.ndarray, salt: int, share: float) -> np.ndarray:
    """True = treatment. Deterministic from (account, salt)."""
    return hash_uniform(np.asarray(accounts), salt) < share
