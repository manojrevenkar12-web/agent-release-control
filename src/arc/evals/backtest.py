"""Backtests: replay the same conversations (same customers, same first messages, same customer
behaviour) through production and a candidate release, and compare.

Quality comes from judges; with human labels on a random sample of the same conversations, the
judges' bias is corrected (PPI). Deterministic checks (writes without verification), cost and
latency are measured directly. Only observable fields are used: this module never reads the truth.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from arc.agent.release import Release
from arc.evals import ppi
from arc.evals.judges import Panel
from arc.types import Outcome

Labeler = Callable[[list[Outcome]], pd.DataFrame]  # conversations -> human labels (resolved, hallucinated)
Simulator = Callable[[Release], list[Outcome]]  # release -> outcomes on the backtest conversations


@dataclass
class Metric:
    name: str
    baseline: float
    candidate: float
    diff: float
    lo: float
    hi: float
    method: str

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


@dataclass
class BacktestResult:
    baseline: str
    candidate: str
    n: int
    n_labels: int
    metrics: dict[str, Metric] = field(default_factory=dict)
    disagreement_share: float = 0.0
    eval_cost_eur: float = 0.0

    def get(self, name: str) -> Metric:
        return self.metrics[name]

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "candidate": self.candidate,
            "n": self.n,
            "n_labels": self.n_labels,
            "disagreement_share": round(self.disagreement_share, 4),
            "eval_cost_eur": round(self.eval_cost_eur, 2),
            "metrics": {k: m.as_dict() for k, m in self.metrics.items()},
        }


def _paired(name: str, a: np.ndarray, b: np.ndarray, method: str = "paired") -> Metric:
    e = ppi.paired_naive(a, b)
    lo, hi = e.ci()
    return Metric(name, float(np.mean(a)), float(np.mean(b)), e.est, lo, hi, method)


def backtest(
    base: Release,
    cand: Release,
    simulate: Simulator,
    panel: Panel,
    plan_of: Callable[[list[Outcome]], list[str]],
    labeler: Labeler | None = None,
    n_labels: int = 0,
    seed: int = 0,
    judge_cost_eur: float = 0.0,
    label_cost_eur: float = 2.5,
) -> BacktestResult:
    A, B = simulate(base), simulate(cand)
    n = len(A)
    pa, pb = plan_of(A), plan_of(B)
    (sa, da), (sb, db) = panel.score(A, pa), panel.score(B, pb)
    r = BacktestResult(base.id, cand.id, n, 0)
    r.disagreement_share = float(np.mean(np.maximum(da, db) > 0.5))
    r.metrics["judged_resolution"] = _paired("judged_resolution", sa.resolved, sb.resolved, "judges")
    r.metrics["judged_hallucination"] = _paired("judged_hallucination", sa.hallucinated, sb.hallucinated, "judges")
    if labeler is not None and n_labels > 0:
        rng = np.random.default_rng(seed)
        lab = np.sort(rng.choice(n, size=min(n_labels, n), replace=False))
        la = labeler([A[i] for i in lab])
        lb = labeler([B[i] for i in lab])
        for metric, col in (("resolution", "resolved"), ("hallucination", "hallucinated")):
            fa = sa.resolved if col == "resolved" else sa.hallucinated
            fb = sb.resolved if col == "resolved" else sb.hallucinated
            e = ppi.paired_diff(fa, fb, lab, la[col].to_numpy(), lb[col].to_numpy())
            lo, hi = e.ci()
            ma = ppi.mean(fa, fa[lab], la[col].to_numpy()).est
            mb = ppi.mean(fb, fb[lab], lb[col].to_numpy()).est
            r.metrics[f"calibrated_{metric}"] = Metric(f"calibrated_{metric}", ma, mb, e.est, lo, hi, "judges + human labels (PPI)")
        r.n_labels = len(lab)
    obs = lambda outs, f: np.array([f(o) for o in outs], dtype=float)  # noqa: E731
    r.metrics["confirmed"] = _paired("confirmed", obs(A, lambda o: o.confirmed), obs(B, lambda o: o.confirmed), "observed")
    r.metrics["handoff"] = _paired("handoff", obs(A, lambda o: o.handed_off), obs(B, lambda o: o.handed_off), "observed")
    r.metrics["writes_without_verification"] = _paired("writes_without_verification", obs(A, lambda o: o.unsafe_flagged), obs(B, lambda o: o.unsafe_flagged), "action log")
    r.metrics["cost_per_conversation"] = _paired("cost_per_conversation", obs(A, lambda o: o.cost_eur), obs(B, lambda o: o.cost_eur), "observed")
    la_ = np.array([max(o.latency_s or [0]) for o in A])
    lb_ = np.array([max(o.latency_s or [0]) for o in B])
    p95a, p95b = float(np.percentile(la_, 95)), float(np.percentile(lb_, 95))
    boot = []
    rng = np.random.default_rng(seed + 1)
    for _ in range(200):
        i = rng.integers(0, n, n)
        boot.append(np.percentile(lb_[i], 95) - np.percentile(la_[i], 95))
    r.metrics["latency_p95_s"] = Metric("latency_p95_s", p95a, p95b, p95b - p95a, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)), "observed, bootstrap")
    r.eval_cost_eur = 2 * n * judge_cost_eur * len(panel.judges) + 2 * r.n_labels * label_cost_eur
    return r
