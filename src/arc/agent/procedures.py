"""Procedures: step-by-step workflows the agent runs for requests that need an action (refunds,
cancellations, account changes). Defined in config/procedures as data, versioned, so a release
pins the version it ships and a change to a procedure goes through the same evaluation as a
prompt or a model change."""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from arc.config import CONFIG

OPS = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}


def evaluate(expr: str, scope: dict[str, Any]) -> Any:
    """A small, safe expression language: names with dots, numbers, comparisons, and/or/not."""

    def ev(n: ast.AST) -> Any:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return not ev(n.operand)
        if isinstance(n, ast.Compare):
            left = ev(n.left)
            for op, right in zip(n.ops, n.comparators, strict=True):
                r = ev(right)
                if not OPS[type(op)](left, r):
                    return False
                left = r
            return True
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            return scope[n.id]
        if isinstance(n, ast.Attribute):
            return ev(n.value)[n.attr]
        raise ValueError(f"not allowed in a procedure condition: {ast.dump(n)}")

    return ev(ast.parse(expr, mode="eval"))


@dataclass
class Procedure:
    name: str
    version: str
    description: str
    steps: list[dict[str, Any]]

    def index(self, step_id: str) -> int:
        return next(i for i, s in enumerate(self.steps) if s["id"] == step_id)

    @property
    def writes_without_verification(self) -> bool:
        """True if some path reaches a write before identity verification (checked statically)."""
        seen_verify = False
        for s in self.steps:
            if s["type"] == "verify_identity":
                seen_verify = True
            if s["type"] == "condition" and not seen_verify:
                return any(self.steps[self.index(t)]["type"] == "action" and self.steps[self.index(t)]["call"] in ("refund", "cancel", "change_email") for t in (s["then"], s["else"]))
            if s["type"] == "action" and s["call"] in ("refund", "cancel", "change_email") and not seen_verify:
                return True
        return False


@lru_cache
def load(name: str, version: str) -> Procedure:
    d = yaml.safe_load((CONFIG / "procedures" / f"{name}.yaml").read_text())
    v = d["versions"][version]
    return Procedure(name, version, v.get("description", ""), v["steps"])


@dataclass
class Run:
    proc: Procedure
    at: int = 0
    scope: dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    waiting: str | None = None  # "code" or a slot name
    attempts: int = 0
