import pytest
import yaml

from arc.agent.release import RELEASES, all_releases, from_dict, heldout, load, validate


def test_every_release_loads_and_validates():
    rs = all_releases()
    assert [r.id for r in rs][:2] == ["r1-prod", "r2-personalised"]
    for r in rs + heldout("v1"):
        assert validate(r.cfg) == []
        assert r.id == (RELEASES / f"{r.id}.yaml").stem or r.id.startswith("h")


def test_every_heldout_set_has_ten_releases_that_change_something():
    from arc.agent.release import heldout_versions
    from arc.config import load as load_cfg

    meta = load_cfg("pipeline")["heldout"]
    assert heldout_versions() and set(heldout_versions()) <= set(meta)
    for v in heldout_versions():
        hs = heldout(v)
        assert len(hs) == 10
        assert all(h.diff(load(meta[v]["base"])) for h in hs)


def test_diff_and_fingerprint():
    a, b = load("r1-prod"), load("r12-personalised-router")
    assert b.diff(a) == {"models.escalate_below": (0.6, 0.8), "personalisation.plan_aware": (False, True)}
    assert a.fingerprint == load("r1-prod").fingerprint != b.fingerprint
    assert a.diff(a) == {}


@pytest.mark.parametrize(
    "over, msg",
    [
        ({"models": {"escalate_below": 2}}, "outside"),
        ({"models": {"answer_tier": "huge"}}, "not one of"),
        ({"retrieval": {"rerank": True}}, "unknown setting"),
        ({"procedures": {"refund": "v9"}}, "does not exist"),
    ],
)
def test_invalid_releases_are_rejected(over, msg):
    with pytest.raises(ValueError, match=msg):
        from_dict({"id": "bad", **over})


def test_base_has_every_schema_setting():
    base = yaml.safe_load((RELEASES / "_base.yaml").read_text())
    assert validate(base) == []
