"""A Claude judge for the panel: reads the redacted conversation and the help-centre article it
answered from, and scores resolution and hallucination. Used when ARC_JUDGE=claude and an API key
is set (`pip install .[llm]`); the offline judges are the default so everything runs without keys.

Its scores go through the same calibration as the others (human labels on a sample, PPI): an LLM
judge is a cheap, biased measurement, not ground truth.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import numpy as np

from arc.agent.safety import redact
from arc.evals.judges import Scores
from arc.knowledge import load as load_kb
from arc.types import Outcome

RUBRIC = """You review conversations between a software company's support agent and a customer.
The customer is on the {plan} plan. Help-centre text the agent answered from, if any:
<article>
{article}
</article>
<conversation>
{conversation}
</conversation>
Answer with JSON only: {{"resolved": p, "hallucinated": q}} where p is the probability that the
customer's need was met by the agent, and q is the probability that the agent told the customer
something false for them (for example a limit or price of a different plan, or an answer the help
centre does not support)."""

JSON = re.compile(r"\{.*\}", re.S)


class ClaudeJudge:
    name = "claude"

    def __init__(self, client: Any = None, model: str | None = None, max_tokens: int = 60):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model or os.environ.get("ARC_JUDGE_MODEL", "claude-haiku-5-5")
        self.max_tokens = max_tokens
        self.kb = load_kb()

    def prompt(self, o: Outcome, plan: str) -> str:
        arts = [e.get("article") for t in o.transcript if t["role"] == "agent" for e in t.get("events", []) if e.get("type") == "answer"]
        a = self.kb.get(arts[-1]) if arts else None
        art = "\n".join([a.body] + [f"{p.title()} plan: {t}" for p, t in a.sections.items()]) if a else "(none)"
        conv = "\n".join(f"{t['role']}: {redact(t['text'])}" for t in o.transcript)
        return RUBRIC.format(plan=plan, article=art[:4000], conversation=conv[:6000])

    def _one(self, o: Outcome, plan: str) -> tuple[float, float]:
        msg = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, messages=[{"role": "user", "content": self.prompt(o, plan)}]
        )
        text = "".join(getattr(b, "text", "") for b in msg.content)
        m = JSON.search(text)
        if not m:
            return np.nan, np.nan
        try:
            d = json.loads(m.group(0))
            return float(np.clip(d["resolved"], 0, 1)), float(np.clip(d["hallucinated"], 0, 1))
        except (ValueError, KeyError, TypeError):
            return np.nan, np.nan

    def score(self, outs: list[Outcome], plans: list[str]) -> Scores:
        r = np.array([self._one(o, p) for o, p in zip(outs, plans, strict=True)], dtype=float).reshape(-1, 2)
        # an unreadable reply scores as the judge's own average rather than poisoning the mean
        for j in (0, 1):
            col = r[:, j]
            col[np.isnan(col)] = np.nanmean(col) if np.isfinite(col).any() else 0.5
        return Scores(r[:, 0], r[:, 1])
