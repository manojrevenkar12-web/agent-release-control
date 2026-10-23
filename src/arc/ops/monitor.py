"""Alerts on the agent in production, from observable data only.

- Availability and latency SLOs with multi-window burn-rate alerts (config/slo.yaml).
- Resolution watched with a one-sided Bernoulli CUSUM against last week's rate.
- AI cost per conversation over the last hour against last week's.

Input is one row per conversation with `t` (minute on the absolute timeline), `error_conv`,
`latency_max_s`, `resolved_obs` and `cost_eur`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from arc.config import load


@dataclass
class Alert:
    t: int
    severity: str
    name: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Baseline:
    resolution: float
    cost_per_conversation: float

    @classmethod
    def of(cls, df: pd.DataFrame) -> Baseline:
        return cls(float(df.resolved_obs.mean()), float(df.cost_eur.mean()))


def _per_minute(df: pd.DataFrame, t0: int, t1: int, col: str) -> np.ndarray:
    out = np.zeros(t1 - t0 + 1)
    np.add.at(out, df.t.to_numpy() - t0, df[col].to_numpy(float))
    return out


def _window(cum: np.ndarray, i: int, w: int) -> float:
    return float(cum[i + 1] - cum[max(0, i + 1 - w)])


def burn_rate_alerts(df: pd.DataFrame, t0: int, t1: int, cfg: dict[str, Any] | None = None, step: int = 5) -> list[Alert]:
    c = cfg or load("slo")
    total = np.concatenate([[0], np.cumsum(_per_minute(df, t0, t1, "one"))])
    out: list[Alert] = []
    for sli, spec in c["slis"].items():
        bad = np.concatenate([[0], np.cumsum(_per_minute(df, t0, t1, f"bad_{sli}"))])
        budget = 1 - spec["target"]
        for rule in c["burn_alerts"]:
            firing = False
            for i in range(0, t1 - t0 + 1, step):
                ok = True
                rates = []
                for w in (rule["long_min"], rule["short_min"]):
                    n = _window(total, i, w)
                    if n < (c["min_events"] if w == rule["long_min"] else 1):
                        ok = False
                        break
                    rates.append(_window(bad, i, w) / n / budget)
                now = ok and all(r > rule["burn"] for r in rates)
                if now and not firing:
                    out.append(
                        Alert(
                            t0 + i,
                            rule["severity"],
                            f"{sli} burn rate",
                            f"{rates[0]:.1f}x budget over {rule['long_min']} min (threshold {rule['burn']}x)",
                        )
                    )
                firing = now
    return out


def cusum_alerts(df: pd.DataFrame, base: Baseline, cfg: dict[str, Any] | None = None) -> list[Alert]:
    q = (cfg or load("slo"))["quality"]
    p0 = min(max(base.resolution, 0.01), 0.99)
    p1 = max(p0 - q["shift"], 0.005)
    up, down = np.log(p1 / p0), np.log((1 - p1) / (1 - p0))
    s, out = 0.0, []
    d = df.sort_values("t")
    for t, x in zip(d.t.to_numpy(), d[q["metric"]].to_numpy(float), strict=True):
        s = max(0.0, s + (up if x else down))
        if s > q["threshold"]:
            out.append(Alert(int(t), q["severity"], "resolution drop", f"CUSUM over {q['threshold']} against a baseline of {p0:.1%}"))
            s = 0.0
    return out


def cost_alerts(df: pd.DataFrame, t0: int, t1: int, base: Baseline, cfg: dict[str, Any] | None = None, step: int = 5) -> list[Alert]:
    c = (cfg or load("slo"))["cost"]
    n = np.concatenate([[0], np.cumsum(_per_minute(df, t0, t1, "one"))])
    eur = np.concatenate([[0], np.cumsum(_per_minute(df, t0, t1, "cost_eur"))])
    out, firing = [], False
    for i in range(0, t1 - t0 + 1, step):
        k = _window(n, i, c["window_min"])
        ratio = _window(eur, i, c["window_min"]) / k / base.cost_per_conversation if k >= c["min_events"] else 0.0
        now = ratio > c["max_ratio"]
        if now and not firing:
            out.append(Alert(t0 + i, c["severity"], "AI cost per conversation", f"{ratio:.2f}x last week's over {c['window_min']} min"))
        firing = now
    return out


def prepare(df: pd.DataFrame, cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    c = cfg or load("slo")
    d = df.copy()
    d["t"] = d.day * 1440 + d.minute
    d["one"] = 1.0
    d["bad_availability"] = d.error_conv.astype(float)
    d["bad_latency"] = (d.latency_max_s > c["slis"]["latency"]["threshold_s"]).astype(float)
    return d


def alerts(df: pd.DataFrame, base: Baseline, t0: int, t1: int, cfg: dict[str, Any] | None = None) -> list[Alert]:
    d = prepare(df, cfg)
    out = burn_rate_alerts(d, t0, t1, cfg) + cusum_alerts(d, base, cfg) + cost_alerts(d, t0, t1, base, cfg)
    return sorted(out, key=lambda a: a.t)


def slo_report(df: pd.DataFrame, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    c = cfg or load("slo")
    d = prepare(df, c)
    out = {}
    for sli, spec in c["slis"].items():
        bad = float(d[f"bad_{sli}"].mean())
        out[sli] = {"target": spec["target"], "achieved": round(1 - bad, 5), "budget_used": round(bad / (1 - spec["target"]), 3)}
    return out
