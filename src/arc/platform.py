"""What the shipping process can use: run a release on conversations, get live traffic, ask people
to review conversations, look up account attributes. Here it is backed by the simulator; in
production, by replay infrastructure, the live router and the review queue. Shipping code only
talks to this interface, so it cannot read the simulator's truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from arc.agent.provider import Incident
from arc.agent.release import Release
from arc.evals.judges import LearnedJudge, Panel, RubricJudge
from arc.runner import Env, env, simulate
from arc.sim import review
from arc.sim.world import Spec, make_specs
from arc.systems import Systems
from arc.types import Outcome


@dataclass
class SimPlatform:
    e: Env = field(default_factory=env)
    b_share: float = 0.3
    label_seed: int = 0

    @property
    def systems(self) -> Systems:
        return self.e.world.systems

    def plans(self, outs: list[Outcome]) -> list[str]:
        p = self.e.world.systems.plan
        return [str(p[o.account]) for o in outs]

    def run(
        self, release: Release, specs: list[Spec], seed: int = 0, incidents: list[tuple[int, int, Incident]] | None = None
    ) -> list[Outcome]:
        return simulate(release, specs, self.e, seed, incidents)

    def replay_set(self, n: int, seed: int) -> list[Spec]:
        """Past conversations to replay: openings and customers from recent traffic."""
        return make_specs(self.e.world, n, seed, b_share=self.b_share, day0=60, prefix="bt")

    def traffic(self, days: int, day0: int, seed: int, per_day: int | None = None) -> list[Spec]:
        per_day = per_day or self.e.world.cfg["traffic"]["per_day"]
        wf = self.e.world.cfg["traffic"]["weekday_factor"]
        n = sum(max(1, int(per_day * wf[(day0 + d) % 7])) for d in range(days))
        return make_specs(self.e.world, n, seed, b_share=self.b_share, day0=day0, per_day=per_day, prefix=f"live{day0}-")

    def suite_specs(self, scenario: dict, seed: int) -> list[Spec]:
        return make_specs(
            self.e.world,
            scenario["n"],
            seed,
            b_share=self.b_share,
            only=[scenario["intent"]],
            injection_rate=1.0 if scenario.get("injection") else 0.0,
            impostor_rate=1.0 if scenario.get("impostor") else 0.0,
            vague_rate=0.0,
            prefix=f"suite-{scenario['intent']}-",
        )

    def label(self, outs: list[Outcome]) -> pd.DataFrame:
        """Human review of these conversations."""
        self.label_seed += 1
        return review.labels(outs, self.label_seed)

    def panel(self) -> Panel:
        judges: list[Any] = [LearnedJudge.load(), RubricJudge()]
        if os.environ.get("ARC_JUDGE") == "claude":
            from arc.evals.claude_judge import ClaudeJudge

            judges.append(ClaudeJudge())
        return Panel(judges)

    def monitor_scores(self, outs: list[Outcome], rate: float, seed: int) -> np.ndarray:
        """Hallucination scores from the monitor judge on a random sample; NaN elsewhere."""
        rng = np.random.default_rng(seed)
        pick = rng.random(len(outs)) < rate
        out = np.full(len(outs), np.nan)
        idx = np.flatnonzero(pick)
        if len(idx):
            sub = [outs[i] for i in idx]
            out[idx] = LearnedJudge.load().score(sub, self.plans(sub)).hallucinated
        return out
