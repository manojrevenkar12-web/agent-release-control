"""The shipping process on releases whose effect is known."""

import pytest

from arc import ship
from arc.agent.release import load
from arc.review import review

pytestmark = pytest.mark.slow


def test_suites_block_the_policy_bug_and_pass_production(platform):
    prod = {s.suite: s for s in ship.suites(platform, load("r1-prod"))}
    assert prod["safety"].ok and prod["escalations"].ok
    bug = {s.suite: s for s in ship.suites(platform, load("r7-refund-v2"))}
    assert not bug["safety"].ok


def test_offline_review_stops_unsafe_and_slow_releases(platform):
    base = load("r1-prod")
    assert review(platform, base, load("r8-refund-v3"), online=False).stopped_at == "static"
    assert review(platform, base, load("r4-always-large"), online=False).stopped_at == "backtest"
    assert review(platform, base, load("r2-personalised"), online=False).decision == "ready for A/B test"


def test_backtest_calibration_finds_the_personalisation_gain(platform):
    bt = ship.run_backtest(platform, load("r1-prod"), load("r2-personalised"), 800, 150, 5)
    m = bt.metrics["calibrated_resolution"]
    assert m.lo > 0
    assert bt.metrics["calibrated_hallucination"].hi < 0


def test_rollout_stops_a_release_that_writes_without_verification(platform):
    ro = ship.rollout(platform, load("r1-prod"), load("r8-refund-v3"), 700, 2)
    assert not ro.shipped and any("writes without verification" in r for r in ro.reasons)
    # it is caught, but rare small refunds can reach real customers first: why the static check runs first
    assert ro.stopped_at in ("dark", "1%", "10%", "50%")
