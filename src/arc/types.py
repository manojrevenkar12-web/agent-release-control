"""What passes between the agent, the customer and the evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KINDS = ("clarify", "ask_slot", "verify", "answer", "result", "decline", "handoff", "refuse", "closing", "error")


@dataclass
class Call:
    """One model call: what it cost and how long it took."""

    purpose: str
    tier: str
    tokens_in: int
    tokens_out: int
    cost_eur: float
    latency_s: float
    ok: bool = True


@dataclass
class AgentTurn:
    text: str
    kind: str
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    asks_if_resolved: bool = False
    calls: list[Call] = field(default_factory=list)

    @property
    def cost_eur(self) -> float:
        return sum(c.cost_eur for c in self.calls)

    @property
    def latency_s(self) -> float:
        return sum(c.latency_s for c in self.calls) + 0.05


@dataclass
class Outcome:
    """How a conversation ended. `truth` is only known to the simulator; the rest is observable."""

    conv: str
    release: str
    intent_true: str
    kind_true: str
    day: int
    minute: int
    account: int
    # observable
    confirmed: bool = False  # hard resolution: the customer said it solved their problem
    handed_off: bool = False
    team: str | None = None
    abandoned: bool = False  # left without confirming or being handed off
    reopened: bool = False  # came back about the same thing within 3 days
    csat: int | None = None
    turns: int = 0
    cost_eur: float = 0.0
    latency_s: list[float] = field(default_factory=list)
    errors: int = 0
    unsafe_flagged: bool = False  # the action log check (verification before every write) failed
    # truth
    resolved: bool = False  # the customer's need was met by the agent
    handled_correctly: bool = False  # resolved, or correctly escalated / declined / refused
    hallucinated: bool = False  # told the customer something false for them
    unsafe: bool = False  # did something it must not do
    transcript: list[dict[str, Any]] = field(default_factory=list)

    @property
    def soft_resolved(self) -> bool:
        return self.abandoned and not self.reopened

    @property
    def fin_resolved(self) -> bool:
        """Resolution as a support team can measure it: hard or soft."""
        return self.confirmed or self.soft_resolved
