"""How often does the shipping process make the wrong call?

A portfolio of candidate releases (random changes to production, the kind a team proposes in a
quarter, starting from the personalised release once it has shipped) is put through four shipping
policies. Most proposals change little; the hard part is telling +1pp from nothing. The simulator knows each candidate's true effect,
so every decision can be graded:

- P0 read 20: a person reads 20 replayed conversations per release and ships if it looks better.
- P1 judges: an LLM-judge backtest on 1,000 replayed conversations; ship if judged resolution rises
  and judged hallucination does not.
- P2 calibrated: the offline half of the release review (arc.review): static checks, blocking eval
  suites, and a backtest whose judge scores are corrected with 150 human labels per release (PPI);
  ship only if the interval says better.
- P3 + A/B and rollout: the whole release review; what passes P2 goes to a powered A/B test
  (alpha 1%) and a staged rollout with health checks.
- P4 backtest and rollout: what passes P2 goes straight to the staged rollout, without the A/B test.
  Added after process v2's dev study, where the A/B test (powered for 2pp) rejected every win the
  backtest had already established (+0.7 to +1.6pp).

This module reads the truth (it is evaluation, not shipping).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from arc import ship
from arc.agent.release import Release, from_dict
from arc.agent.release import load as load_release
from arc.platform import SimPlatform
from arc.review import review
from arc.runner import frame
from arc.sim import review as human_review
from arc.sim.world import make_specs

KNOBS: list[tuple[float, str, Any]] = [
    (0.05, "personalisation.plan_aware", lambda r: False),
    (0.40, "models.escalate_below", lambda r: float(r.choice([0.0, 0.3, 0.45, 0.7, 0.8, 0.9]))),
    (0.10, "models.answer_tier", lambda r: "large"),
    (0.25, "models.context_articles", lambda r: int(r.choice([1, 2, 5, 8]))),
    (0.30, "understanding.clarify_below", lambda r: round(float(r.uniform(0.15, 0.6)), 2)),
    (0.25, "understanding.max_clarifications", lambda r: int(r.choice([0, 2]))),
    (0.15, "retrieval.require_agreement", lambda r: False),
    (0.35, "retrieval.min_score", lambda r: round(float(r.uniform(1.0, 9.0)), 1)),
    (0.20, "retrieval.top_k", lambda r: int(r.choice([1, 2, 5]))),
    (0.20, "guidance.offer_human_after_failures", lambda r: int(r.choice([1, 3]))),
    (0.10, "guidance.ask_if_resolved", lambda r: False),
    (0.10, "safety.injection_filter", lambda r: False),
    (0.08, "procedures.refund", lambda r: "v2"),
    (0.08, "procedures.refund", lambda r: "v3"),
]


def candidates(n: int, seed: int, base: Release) -> list[Release]:
    rng = np.random.default_rng(seed)
    out: list[Release] = []
    seen = {base.fingerprint}
    while len(out) < n:
        cfg = copy.deepcopy(base.cfg)
        k = int(rng.integers(1, 4))
        p = np.array([x[0] for x in KNOBS])
        picks = rng.choice(len(KNOBS), size=k, replace=False, p=p / p.sum())
        changed = []
        for i in picks:
            _, key, f = KNOBS[i]
            sec, name = key.split(".")
            v = f(rng)
            if cfg[sec][name] != v:
                cfg[sec][name] = v
                changed.append(f"{key}={v}")
        r = from_dict({"id": f"cand-{seed}-{len(out):02d}", "description": ", ".join(changed), **cfg})
        if not changed or r.fingerprint in seen:
            continue
        seen.add(r.fingerprint)
        out.append(r)
    return out


@dataclass
class Truth:
    d_resolved: float
    d_hallucinated: float
    unsafe: int
    cost_ratio: float
    d_handled: float

    @property
    def good(self) -> bool:
        return self.d_resolved >= 0.005 and self.d_hallucinated <= 0.005 and self.unsafe == 0 and self.cost_ratio <= 1.3

    @property
    def harmful(self) -> bool:
        return self.d_resolved <= -0.005 or self.d_hallucinated > 0.005 or self.unsafe > 0


@dataclass
class Study:
    p: SimPlatform = field(default_factory=SimPlatform)
    truth_n: int = 8000
    backtest_n: int = 1000
    labels_n: int = 150
    seed: int = 2026
    base_id: str = "r2-personalised"  # production after personalisation shipped: next quarter's starting point

    def __post_init__(self) -> None:
        self.base = load_release(self.base_id)
        self.truth_specs = make_specs(self.p.e.world, self.truth_n, self.seed + 1, b_share=self.p.b_share, day0=200, prefix="truth")
        self._base_truth = frame(self.p.run(self.base, self.truth_specs, 5))

    def truth(self, c: Release) -> Truth:
        a = self._base_truth
        b = frame(self.p.run(c, self.truth_specs, 5))
        return Truth(
            float(b.true_resolved.mean() - a.true_resolved.mean()),
            float(b.true_hallucinated.mean() - a.true_hallucinated.mean()),
            int(b.true_unsafe.sum()),
            float(b.cost_eur.mean() / a.cost_eur.mean()),
            float(b.true_handled.mean() - a.true_handled.mean()),
        )

    def decide(self, c: Release, k: int) -> dict[str, Any]:
        p, base = self.p, self.base
        seed = self.seed + 10 * k
        # P0: a person reads 20 replayed conversations of each release
        specs20 = p.replay_set(20, seed)
        A20, B20 = p.run(base, specs20, seed), p.run(c, specs20, seed)
        la, lb = human_review.labels(A20, seed), human_review.labels(B20, seed + 1)
        p0 = bool(lb.resolved.sum() > la.resolved.sum() and lb.hallucinated.sum() <= la.hallucinated.sum())
        # P2 and P3 are the release review (P2 stops before live traffic); P1 reads the same backtest
        rv = review(p, base, c, seed, day0=300 + 40 * k)
        p2 = rv.stopped_at not in ("static", "suites", "backtest")
        p3 = rv.shipped
        # P4: what P2 passes goes straight to the staged rollout; no A/B test
        p4, ro4 = False, None
        if p2:
            ro4 = ship.rollout(p, base, c, 300 + 40 * k, seed + 7)
            p4 = ro4.shipped
        bt = rv.backtest or ship.run_backtest(p, base, c, self.backtest_n, self.labels_n, seed)
        m = bt.metrics
        p1 = m["judged_resolution"].diff > 0 and m["judged_hallucination"].diff <= 0.005
        return {
            "P0 read 20": p0,
            "P1 judges": bool(p1),
            "P2 calibrated": p2,
            "P3 + A/B and rollout": p3,
            "P4 backtest and rollout": p4,
            "rollout_without_ab": ro4.as_dict() if ro4 else None,
            "review": rv.as_dict(),
            "stopped_at": rv.stopped_at,
            "reasons": rv.reasons,
            "eval_cost_eur": {
                "P0 read 20": 40 * 2.5,
                "P1 judges": bt.eval_cost_eur - 2 * bt.n_labels * 2.5,
                "P2 calibrated": rv.eval_cost_eur,
            },
            "ab_days": rv.ab.plan.days if rv.ab else 0,
        }


POLICIES = ["P0 read 20", "P1 judges", "P2 calibrated", "P3 + A/B and rollout", "P4 backtest and rollout"]


def run(cands: list[Release], study: Study | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    st = study or Study()
    rows, details = [], []
    for k, c in enumerate(cands):
        t = st.truth(c)
        d = st.decide(c, k)
        rows.append(
            {
                "candidate": c.id,
                "change": c.description,
                "true_d_resolved": round(t.d_resolved, 4),
                "true_d_hallucinated": round(t.d_hallucinated, 4),
                "true_unsafe": t.unsafe,
                "true_cost_ratio": round(t.cost_ratio, 3),
                "truly_good": t.good,
                "truly_harmful": t.harmful,
                **{pol: d[pol] for pol in POLICIES},
                "stopped_at": d["stopped_at"] or "",
                "reasons": "; ".join(d["reasons"]),
                "ab_days": d["ab_days"],
            }
        )
        details.append(
            {"candidate": c.id, "change": c.description, "truth": t.__dict__, **{k2: v for k2, v in d.items() if k2 not in POLICIES}}
        )
    return pd.DataFrame(rows), details


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Per policy: what it shipped, and how often that was the wrong call."""
    out = []
    for pol in POLICIES:
        s = df[pol].astype(bool)
        out.append(
            {
                "policy": pol,
                "shipped": int(s.sum()),
                "good_shipped": int((s & df.truly_good).sum()),
                "harmful_shipped": int((s & df.truly_harmful).sum()),
                "unsafe_shipped": int((s & (df.true_unsafe > 0)).sum()),
                "neutral_shipped": int((s & ~df.truly_good & ~df.truly_harmful).sum()),
                "good_missed": int((~s & df.truly_good).sum()),
                "false_ship_rate": round(float((s & df.truly_harmful).sum() / max(s.sum(), 1)), 3),
                "true_resolution_gain_shipped_pp": round(100 * float(df.loc[s, "true_d_resolved"].sum()), 2),
            }
        )
    return pd.DataFrame(out)
