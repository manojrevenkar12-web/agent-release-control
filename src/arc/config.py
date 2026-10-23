"""Paths and configuration. Product and business settings live in config/, never in code."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("ARC_ROOT", Path(__file__).resolve().parents[2]))
CONFIG = ROOT / "config"
KNOWLEDGE = ROOT / "knowledge"
WORLD = ROOT / "world"
DATA = Path(os.environ.get("ARC_DATA", ROOT / "data"))
MODELS = Path(os.environ.get("ARC_MODELS", ROOT / "models"))
REPORTS = Path(os.environ.get("ARC_REPORTS", ROOT / "reports"))


@lru_cache
def load(name: str) -> Any:
    """config/<name>.yaml (cached; do not mutate)."""
    return yaml.safe_load((CONFIG / f"{name}.yaml").read_text())
