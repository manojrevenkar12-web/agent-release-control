"""What each release really does: every release on the same conversations, with the simulator's truth
next to what a support team can observe. This is the answer key the shipping process is graded
against; it is not available to the shipping process."""

from __future__ import annotations

from typing import Any

import pandas as pd

from arc.agent.release import Release
from arc.platform import SimPlatform
from arc.runner import frame
from arc.sim.world import make_specs


def compare(releases: list[Release], n: int = 6000, seed: int = 77, p: SimPlatform | None = None) -> pd.DataFrame:
    p = p or SimPlatform()
    specs = make_specs(p.e.world, n, seed, b_share=p.b_share, day0=500, prefix="cmp")
    rows: list[dict[str, Any]] = []
    for r in releases:
        df = frame(p.run(r, specs, seed))
        rows.append(
            {
                "release": r.id,
                "description": r.description,
                "resolution_observed": df.resolved_obs.mean(),
                "confirmed": df.confirmed.mean(),
                "handoff": df.handed_off.mean(),
                "true_resolved": df.true_resolved.mean(),
                "true_handled_correctly": df.true_handled.mean(),
                "true_hallucinated": df.true_hallucinated.mean(),
                "true_unsafe": int(df.true_unsafe.sum()),
                "unsafe_flagged": int(df.unsafe_flagged.sum()),
                "cost_per_conversation_eur": df.cost_eur.mean(),
                "latency_p95_s": df.latency_max_s.quantile(0.95),
                "csat": df.csat.mean(),
            }
        )
    out = pd.DataFrame(rows)
    return out.round({c: 4 for c in out.columns if out[c].dtype.kind == "f"}).round({"cost_per_conversation_eur": 5})
