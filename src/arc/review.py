"""A release review: everything a candidate goes through before it replaces production, in order,
stopping at the first stage it fails.

1. Static checks: settings in range, procedures exist, no write path skips verification.
2. Eval suites: targeted simulations; blocking suites stop the release.
3. Backtest: the same replayed conversations through production and the candidate; judge scores
   corrected with human labels (PPI); deterministic checks, cost and latency.
4. A/B test on live traffic, sized by a power analysis, randomised by account.
5. Staged rollout: dark, 1%, 10%, 50%, 100%, with health checks and automatic rollback.

Uses only the platform interface: nothing here can read the simulator's truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arc import ship
from arc.agent.release import Release
from arc.config import load
from arc.evals.backtest import BacktestResult
from arc.evals.lint import lint
from arc.evals.suites import SuiteResult
from arc.experiment.ab import ABResult
from arc.platform import SimPlatform


@dataclass
class Review:
    candidate: str
    baseline: str
    description: str
    changes: dict[str, Any]
    decision: str = "ship"
    stopped_at: str | None = None
    reasons: list[str] = field(default_factory=list)
    static: list[str] = field(default_factory=list)
    suites: list[SuiteResult] = field(default_factory=list)
    backtest: BacktestResult | None = None
    ab: ABResult | None = None
    rollout: ship.Rollout | None = None
    eval_cost_eur: float = 0.0
    calendar_days: int = 0

    @property
    def shipped(self) -> bool:
        return self.decision == "ship"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "baseline": self.baseline,
            "description": self.description,
            "changes": {k: {"from": a, "to": b} for k, (a, b) in self.changes.items()},
            "decision": self.decision,
            "stopped_at": self.stopped_at,
            "reasons": self.reasons,
            "static": self.static,
            "suites": [s.as_dict() for s in self.suites],
            "backtest": self.backtest.as_dict() if self.backtest else None,
            "ab": self.ab.as_dict() if self.ab else None,
            "rollout": self.rollout.as_dict() if self.rollout else None,
            "eval_cost_eur": round(self.eval_cost_eur, 2),
            "calendar_days": self.calendar_days,
        }


def offline_reasons(bt: BacktestResult, cfg: dict[str, Any] | None = None) -> list[str]:
    g = (cfg or load("review"))["offline_gate"]
    m = bt.metrics
    out = []
    if "calibrated_resolution" in m:
        if m["calibrated_resolution"].lo <= g["calibrated_resolution_lower_bound_min"]:
            out.append(
                f"resolution gain not established (95% interval {m['calibrated_resolution'].lo:+.3f} to {m['calibrated_resolution'].hi:+.3f})"
            )
        if m["calibrated_hallucination"].hi >= g["calibrated_hallucination_upper_bound_max"]:
            out.append(f"hallucination may rise (upper bound {m['calibrated_hallucination'].hi:+.3f})")
    if m["writes_without_verification"].candidate * bt.n > g["writes_without_verification_max"]:
        out.append(f"{round(m['writes_without_verification'].candidate * bt.n)} writes without verification in the backtest")
    if m["cost_per_conversation"].candidate > g["cost_max_ratio"] * m["cost_per_conversation"].baseline:
        out.append(f"cost per conversation x{m['cost_per_conversation'].candidate / m['cost_per_conversation'].baseline:.2f}")
    if m["latency_p95_s"].candidate > g["latency_p95_max_ratio"] * m["latency_p95_s"].baseline:
        out.append(f"p95 latency x{m['latency_p95_s'].candidate / m['latency_p95_s'].baseline:.2f}")
    return out


def review(p: SimPlatform, base: Release, cand: Release, seed: int = 0, day0: int = 300, online: bool | None = None) -> Review:
    c = load("review")
    online = c["online"] if online is None else online
    r = Review(cand.id, base.id, cand.description, cand.diff(base))
    if not r.changes:
        r.decision, r.stopped_at, r.reasons = "do not ship", "static", ["no change from the baseline"]
        return r
    r.static = lint(cand)
    if r.static:
        r.decision, r.stopped_at, r.reasons = "do not ship", "static", r.static
        return r
    r.suites = ship.suites(p, cand, seed)
    blocked = [s for s in r.suites if s.blocking and not s.ok]
    if blocked:
        r.decision, r.stopped_at = "do not ship", "suites"
        r.reasons = [f"{s.suite} suite: {s.pass_rate:.1%} passed, needs {s.min_pass_rate:.0%}" for s in blocked]
        return r
    r.backtest = ship.run_backtest(p, base, cand, c["backtest"]["conversations"], c["backtest"]["human_labels"], seed)
    r.eval_cost_eur = r.backtest.eval_cost_eur
    reasons = offline_reasons(r.backtest, c)
    if reasons:
        r.decision, r.stopped_at, r.reasons = "do not ship", "backtest", reasons
        return r
    if not online:
        r.decision = "ready for A/B test"
        return r
    r.ab = ship.run_ab(p, base, cand, day0, seed)
    r.calendar_days += r.ab.plan.days
    if r.ab.decision != "ship":
        r.decision, r.stopped_at, r.reasons = "do not ship", "A/B test", r.ab.reasons or [r.ab.decision]
        return r
    r.rollout = ship.rollout(p, base, cand, day0 + r.ab.plan.days, seed)
    r.calendar_days += sum(s["days"] for s in r.rollout.stages)
    if not r.rollout.shipped:
        r.decision, r.stopped_at = "rolled back", f"rollout {r.rollout.stopped_at}"
        r.reasons = r.rollout.reasons
    return r


def markdown(r: Review) -> str:
    lines = [
        f"# Release review: {r.candidate}",
        "",
        f"{r.description}",
        "",
        f"**Decision: {r.decision}**" + (f" (stopped at {r.stopped_at})" if r.stopped_at else ""),
        "",
    ]
    if r.reasons:
        lines += [f"- {x}" for x in r.reasons] + [""]
    lines += ["## Changes from " + r.baseline, "", "| Setting | From | To |", "|---|---|---|"]
    lines += [f"| `{k}` | {a} | {b} |" for k, (a, b) in r.changes.items()] + [""]
    if r.suites:
        lines += ["## Eval suites", "", "| Suite | Blocking | Passed | Needs |", "|---|---|---|---|"]
        lines += [f"| {s.suite} | {'yes' if s.blocking else 'no'} | {s.pass_rate:.1%} | {s.min_pass_rate:.0%} |" for s in r.suites] + [""]
    if r.backtest:
        b = r.backtest
        lines += [
            f"## Backtest ({b.n} replayed conversations, {b.n_labels} human-labelled, eval cost €{b.eval_cost_eur:.0f})",
            "",
            "| Metric | Production | Candidate | Change | 95% interval | Method |",
            "|---|---|---|---|---|---|",
        ]
        for m in b.metrics.values():
            lines.append(f"| {m.name} | {m.baseline:.4f} | {m.candidate:.4f} | {m.diff:+.4f} | {m.lo:+.4f} to {m.hi:+.4f} | {m.method} |")
        lines.append("")
    if r.ab:
        a = r.ab
        lines += [
            f"## A/B test ({a.plan.days} days, {a.conversations['control'] + a.conversations['treatment']:,} conversations, alpha {a.plan.alpha})",
            "",
            f"Primary ({a.primary.metric}): {a.primary.control:.4f} → {a.primary.treatment:.4f}, {a.primary.diff:+.4f} ({a.primary.lo:+.4f} to {a.primary.hi:+.4f}), p = {a.primary.p:.2g}. Decision: {a.decision}.",
            "",
        ]
        lines += ["| Guardrail | Control | Treatment | Change |", "|---|---|---|---|"]
        lines += [f"| {k} | {e.control:.4f} | {e.treatment:.4f} | {e.diff:+.4f} |" for k, e in a.guardrails.items()] + [""]
    if r.rollout:
        lines += ["## Rollout", "", "| Stage | Days | Treated | Failed checks |", "|---|---|---|---|"]
        lines += [f"| {s['stage']} | {s['days']} | {s['treated']:,} | {', '.join(s['failed']) or 'none'} |" for s in r.rollout.stages] + [
            ""
        ]
    return "\n".join(lines)
