"""The shipping process must decide from what a support team can see. These tests poison every
truth field the simulator keeps; any shipping code that reads one fails loudly."""

import ast
from pathlib import Path

import pytest

from arc.agent.release import load
from arc.platform import SimPlatform
from arc.sim import review as human_review

SRC = Path(__file__).resolve().parents[1] / "src" / "arc"
SHIPPING = ["ship.py", "review.py", "evals", "experiment", "ops/monitor.py", "api.py", "agent"]
TRUTH = ("resolved", "handled_correctly", "hallucinated", "unsafe", "intent_true", "kind_true")


class Poison:
    def __bool__(self):
        raise AssertionError("shipping code read the truth")

    __float__ = __int__ = __index__ = __bool__

    def __eq__(self, other):
        raise AssertionError("shipping code read the truth")

    __hash__ = object.__hash__


class PoisonedPlatform(SimPlatform):
    """Outcomes come back with their truth replaced; human review still sees the real conversations."""

    def __init__(self):
        super().__init__()
        self.real = {}

    def run(self, release, specs, seed=0, incidents=None):
        outs = super().run(release, specs, seed, incidents)
        for o in outs:
            self.real[(release.fingerprint, o.conv, seed)] = {k: getattr(o, k) for k in TRUTH}
            o._key = (release.fingerprint, o.conv, seed)
            for k in TRUTH:
                setattr(o, k, Poison())
        return outs

    def label(self, outs):
        restored = []
        for o in outs:
            c = type(o)(**{f: getattr(o, f) for f in o.__dataclass_fields__})
            for k, v in self.real[o._key].items():
                setattr(c, k, v)
            restored.append(c)
        self.label_seed += 1
        return human_review.labels(restored, self.label_seed)


def _imports(path: Path) -> set[str]:
    mods = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
        elif isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
    return mods


def test_shipping_code_never_imports_the_simulator():
    files = [p for s in SHIPPING for p in ((SRC / s).rglob("*.py") if (SRC / s).is_dir() else [SRC / s])]
    assert files
    for f in files:
        bad = {m for m in _imports(f) if m.startswith("arc.sim") or m.startswith("arc.study")}
        assert not bad, f"{f.relative_to(SRC)} imports {bad}"


@pytest.mark.slow
def test_release_review_runs_on_poisoned_truth(trained):
    from arc.review import review

    p = PoisonedPlatform()
    r = review(p, load("r1-prod"), load("r2-personalised"), seed=3, day0=900)
    assert r.backtest is not None and r.ab is not None
    assert r.decision == "ship"
    r = review(p, load("r1-prod"), load("r7-refund-v2"), seed=3)
    assert r.stopped_at == "suites"
