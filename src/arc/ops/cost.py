"""What the router threshold buys: resolution, AI cost and latency for each escalation threshold and
answer tier, on the same conversations. Value per conversation = resolutions x the cost of a human
handling the conversation instead - AI spend, among settings that meet the latency SLO. Chosen from
observable resolution, as a team would; the true resolution is shown next to it to check the
choice."""

from __future__ import annotations

from typing import Any

import pandas as pd

from arc.agent.release import from_dict
from arc.agent.release import load as load_release
from arc.config import load
from arc.platform import SimPlatform
from arc.runner import frame

THRESHOLDS = [0.0, 0.3, 0.45, 0.6, 0.7, 0.8, 0.9, 1.01]


def frontier(p: SimPlatform | None = None, n: int = 3000, seed: int = 41, base_id: str = "r2-personalised") -> pd.DataFrame:
    p = p or SimPlatform()
    base = load_release(base_id)
    human = load("models")["human_handling_eur"]
    lat = load("slo")["slis"]["latency"]
    specs = p.replay_set(n, seed)
    rows: list[dict[str, Any]] = []
    for tier in ("small", "large"):
        for th in THRESHOLDS:
            cfg = {**base.cfg, "models": {**base.cfg["models"], "escalate_below": th, "answer_tier": tier}}
            r = from_dict({"id": f"{base_id}@{th}/{tier}", "description": "", **cfg})
            df = frame(p.run(r, specs, seed))
            rows.append(
                {
                    "escalate_below": th,
                    "answer_tier": tier,
                    "resolution_observed": round(float(df.resolved_obs.mean()), 4),
                    "resolution_true": round(float(df.true_resolved.mean()), 4),
                    "ai_cost_per_conversation_eur": round(float(df.cost_eur.mean()), 5),
                    "latency_p95_s": round(float(df.latency_max_s.quantile(0.95)), 2),
                    "meets_latency_slo": bool((df.latency_max_s <= lat["threshold_s"]).mean() >= lat["target"]),
                    "value_per_conversation_eur": round(float(df.resolved_obs.mean() * human - df.cost_eur.mean()), 4),
                    "value_true_eur": round(float(df.true_resolved.mean() * human - df.cost_eur.mean()), 4),
                }
            )
    out = pd.DataFrame(rows)
    # what one extra resolution costs in AI spend, moving up from the previous threshold
    d_cost = out.groupby("answer_tier").ai_cost_per_conversation_eur.diff()
    d_res = out.groupby("answer_tier").resolution_observed.diff()
    out["eur_per_extra_resolution"] = (d_cost / d_res.where(d_res > 0)).round(3)
    ok = out[out.meets_latency_slo]
    out["best_observed"] = out.index == ok.value_per_conversation_eur.idxmax()
    out["best_true"] = out.index == ok.value_true_eur.idxmax()
    return out
