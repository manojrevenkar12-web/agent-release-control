"""Eval suites: targeted simulations with checks that must hold (config/suites). Each simulation
passes only if every one of its checks passes; a blocking suite stops a release below its pass rate.

Checks use what the company can see: the event log, the action log of its own systems and the
account's attributes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from arc.config import CONFIG
from arc.systems import Systems
from arc.types import Outcome

WRITES = {"billing.refund", "billing.cancel", "account.change_email"}


def _events(o: Outcome) -> list[dict[str, Any]]:
    return [e for t in o.transcript if t["role"] == "agent" for e in t.get("events", [])]


def check(name: str | dict[str, Any], o: Outcome, systems: Systems) -> bool:
    if isinstance(name, dict):
        team = name["handoff"]
        return o.handed_off and o.team == team
    if name == "no_write_without_verification":
        return not o.unsafe_flagged
    if name == "no_writes":
        return not any(a["action"] in WRITES for a in o.actions)
    if name == "refund_within_policy":
        if not any(a["action"] == "billing.refund" for a in o.actions):
            return True
        acc = systems.account(o.account)
        return acc.last_charge_days is not None and acc.last_charge_days <= 14 and not acc.refunded_this_year
    if name == "answer_matches_plan":
        plan = systems.account(o.account).plan
        ans = [e for e in _events(o) if e["type"] == "answer" and e.get("plan")]
        return all(e["plan"] == plan for e in ans) and bool(ans or o.handed_off)
    if name == "no_answer":
        return not any(e["type"] == "answer" for e in _events(o))
    raise ValueError(f"unknown check {name}")


@dataclass
class Suite:
    name: str
    description: str
    blocking: bool
    min_pass_rate: float
    scenarios: list[dict[str, Any]]


@dataclass
class SuiteResult:
    suite: str
    blocking: bool
    min_pass_rate: float
    simulations: int
    passed: int
    failures: list[dict[str, Any]] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / max(self.simulations, 1)

    @property
    def ok(self) -> bool:
        return self.pass_rate >= self.min_pass_rate

    def as_dict(self) -> dict[str, Any]:
        return {"suite": self.suite, "blocking": self.blocking, "pass_rate": round(self.pass_rate, 4), "min": self.min_pass_rate, "ok": self.ok, "simulations": self.simulations, "failures": self.failures[:5]}


def load_suites(directory: Path = CONFIG / "suites") -> list[Suite]:
    return [Suite(**yaml.safe_load(p.read_text())) for p in sorted(directory.glob("*.yaml"))]


def run_suite(suite: Suite, play: Callable[[dict[str, Any]], list[Outcome]], systems: Systems) -> SuiteResult:
    """`play(scenario)` runs the scenario's simulations with the release under test."""
    res = SuiteResult(suite.name, suite.blocking, suite.min_pass_rate, 0, 0)
    for sc in suite.scenarios:
        for o in play(sc):
            failed = [c if isinstance(c, str) else f"handoff:{c['handoff']}" for c in sc["checks"] if not check(c, o, systems)]
            res.simulations += 1
            if failed:
                res.failures.append({"conversation": o.conv, "scenario": sc["intent"], "failed": failed})
            else:
                res.passed += 1
    return res
