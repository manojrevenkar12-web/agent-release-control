"""Production drill: two weeks of traffic with incidents injected (config/incidents.yaml), the same
two weeks without them, and a week before for the baselines. Grades the alerts: was each incident
detected, by which alert, how many minutes after it started; and how many alerts fired when nothing
was wrong."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from arc.agent.provider import Incident
from arc.agent.release import load as load_release
from arc.config import load
from arc.ops import monitor
from arc.platform import SimPlatform
from arc.runner import frame


@dataclass
class DrillResult:
    days: int
    conversations: int
    incidents: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    false_alarms_with_incidents: int = 0
    false_alarms_clean_run: int = 0
    clean_alerts: list[dict[str, Any]] = field(default_factory=list)
    slo: dict[str, Any] = field(default_factory=dict)
    slo_clean: dict[str, Any] = field(default_factory=dict)
    baseline: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _observable(df: pd.DataFrame) -> pd.DataFrame:
    return df[[c for c in df.columns if not c.startswith("true_")]]


def run(p: SimPlatform | None = None, cfg: dict[str, Any] | None = None, seed: int = 31) -> DrillResult:
    p = p or SimPlatform()
    c = cfg or load("incidents")
    slo = load("slo")
    day0, days = c["day0"], c["days"]
    base_rel = load_release(c["release"])
    warm = _observable(
        frame(p.run(base_rel, p.traffic(slo["quality"]["baseline_days"], day0 - slo["quality"]["baseline_days"], seed), seed))
    )
    base = monitor.Baseline.of(warm)
    specs = p.traffic(days, day0, seed + 1)
    windows = []
    provider_incidents = []
    for inc in c["incidents"]:
        a = (day0 + inc["day"]) * 1440 + inc["start"]
        b = a + inc["minutes"]
        windows.append((inc, a, b))
        if "effect" in inc:
            provider_incidents.append((a, b, Incident(**inc["effect"])))
    # config pushes: a different release serves the conversations in its window
    pushed = [(a, b, load_release(inc["release"])) for inc, a, b in windows if "release" in inc]

    def which(s: Any) -> int:
        t = s.day * 1440 + s.minute
        return next((k for k, (a, b, _) in enumerate(pushed) if a <= t < b), -1)

    groups: dict[int, list[Any]] = {}
    for s in specs:
        groups.setdefault(which(s), []).append(s)
    outs = []
    for k, ss in groups.items():
        rel = base_rel if k < 0 else pushed[k][2]
        outs += p.run(rel, ss, seed + 2, provider_incidents)
    df = _observable(frame(outs))
    clean = _observable(frame(p.run(base_rel, specs, seed + 2)))
    t0, t1 = day0 * 1440, (day0 + days) * 1440 - 1
    al = monitor.alerts(df, base, t0, t1)
    al_clean = monitor.alerts(clean, base, t0, t1)
    grace = slo["grace_min"]
    res = DrillResult(days, len(df))
    used = set()
    for inc, a, b in windows:
        hits = [x for x in al if a <= x.t <= b + grace]
        used |= {id(x) for x in hits}
        first = min(hits, key=lambda x: x.t) if hits else None
        inside = df[(df.day * 1440 + df.minute >= a) & (df.day * 1440 + df.minute < b)]
        res.incidents.append(
            {
                "name": inc["name"],
                "start": f"day {inc['day']} {inc['start'] // 60:02d}:{inc['start'] % 60:02d}",
                "minutes": inc["minutes"],
                "conversations_affected": len(inside),
                "resolution_during": round(float(inside.resolved_obs.mean()), 3) if len(inside) else None,
                "detected": first is not None,
                "minutes_to_detect": (first.t - a) if first else None,
                "first_alert": f"{first.severity}: {first.name}" if first else None,
                "alerts": sorted({f"{x.severity}: {x.name}" for x in hits}),
            }
        )
    res.alerts = [{**x.as_dict(), "caused_by_incident": id(x) in used} for x in al]
    res.false_alarms_with_incidents = sum(1 for x in al if id(x) not in used)
    res.false_alarms_clean_run = len(al_clean)
    res.clean_alerts = [x.as_dict() for x in al_clean]
    res.slo = monitor.slo_report(df)
    res.slo_clean = monitor.slo_report(clean)
    res.baseline = {"resolution": round(base.resolution, 4), "cost_per_conversation_eur": round(base.cost_per_conversation, 5)}
    return res
