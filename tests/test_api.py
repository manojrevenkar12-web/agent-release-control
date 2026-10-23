import pytest
from fastapi.testclient import TestClient

from arc.api import create_app

pytestmark = pytest.mark.usefixtures("trained")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ARC_API_KEYS", "v-key:viewer,r-key:releaser")
    return TestClient(create_app())


V, R = {"X-API-Key": "v-key"}, {"X-API-Key": "r-key"}


def test_auth(client):
    assert client.get("/releases").status_code == 401
    assert client.get("/releases", headers={"X-API-Key": "nope"}).status_code == 401
    assert client.get("/releases", headers=V).status_code == 200
    assert client.put("/serving", json={"production": "r1-prod"}, headers=V).status_code == 403
    assert client.get("/health").json()["auth"] == "api keys"


def test_refund_conversation_end_to_end(client):
    r = client.post("/conversations", json={"account": 5, "message": "please refund my last payment"}, headers=V).json()
    assert r["kind"] == "verify" and r["release"] == "r1-prod"
    code = client.get(f"/demo/inbox/{r['conversation']}", headers=V).json()["verification_code"]
    r2 = client.post(f"/conversations/{r['conversation']}/messages", json={"message": f"here: {code}"}, headers=V).json()
    assert r2["kind"] == "result"
    acts = client.get(f"/conversations/{r['conversation']}/actions", headers=V).json()["actions"]
    assert acts[0]["action"] == "identity.send_code"
    m = client.get("/metrics").text
    assert 'arc_agent_replies_total{kind="result",release="r1-prod"}' in m


def test_releases_and_diff(client):
    ids = {r["id"]: r["set"] for r in client.get("/releases", headers=V).json()}
    assert ids["r2-personalised"] == "dev" and sum(s.startswith("heldout") for s in ids.values()) >= 10
    d = client.get("/releases/r2-personalised/diff", headers=V).json()
    assert d["changes"] == {"personalisation.plan_aware": {"from": False, "to": True}}
    assert client.get("/releases/nope", headers=V).status_code == 404


def test_serving_split_routes_some_accounts_to_the_candidate(client):
    assert (
        client.put("/serving", json={"production": "r1-prod", "candidate": "r2-personalised", "share": 0.5}, headers=R).status_code == 200
    )
    rels = {
        client.post("/conversations", json={"account": a, "message": "how do I export a report"}, headers=V).json()["release"]
        for a in range(40)
    }
    assert rels == {"r1-prod", "r2-personalised"}


def test_validation(client):
    assert client.post("/conversations", json={"account": -1, "message": "hi"}, headers=V).status_code == 422
    assert client.post("/conversations", json={"account": 10**9, "message": "hi"}, headers=V).status_code == 404
    assert client.post("/conversations/none/messages", json={"message": "hi"}, headers=V).status_code == 404
