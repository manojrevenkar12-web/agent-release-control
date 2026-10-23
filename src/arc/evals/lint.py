"""Static checks on a release before anything runs: settings within range, procedures that exist,
and no procedure path that writes (refund, cancel, change email) before verifying identity."""

from __future__ import annotations

from arc.agent import procedures
from arc.agent.release import Release, validate


def lint(r: Release) -> list[str]:
    problems = validate(r.cfg)
    for name, ver in r.cfg["procedures"].items():
        try:
            p = procedures.load(name, ver)
        except (FileNotFoundError, KeyError):
            continue
        if p.writes_without_verification:
            problems.append(f"procedure {name} {ver}: a path writes before verifying identity")
    return problems
