"""Judges: read a finished conversation (transcript, event log, account attributes) and score it.

They never see the truth. Two families stand in for LLM judges from different model families:

- `RubricJudge`: a fixed rubric (did the agent give an answer or a result the customer did not push
  back on). Cheap, lenient, blind to wrong plan details and to answers to questions we cannot answer.
- `LearnedJudge`: a model trained on conversations that support specialists labelled. Better, but it
  learned on the production release's conversations, so it can be wrong in new ways on a release
  that behaves differently.

With ARC_LLM=claude, `arc.evals.claude_judge` adds a real LLM judge with the same interface.
Judges are combined (mean) and their disagreement routes conversations to human review; human
labels on a sample correct the judges' bias (prediction-powered inference, arc.evals.ppi).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from arc.config import MODELS
from arc.types import Outcome

KINDS = ["answer", "result", "decline", "handoff", "refuse", "clarify", "verify", "ask_slot", "closing", "error"]
PLAN_WORDS = {
    "free": re.compile(r"\b(on free|free plan|free workspaces)\b", re.I),
    "pro": re.compile(r"\b(on pro|pro plan|pro workspaces)\b", re.I),
    "business": re.compile(r"\b(on business|business plan|business workspaces)\b", re.I),
}
NEG = re.compile(r"^\s*(no\b|not what|that's not|wrong)", re.I)
HUMAN = re.compile(r"\b(human|real person|agent)\b", re.I)
THANKS = re.compile(r"\b(solved|perfect|thank|great|what i needed)\b", re.I)


def features(o: Outcome, plan: str) -> dict[str, float]:
    """What a reader of the conversation can see. No truth fields are used here."""
    agent = [t for t in o.transcript if t["role"] == "agent"]
    cust = [t for t in o.transcript if t["role"] == "customer"]
    last = agent[-1] if agent else {"kind": "none", "events": [], "text": ""}
    after_last = [t for t in o.transcript[o.transcript.index(last) + 1 :]] if agent else []
    events = [e for t in agent for e in t.get("events", [])]
    ans = [e for e in events if e["type"] == "answer"]
    f: dict[str, float] = {f"last_{k}": float(last["kind"] == k) for k in KINDS}
    texts = " ".join(t["text"] for t in agent)
    mentioned = [p for p, rx in PLAN_WORDS.items() if rx.search(texts)]
    f.update(
        {
            "answers": len(ans),
            "answer_conf": float(np.mean([e.get("confidence", 0) for e in ans])) if ans else 0.0,
            "answer_support": float(np.mean([e.get("support", 0) for e in ans])) if ans else 0.0,
            "customer_msgs": len(cust),
            "negations": sum(bool(NEG.search(t["text"])) for t in cust),
            "asked_human": float(any(HUMAN.search(t["text"]) for t in cust[1:])),
            "thanked": float(any(THANKS.search(t["text"]) for t in after_last)),
            "confirmed": float(o.confirmed),
            "handed_off": float(o.handed_off),
            "plan_mismatch": float(bool(mentioned) and plan not in mentioned),
            "plan_match": float(plan in mentioned),
            "verified": float(any(e["type"] == "verify" for e in events)),
            "result_refunded": float(any(e.get("outcome") == "refunded" for e in events)),
            "result_not_eligible": float(any(e.get("outcome") == "not_eligible" for e in events)),
            "declined": float(any(e["type"] == "decline" for e in events)),
            "clarified": float(any(e["type"] == "clarify" for e in events)),
            "injection": float(any(e["type"] == "injection_detected" for e in events)),
            "turns": float(o.turns),
            "text_len": len(texts) / 500,
        }
    )
    return f


@dataclass
class Scores:
    resolved: np.ndarray
    hallucinated: np.ndarray


class RubricJudge:
    name = "rubric"

    def score(self, outs: list[Outcome], plans: list[str]) -> Scores:
        r, h = [], []
        for o, p in zip(outs, plans, strict=True):
            f = features(o, p)
            ok = (f["last_answer"] or f["last_result"] or f["last_closing"]) and not f["asked_human"]
            r.append(0.85 if ok else 0.1)
            h.append(0.3 if f["answers"] and f["answer_support"] < 4 else 0.02)
        return Scores(np.array(r), np.array(h))


@dataclass
class LearnedJudge:
    columns: list[str]
    res: LogisticRegression
    hal: LogisticRegression
    trained_on: dict[str, Any]
    name: str = "learned"

    @classmethod
    def fit(cls, outs: list[Outcome], plans: list[str], labels: pd.DataFrame, trained_on: dict[str, Any]) -> LearnedJudge:
        X = pd.DataFrame([features(o, p) for o, p in zip(outs, plans, strict=True)])
        res = LogisticRegression(C=1.0, max_iter=2000).fit(X, labels.resolved.to_numpy())
        hal = LogisticRegression(C=1.0, max_iter=2000).fit(X, labels.hallucinated.to_numpy())
        return cls(list(X.columns), res, hal, trained_on)

    def score(self, outs: list[Outcome], plans: list[str]) -> Scores:
        X = pd.DataFrame([features(o, p) for o, p in zip(outs, plans, strict=True)])[self.columns]
        return Scores(self.res.predict_proba(X)[:, 1], self.hal.predict_proba(X)[:, 1])

    def save(self, path: Path = MODELS / "judge.joblib") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)

    @staticmethod
    def load(path: Path = MODELS / "judge.joblib") -> LearnedJudge:
        return joblib.load(path)


class Panel:
    """Judges together: mean score, and disagreement between them."""

    def __init__(self, judges: list[Any]):
        self.judges = judges

    def score(self, outs: list[Outcome], plans: list[str]) -> tuple[Scores, np.ndarray]:
        s = [j.score(outs, plans) for j in self.judges]
        res = np.mean([x.resolved for x in s], axis=0)
        hal = np.mean([x.hallucinated for x in s], axis=0)
        disagree = np.max([x.resolved for x in s], axis=0) - np.min([x.resolved for x in s], axis=0)
        return Scores(res, hal), disagree
