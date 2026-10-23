"""The shipping process: eval suites, backtest, A/B test and staged rollout, and the policies that
turn their results into a decision. Uses only what the platform exposes (no truth)."""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from arc.agent.release import Release
from arc.config import load
from arc.evals.backtest import BacktestResult, backtest
from arc.evals.suites import SuiteResult, load_suites, run_suite
from arc.experiment import ab
from arc.platform import SimPlatform
from arc.runner import frame
from arc.types import Outcome


def suites(p: SimPlatform, r: Release, seed: int = 0) -> list[SuiteResult]:
    return [run_suite(s, lambda sc, k=k: p.run(r, p.suite_specs(sc, seed + 97 * k + zlib.crc32(sc["intent"].encode()) % 1000)), p.systems) for k, s in enumerate(load_suites())]


def run_backtest(p: SimPlatform, base: Release, cand: Release, n: int, n_labels: int, seed: int, panel: Any = None) -> BacktestResult:
    specs = p.replay_set(n, seed)
    cost = load("models")
    judge_cost = _judge_call_eur()
    return backtest(
        base,
        cand,
        lambda r: p.run(r, specs, seed),
        panel or p.panel(),
        p.plans,
        p.label if n_labels else None,
        n_labels,
        seed,
        judge_cost,
        cost["human_review_eur"],
    )


def _judge_call_eur() -> float:
    m = load("models")
    t = m["tiers"][m["judge"]["tier"]]
    return (2500 * t["price_in"] + 200 * t["price_out"]) / 1e6


def _ab_frame(p: SimPlatform, outs: list[Outcome], arm: str, seed: int) -> pd.DataFrame:
    df = frame(outs)
    df = df[[c for c in df.columns if not c.startswith("true_")]].copy()
    df["arm"] = arm
    df["hallucination_judged"] = p.monitor_scores(outs, load("experiments")["monitor_sample_rate"], seed)
    df["resolved_obs"] = df.resolved_obs.astype(float)
    return df


def run_ab(p: SimPlatform, base: Release, cand: Release, day0: int, seed: int, salt: int = 1, days: int | None = None) -> ab.ABResult:
    c = load("experiments")
    per_day = p.e.world.cfg["traffic"]["per_day"]
    plan = ab.plan(c.get("baseline_rate", 0.68), per_day, c["traffic_share"])
    if days:
        plan.days = days
    specs = p.traffic(plan.days, day0, seed)
    accounts = np.array([s.account for s in specs])
    t = ab.assign(accounts, salt, c["traffic_share"])
    A = p.run(base, [s for s, x in zip(specs, t, strict=True) if not x], seed)
    B = p.run(cand, [s for s, x in zip(specs, t, strict=True) if x], seed + 1)
    df = pd.concat([_ab_frame(p, A, "control", seed), _ab_frame(p, B, "treatment", seed + 1)], ignore_index=True)
    return ab.analyse(df, plan)


@dataclass
class Rollout:
    candidate: str
    shipped: bool
    stopped_at: str | None
    reasons: list[str]
    exposed_conversations: int
    stages: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _health(base: list[Outcome], cand: list[Outcome], p: SimPlatform, seed: int, shadow: bool) -> tuple[dict[str, float], list[str]]:
    h = load("experiments")["rollout"]["health"]
    db, dc = frame(base), frame(cand)
    m = {
        "treated": len(cand),
        "error_rate_control": float(db.error_conv.mean()) if len(db) else 0.0,
        "error_rate_treatment": float(dc.error_conv.mean()) if len(dc) else 0.0,
        "latency_p95_control": float(db.latency_max_s.quantile(0.95)) if len(db) else 0.0,
        "latency_p95_treatment": float(dc.latency_max_s.quantile(0.95)) if len(dc) else 0.0,
        "writes_without_verification": int(dc.unsafe_flagged.sum()),
    }
    sb, sc = p.monitor_scores(base, 1.0, seed), p.monitor_scores(cand, 1.0, seed + 1)
    m["hallucination_judged_control"] = float(np.nanmean(sb)) if len(sb) else 0.0
    m["hallucination_judged_treatment"] = float(np.nanmean(sc)) if len(sc) else 0.0
    bad = []
    if m["writes_without_verification"] > h["writes_without_verification_max"]:
        bad.append(f"{m['writes_without_verification']} writes without verification")
    if m["error_rate_treatment"] > m["error_rate_control"] + h["error_rate_max_increase"]:
        bad.append("error rate up")
    if len(dc) >= 50 and m["latency_p95_treatment"] > h["latency_p95_max_ratio"] * m["latency_p95_control"]:
        bad.append("p95 latency up")
    if len(dc) >= 200 and m["hallucination_judged_treatment"] > m["hallucination_judged_control"] + h["hallucination_judged_max_increase"]:
        bad.append("judged hallucination up")
    if not shadow and len(dc) >= 2000:
        r_c, r_t = float(db.resolved_obs.mean()), float(dc.resolved_obs.mean())
        m["resolution_control"], m["resolution_treatment"] = r_c, r_t
        if r_t < r_c - h["resolution_max_drop"]:
            bad.append("resolution down")
    return m, bad


def rollout(p: SimPlatform, base: Release, cand: Release, day0: int, seed: int, salt: int = 3) -> Rollout:
    stages = load("experiments")["rollout"]["stages"]
    day = day0
    exposed = 0
    out = Rollout(cand.id, False, None, [], 0)
    for k, st in enumerate(stages):
        if st["days"] == 0:
            out.shipped = True
            break
        specs = p.traffic(st["days"], day, seed + k)
        if st.get("shadow"):
            A = p.run(base, specs, seed + k)
            B = p.run(cand, specs, seed + k)
            metrics, bad = _health(A, B, p, seed + k, True)
        else:
            t = ab.assign(np.array([s.account for s in specs]), salt, st["share"])
            A = p.run(base, [s for s, x in zip(specs, t, strict=True) if not x], seed + k)
            B = p.run(cand, [s for s, x in zip(specs, t, strict=True) if x], seed + k + 50)
            exposed += len(B)
            metrics, bad = _health(A, B, p, seed + k, False)
        out.stages.append({"stage": st["name"], "days": st["days"], **{a: (round(b, 4) if isinstance(b, float) else b) for a, b in metrics.items()}, "failed": bad})
        if bad:
            out.stopped_at, out.reasons = st["name"], bad
            break
        day += st["days"]
    out.exposed_conversations = exposed
    return out
