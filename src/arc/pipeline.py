"""`arc run`: train, compare releases against the truth, review releases, A/A test, the
shipping-process study, the production drill and the cost frontier; then the report and the gate."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from arc import ship
from arc.agent.release import all_releases, heldout, heldout_versions
from arc.agent.release import load as load_release
from arc.config import MODELS, REPORTS, load
from arc.ops import cost, drill
from arc.platform import SimPlatform
from arc.review import Review, markdown, review
from arc.study import process
from arc.study import releases as release_study


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, pd.DataFrame):
        path.write_text(data.to_json(orient="records", indent=1))
    elif isinstance(data, str):
        path.write_text(data)
    else:
        path.write_text(json.dumps(data, indent=1, default=str))


def _log(msg: str) -> None:
    print(f"[arc] {msg}", flush=True)


def run_reviews(names: list[str], p: SimPlatform) -> list[Review]:
    base = load_release("r1-prod")
    out = []
    for k, name in enumerate(names):
        t = time.time()
        r = review(p, base, load_release(name), seed=100 + k, day0=600 + 60 * k)
        _write(REPORTS / "reviews" / f"{name}.json", r.as_dict())
        _write(REPORTS / "reviews" / f"{name}.md", markdown(r))
        _log(f"review {name}: {r.decision}{' at ' + r.stopped_at if r.stopped_at else ''} ({time.time() - t:.0f}s)")
        out.append(r)
    return out


def aa_test(p: SimPlatform) -> dict[str, Any]:
    base = load_release("r1-prod")
    res = ship.run_ab(p, base, base, 1400, 5).as_dict()
    _write(REPORTS / "aa_test.json", res)
    _log(f"A/A test: {res['decision']} (p = {res['primary']['p']:.3f})")
    return res


def study(n: int, truth_n: int, seed: int, p: SimPlatform) -> dict[str, Any]:
    st = process.Study(p, truth_n=truth_n)
    cands = process.candidates(n, seed, st.base)
    df, details = process.run(cands, st)
    sc = process.score(df)
    out = {"candidates": df.to_dict(orient="records"), "score": sc.to_dict(orient="records"), "truth_conversations": truth_n}
    _write(REPORTS / "process_study.json", out)
    _write(REPORTS / "process_study_details.json", details)
    _log("process study:\n" + sc.to_string(index=False))
    return out


def ops(seeds: list[int], frontier_n: int, p: SimPlatform) -> dict[str, Any]:
    runs = [drill.run(p, seed=s).as_dict() for s in seeds]
    fr = cost.frontier(p, frontier_n)
    out = {"drills": runs, "seeds": seeds}
    _write(REPORTS / "ops_drill.json", out)
    _write(REPORTS / "cost_frontier.json", fr)
    for r in runs:
        _log(
            "drill: "
            + ", ".join(f"{i['name']}: {i['minutes_to_detect']} min" for i in r["incidents"])
            + f"; false alarms {r['false_alarms_clean_run']}"
        )
    return out


def run_heldout(p: SimPlatform, version: str | None = None, truth_n: int = 20000) -> dict[str, Any]:
    """The blind candidates (config/releases/heldout_vN). The first run is written once and kept."""
    v = version or heldout_versions()[-1]
    meta = load("pipeline")["heldout"][v]
    st = process.Study(p, truth_n=truth_n, seed=4040, base_id=meta["base"])
    df, details = process.run(heldout(v), st)
    out = {
        "version": v,
        "base": meta["base"],
        "process": meta["process"],
        "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "candidates": df.to_dict(orient="records"),
        "score": process.score(df).to_dict(orient="records"),
    }
    d = REPORTS / "heldout" / v
    first = d / "first_run.json"
    target = first if not first.exists() else d / "latest.json"
    _write(target, out)
    _write(target.with_name(target.stem + "_details.json"), details)
    if target == first:
        _write(d / "FIRST_RUN.md", heldout_markdown(out, df))
    _log(f"held-out {v} written to {target.relative_to(REPORTS.parent)}")
    return out


def heldout_markdown(out: dict[str, Any], df: pd.DataFrame) -> str:
    L = [
        f"# Held-out candidate releases {out['version']}: first run",
        "",
        f"Set {out['version']}, run once on {out['ran_at']} against `{out['base']}` with process {out['process']}.",
        f"Written by an agent that read only `docs/RELEASES.md`, `_base.yaml` and `{out['base']}.yaml`, before",
        "these candidates were ever run. This file is not regenerated: later runs go to",
        "`latest.json`. If the shipping process is changed after studying these, move them to the dev set and",
        "commission new ones (see AGENTS.md).",
        "",
        "| Candidate | True Δ resolution | True Δ hallucination | Unsafe actions | Cost ratio | P0 | P1 | P2 | P3 | P4 | Stopped at | Why |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    yes = lambda b: "ship" if b else "·"  # noqa: E731
    for c in df.to_dict(orient="records"):
        L.append(
            f"| {c['candidate']} | {100 * c['true_d_resolved']:+.1f}pp | {100 * c['true_d_hallucinated']:+.1f}pp | {c['true_unsafe']} | {c['true_cost_ratio']:.2f} | "
            f"{yes(c['P0 read 20'])} | {yes(c['P1 judges'])} | {yes(c['P2 calibrated'])} | {yes(c['P3 + A/B and rollout'])} | {yes(c.get('P4 backtest and rollout', False))} | {c['stopped_at']} | {c['reasons'][:140]} |"
        )
    L += ["", "| Policy | Shipped | Truly better | Harmful | Unsafe | Better ones missed |", "|---|---|---|---|---|---|"]
    L += [
        f"| {s['policy']} | {s['shipped']} | {s['good_shipped']} | {s['harmful_shipped']} | {s['unsafe_shipped']} | {s['good_missed']} |"
        for s in out["score"]
    ]
    return "\n".join(L) + "\n"


def run(profile: str = "full", skip_train: bool = False) -> dict[str, Any]:
    from arc.gate import gate
    from arc.report import write_report
    from arc.train import train

    c = load("pipeline")[profile]
    t0 = time.time()
    if not skip_train or not (MODELS / "nlu.joblib").exists():
        _log("training")
        train()
    _write(REPORTS / "model_card.json", json.loads((MODELS / "model_card.json").read_text()))
    p = SimPlatform()
    _log("comparing releases against the truth")
    _write(REPORTS / "releases.json", release_study.compare(all_releases(), c["compare_conversations"], p=p))
    run_reviews(c["reviews"], p)
    aa_test(p)
    _log("shipping-process study")
    study(c["study_candidates"], c["study_truth_conversations"], c["study_seed"], p)
    _log("production drill and cost frontier")
    ops(c["drill_seeds"], c["frontier_conversations"], p)
    res = gate()
    write_report(profile)
    _log(f"done in {time.time() - t0:.0f}s; gate {'passed' if res['passed'] else 'FAILED'}")
    return res
