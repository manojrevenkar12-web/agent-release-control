"""The release gate for the platform (config/release.yaml), over the reports `arc run` wrote."""

from __future__ import annotations

import json
from typing import Any

from arc.config import REPORTS, load


def _read(name: str) -> Any:
    p = REPORTS / name
    return json.loads(p.read_text()) if p.exists() else None


def gate() -> dict[str, Any]:
    c = load("release")
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    card = _read("model_card.json")
    if card:
        auc = card["judge"]["validation"]["r1-prod"]["resolved"]["auc"]
        add(
            "judge ranks production conversations",
            auc >= c["judge"]["min_auc_resolved_production"],
            f"AUC {auc} (needs {c['judge']['min_auc_resolved_production']})",
        )
    else:
        add("judge ranks production conversations", False, "no model card")
    for rid, want in c["expected_reviews"].items():
        r = _read(f"reviews/{rid}.json")
        if r is None:
            continue  # the quick profile reviews fewer releases
        got = "ship" if r["decision"] == "ship" else "do not ship"
        add(
            f"review of {rid}",
            got == want,
            f"{r['decision']}" + (f" at {r['stopped_at']}" if r["stopped_at"] else "") + f" (expected {want})",
        )
    aa = _read("aa_test.json")
    if aa:
        ok = (aa["decision"] != "ship" or not c["aa_test"]["must_not_ship"]) and aa["srm_p"] >= c["aa_test"]["min_srm_p"]
        add("A/A test", ok, f"{aa['decision']}, p = {aa['primary']['p']:.3f}, SRM p = {aa['srm_p']}")
    else:
        add("A/A test", False, "not run")
    ps = _read("process_study.json")
    if ps:
        sc = {s["policy"]: s for s in ps["score"]}
        pc = c["process"]
        s = sc[pc["policy"]]
        add(
            f"{pc['policy']}: unsafe releases shipped",
            s["unsafe_shipped"] <= pc["max_unsafe_shipped"],
            f"{s['unsafe_shipped']} of {s['shipped']} shipped",
        )
        add(
            f"{pc['policy']}: harmful releases shipped",
            s["harmful_shipped"] <= pc["max_harmful_shipped"],
            f"{s['harmful_shipped']} of {s['shipped']} shipped",
        )
        s2 = sc[pc["calibrated_policy"]]
        add(
            f"{pc['calibrated_policy']}: unsafe releases passed",
            s2["unsafe_shipped"] <= pc["calibrated_max_unsafe_shipped"],
            f"{s2['unsafe_shipped']} of {s2['shipped']} passed",
        )
    else:
        add("shipping-process study", False, "not run")
    od = _read("ops_drill.json")
    if od:
        oc = c["ops"]
        for d, seed in zip(od["drills"], od["seeds"], strict=True):
            missed = [i["name"] for i in d["incidents"] if not i["detected"] or i["minutes_to_detect"] > i["minutes"]]
            if oc["every_incident_detected_while_ongoing"]:
                add(
                    f"drill seed {seed}: incidents detected while ongoing",
                    not missed,
                    "all detected" if not missed else "missed or late: " + ", ".join(missed),
                )
            add(
                f"drill seed {seed}: false alarms",
                d["false_alarms_clean_run"] <= oc["max_false_alarms_per_clean_fortnight"],
                f"{d['false_alarms_clean_run']} on a clean fortnight",
            )
    else:
        add("production drill", False, "not run")
    res = {"passed": all(x["passed"] for x in checks), "checks": checks}
    (REPORTS / "gate.json").write_text(json.dumps(res, indent=1))
    return res
