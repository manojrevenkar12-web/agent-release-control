"""Releases: versioned bundles of everything that changes the agent's behaviour (models and routing,
understanding, retrieval, personalisation, procedure versions, guidance, safety)."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from arc.config import CONFIG

RELEASES = CONFIG / "releases"


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass(frozen=True)
class Release:
    id: str
    description: str
    cfg: dict[str, Any]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.cfg, sort_keys=True).encode()).hexdigest()[:10]

    def __getitem__(self, k: str) -> Any:
        return self.cfg[k]

    def diff(self, other: Release) -> dict[str, tuple[Any, Any]]:
        """Settings that differ from `other` (dotted keys): {key: (other, self)}."""
        out: dict[str, tuple[Any, Any]] = {}

        def walk(a: Any, b: Any, path: str) -> None:
            if isinstance(a, dict) and isinstance(b, dict):
                for k in sorted(set(a) | set(b)):
                    walk(a.get(k), b.get(k), f"{path}.{k}" if path else k)
            elif a != b:
                out[path] = (a, b)

        walk(other.cfg, self.cfg, "")
        return out


SCHEMA: dict[str, dict[str, tuple[Any, ...]]] = {
    "models": {
        "understand_tier": ("small", "large"),
        "escalate_below": (0.0, 1.01),
        "answer_tier": ("small", "large"),
        "context_articles": (1, 12),
    },
    "understanding": {"clarify_below": (0.0, 1.0), "max_clarifications": (0, 3)},
    "retrieval": {"require_agreement": (False, True), "top_k": (1, 10), "min_score": (0.0, 30.0)},
    "personalisation": {"plan_aware": (False, True)},
    "guidance": {"offer_human_after_failures": (1, 5), "ask_if_resolved": (False, True)},
    "safety": {"injection_filter": (False, True)},
}


def validate(cfg: dict[str, Any]) -> list[str]:
    """Problems with a release configuration (unknown keys, values out of range, missing procedures)."""
    errs = []
    for sec, keys in SCHEMA.items():
        got: dict[str, Any] = cfg.get(sec, {})
        for k in set(got) - set(keys):
            errs.append(f"unknown setting {sec}.{k}")
        for k, allowed in keys.items():
            if k not in got:
                errs.append(f"missing {sec}.{k}")
                continue
            v = got[k]
            if isinstance(allowed[0], str | bool):
                if v not in allowed:
                    errs.append(f"{sec}.{k}={v!r} is not one of {allowed}")
            elif not (allowed[0] <= v <= allowed[1]):
                errs.append(f"{sec}.{k}={v} outside {allowed[0]}..{allowed[1]}")
    for name, ver in cfg.get("procedures", {}).items():
        p = CONFIG / "procedures" / f"{name}.yaml"
        if not p.exists() or ver not in yaml.safe_load(p.read_text())["versions"]:
            errs.append(f"procedure {name} {ver} does not exist")
    return errs


def base() -> dict[str, Any]:
    return yaml.safe_load((RELEASES / "_base.yaml").read_text())


def from_dict(d: dict[str, Any]) -> Release:
    d = dict(d)
    rid, desc = d.pop("id"), d.pop("description", "")
    cfg = merge(base(), d)
    errs = validate(cfg)
    if errs:
        raise ValueError(f"release {rid}: " + "; ".join(errs))
    return Release(rid, desc, cfg)


def load(name_or_path: str | Path) -> Release:
    p = Path(name_or_path)
    if not p.exists():
        p = RELEASES / f"{name_or_path}.yaml"
    if not p.exists():
        found = sorted(RELEASES.glob(f"heldout_v*/{name_or_path}.yaml"))
        if found:
            p = found[-1]
    return from_dict(yaml.safe_load(p.read_text()))


def all_releases(directory: Path = RELEASES, prefix: str = "r") -> list[Release]:
    return [load(p) for p in sorted(directory.glob(f"{prefix}*.yaml"), key=lambda p: int(p.stem.split("-")[0][len(prefix) :]))]


def heldout_versions() -> list[str]:
    return sorted((p.name.removeprefix("heldout_") for p in RELEASES.glob("heldout_v*") if p.is_dir()), key=lambda v: int(v[1:]))


def heldout(version: str | None = None) -> list[Release]:
    """Candidate releases written without seeing the agent or the simulator (docs/RELEASES.md only).
    Each version was written fresh after the shipping process last changed; the latest is current."""
    vs = heldout_versions()
    v = version or (vs[-1] if vs else None)
    return all_releases(RELEASES / f"heldout_{v}", "h") if v else []
