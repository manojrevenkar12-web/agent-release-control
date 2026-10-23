import pytest

from arc.agent import procedures
from arc.agent.release import load
from arc.evals.lint import lint


def test_expression_language():
    s = {"charge": {"days_ago": 10, "refunded_this_year": False, "amount": 12.5}}
    assert procedures.evaluate("charge.days_ago <= 14 and not charge.refunded_this_year", s)
    assert not procedures.evaluate("charge.amount >= 20", s)
    assert procedures.evaluate("0 < charge.days_ago < 11", s)


@pytest.mark.parametrize("expr", ["__import__('os').system('true')", "charge.amount + 1 > 2", "[x for x in charge]", "open('f')"])
def test_expression_language_refuses_anything_else(expr):
    with pytest.raises((ValueError, SyntaxError)):
        procedures.evaluate(expr, {"charge": {"amount": 1}})


def test_static_check_finds_writes_before_verification():
    assert not procedures.load("refund", "v1").writes_without_verification
    assert procedures.load("refund", "v3").writes_without_verification
    assert lint(load("r1-prod")) == []
    assert any("writes before verifying" in p for p in lint(load("r8-refund-v3")))
    # v2's bug (a 30-day window) is a policy error, not a structural one: only the safety suite sees it
    assert lint(load("r7-refund-v2")) == []


def test_every_procedure_version_is_reachable_and_ends():
    for name in ("refund", "cancel", "change_email", "send_invoice", "update_payment"):
        p = procedures.load(name, "v1")
        assert p.steps[0]["id"]
        assert any(s["type"] in ("action", "say") for s in p.steps)
