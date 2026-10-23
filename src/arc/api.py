"""HTTP API: talk to the agent under any release, inspect and diff releases, read release reviews,
start a review, and Prometheus metrics for the live agent.

Auth: `X-API-Key`. Keys come from ARC_API_KEYS ("key:role,key:role"); roles are `viewer` (read,
talk to the agent) and `releaser` (also start reviews and change what is serving). Without
ARC_API_KEYS the API runs open for local use and says so in /health.

The company systems behind the agent are the simulated Larkspur backend; `/demo/inbox` shows the
verification code the backend "emailed" to the account owner so a person can complete a procedure.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from arc.agent.core import Agent, ConvState
from arc.agent.provider import Offline
from arc.agent.release import Release, all_releases, heldout, heldout_versions
from arc.agent.release import load as load_release
from arc.config import REPORTS
from arc.experiment.ab import assign
from arc.runner import env

REG = CollectorRegistry()
TURNS = Counter("arc_agent_replies_total", "Agent replies", ["release", "kind"], registry=REG)
COST = Counter("arc_agent_cost_eur_total", "AI spend in EUR", ["release"], registry=REG)
LAT = Histogram(
    "arc_agent_reply_seconds", "Simulated model latency per reply", ["release"], buckets=(0.5, 1, 2, 3, 5, 8, 13, 21), registry=REG
)
HANDOFF = Counter("arc_agent_handoffs_total", "Handoffs to people", ["release", "team"], registry=REG)

MAX_CONVERSATIONS = 2000


def _keys() -> dict[str, str]:
    raw = os.environ.get("ARC_API_KEYS", "")
    out = {}
    for part in filter(None, (p.strip() for p in raw.split(","))):
        k, _, role = part.partition(":")
        out[k] = role or "viewer"
    return out


def role(x_api_key: str | None = Header(default=None)) -> str:
    keys = _keys()
    if not keys:
        return "releaser"
    if not x_api_key or x_api_key not in keys:
        raise HTTPException(401, "missing or unknown X-API-Key")
    return keys[x_api_key]


def releaser(r: str = Depends(role)) -> str:
    if r != "releaser":
        raise HTTPException(403, "needs the releaser role")
    return r


class Serving(BaseModel):
    production: str = "r1-prod"
    candidate: str | None = None
    share: float = Field(default=0.0, ge=0.0, le=1.0)


class Start(BaseModel):
    account: int = Field(ge=0)
    message: str = Field(min_length=1, max_length=2000)
    release: str | None = None  # default: what is serving for this account


class Say(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ReviewRequest(BaseModel):
    candidate: str
    baseline: str = "r1-prod"
    online: bool = False  # offline review takes seconds; online adds the A/B test and rollout


class State:
    def __init__(self) -> None:
        self.serving = Serving()
        self.agents: dict[str, Agent] = {}
        self.convs: OrderedDict[str, tuple[Agent, ConvState]] = OrderedDict()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def agent(self, rid: str) -> Agent:
        if rid not in self.agents:
            e = env()
            self.agents[rid] = Agent(_release(rid), e.nlu, e.world.systems, Offline(seed=len(self.agents)))
        return self.agents[rid]


def _release(rid: str) -> Release:
    try:
        return load_release(rid)
    except (FileNotFoundError, ValueError) as err:
        raise HTTPException(404, f"no release {rid}") from err


def _turn_out(cid: str, rid: str, t: Any) -> dict[str, Any]:
    TURNS.labels(rid, t.kind).inc()
    COST.labels(rid).inc(t.cost_eur)
    LAT.labels(rid).observe(t.latency_s)
    for e in t.events:
        if e["type"] == "handoff":
            HANDOFF.labels(rid, e["team"]).inc()
    return {
        "conversation": cid,
        "release": rid,
        "reply": t.text,
        "kind": t.kind,
        "done": t.done,
        "events": t.events,
        "cost_eur": round(t.cost_eur, 6),
        "latency_s": round(t.latency_s, 3),
    }


def create_app() -> FastAPI:
    app = FastAPI(title="agent-release-control", version="0.1.0")
    st = State()
    app.state.arc = st

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "auth": "api keys" if _keys() else "open (set ARC_API_KEYS)", "serving": st.serving.model_dump()}

    @app.get("/releases")
    def releases(_: str = Depends(role)) -> list[dict[str, Any]]:
        out = [{"id": r.id, "description": r.description, "fingerprint": r.fingerprint, "set": "dev"} for r in all_releases()]
        return out + [
            {"id": r.id, "description": r.description, "fingerprint": r.fingerprint, "set": f"heldout {v}"}
            for v in heldout_versions()
            for r in heldout(v)
        ]

    @app.get("/releases/{rid}")
    def release(rid: str, _: str = Depends(role)) -> dict[str, Any]:
        r = _release(rid)
        return {"id": r.id, "description": r.description, "fingerprint": r.fingerprint, "settings": r.cfg}

    @app.get("/releases/{rid}/diff")
    def diff(rid: str, against: str = "r1-prod", _: str = Depends(role)) -> dict[str, Any]:
        d = _release(rid).diff(_release(against))
        return {"release": rid, "against": against, "changes": {k: {"from": a, "to": b} for k, (a, b) in d.items()}}

    @app.get("/serving")
    def get_serving(_: str = Depends(role)) -> dict[str, Any]:
        return st.serving.model_dump()

    @app.put("/serving")
    def put_serving(s: Serving, _: str = Depends(releaser)) -> dict[str, Any]:
        _release(s.production)
        if s.candidate:
            _release(s.candidate)
        st.serving = s
        return s.model_dump()

    def serving_for(account: int) -> str:
        s = st.serving
        if s.candidate and s.share > 0 and bool(assign(np.array([account]), 3, s.share)[0]):
            return s.candidate
        return s.production

    @app.post("/conversations")
    def start(body: Start, _: str = Depends(role)) -> dict[str, Any]:
        e = env()
        if body.account >= e.world.n_accounts:
            raise HTTPException(404, "no such account")
        rid = body.release or serving_for(body.account)
        with st.lock:
            a = st.agent(rid)
            cid = "api-" + uuid.uuid4().hex[:12]
            cs = a.start(cid, body.account)
            st.convs[cid] = (a, cs)
            while len(st.convs) > MAX_CONVERSATIONS:
                old, (old_agent, _old_state) = st.convs.popitem(last=False)
                old_agent.sys.forget(old)
            t = a.respond(cs, body.message)
        return _turn_out(cid, rid, t)

    @app.post("/conversations/{cid}/messages")
    def say(cid: str, body: Say, _: str = Depends(role)) -> dict[str, Any]:
        with st.lock:
            if cid not in st.convs:
                raise HTTPException(404, "no such conversation")
            a, cs = st.convs[cid]
            if cs.last_kind in ("handoff", "closing"):
                raise HTTPException(409, "the conversation has ended")
            t = a.respond(cs, body.message)
        return _turn_out(cid, a.r.id, t)

    @app.get("/conversations/{cid}/actions")
    def actions(cid: str, _: str = Depends(role)) -> dict[str, Any]:
        if cid not in st.convs:
            raise HTTPException(404, "no such conversation")
        a, cs = st.convs[cid]
        return {"conversation": cid, "events": cs.log, "actions": a.sys.actions_of(cid)}

    @app.get("/demo/inbox/{cid}")
    def inbox(cid: str, _: str = Depends(role)) -> dict[str, Any]:
        if cid not in st.convs:
            raise HTTPException(404, "no such conversation")
        a, cs = st.convs[cid]
        return {"conversation": cid, "verification_code": a.sys.code_for(cid, cs.account)}

    @app.get("/reviews")
    def reviews(_: str = Depends(role)) -> list[dict[str, Any]]:
        out = []
        for p in sorted((REPORTS / "reviews").glob("*.json")):
            d = json.loads(p.read_text())
            out.append({k: d[k] for k in ("candidate", "baseline", "decision", "stopped_at", "reasons")})
        return out

    @app.get("/reviews/{rid}")
    def review_get(rid: str, _: str = Depends(role)) -> dict[str, Any]:
        p = REPORTS / "reviews" / f"{rid}.json"
        if not p.exists():
            raise HTTPException(404, f"no review for {rid}; POST /reviews to run one")
        return json.loads(p.read_text())

    @app.post("/reviews", status_code=202)
    def review_post(body: ReviewRequest, _: str = Depends(releaser)) -> dict[str, Any]:
        cand, base = _release(body.candidate), _release(body.baseline)
        jid = uuid.uuid4().hex[:12]
        st.jobs[jid] = {"id": jid, "status": "running", "candidate": cand.id, "started": time.time()}

        def work() -> None:
            from arc.platform import SimPlatform
            from arc.review import review

            try:
                r = review(SimPlatform(), base, cand, online=body.online)
                st.jobs[jid].update(status="done", result=r.as_dict())
            except Exception as err:  # reported to the caller, not swallowed
                st.jobs[jid].update(status="failed", error=repr(err))

        threading.Thread(target=work, daemon=True).start()
        return {"job": jid, "status": "running"}

    @app.get("/jobs/{jid}")
    def job(jid: str, _: str = Depends(role)) -> dict[str, Any]:
        if jid not in st.jobs:
            raise HTTPException(404, "no such job")
        return st.jobs[jid]

    @app.get("/reports/{name}")
    def report(name: str, _: str = Depends(role)) -> Any:
        allowed = {
            "process_study": "process_study.json",
            "ops_drill": "ops_drill.json",
            "gate": "gate.json",
            "releases": "releases.json",
            "heldout_v1": "heldout/v1/first_run.json",
            "heldout_v2": "heldout/v2/first_run.json",
        }
        if name not in allowed or not (REPORTS / allowed[name]).exists():
            raise HTTPException(404, f"no report {name}")
        return json.loads((REPORTS / allowed[name]).read_text())

    @app.get("/metrics")
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(REG).decode(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
