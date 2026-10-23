"""The support agent: understands a message, then answers from the help centre, runs a procedure,
hands off to a team, or says it cannot help, under the settings of a release.

Every reply carries structured events (what it answered from, which plan section, which procedure
step, which team) and the model calls it made, with their cost and latency. Evaluation reads the
events and the systems' action log, not just the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from arc.agent import procedures as procs
from arc.agent.nlu import NLU, expand
from arc.agent.provider import Offline, tokens
from arc.agent.release import Release
from arc.agent.safety import code_in, email_in, is_injection, redact
from arc.config import load
from arc.knowledge import index as kb_index
from arc.knowledge import load as load_kb
from arc.systems import Systems
from arc.types import AgentTurn, Call

CONFIRM = re.compile(r"\b(solved|perfect|thank|thanks|great|that's what i needed|yes)\b", re.I)
HUMAN = re.compile(r"\b(human|real person|agent|someone|person)\b", re.I)
NEGATIVE = re.compile(r"^\s*(no\b|not what|that's not|wrong)", re.I)
TEAM_TEXT = {
    "engineering": "our engineering team, who will look into the bug",
    "privacy": "our privacy team, who handle data deletion requests and confirm within 30 days",
    "security": "our security team. Please don't click links in that email or share your password",
    "support": "a member of our support team",
    "billing": "our billing team",
}


@dataclass
class ConvState:
    id: str
    account: int
    turns: int = 0
    clarifications: int = 0
    failures: int = 0
    last_kind: str = ""
    run: procs.Run | None = None
    intent: str | None = None
    used_large: bool = False
    first_message: str = ""
    log: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    def __init__(self, release: Release, nlu: NLU, systems: Systems, provider: Offline | None = None):
        self.r = release
        self.cfg = release.cfg
        self.nlu = nlu
        self.sys = systems
        self.provider = provider or Offline()
        self.kb = load_kb()
        self.index = kb_index()
        self.playbook = load("playbook")
        self.models = load("models")
        self.answer_to = self.playbook["answer"]
        self.procedure_for = self.playbook["procedure"]
        self.handoff_to = self.playbook["handoff"]
        self.declined = set(self.playbook["decline"])

    def start(self, conv: str, account: int) -> ConvState:
        return ConvState(conv, account)

    # ---------------------------------------------------------------------------------------------
    def respond(self, st: ConvState, message: str) -> AgentTurn:
        st.turns += 1
        if st.turns == 1:
            st.first_message = message
        calls: list[Call] = []
        if st.last_kind in ("answer", "result") and CONFIRM.search(message) and not NEGATIVE.search(message):
            return self._turn(st, AgentTurn("Glad I could help. Have a good day!", "closing", [{"type": "closing"}], done=True), calls)
        if HUMAN.search(message) and st.turns > 1:
            return self._handoff(st, "support", "the customer asked for a person", calls)
        if self.cfg["safety"]["injection_filter"] and is_injection(message):
            ev: list[dict[str, Any]] = [{"type": "injection_detected"}]
            return self._turn(
                st,
                AgentTurn("I can't do that. I can help with questions about your account, billing or Larkspur itself.", "refuse", ev),
                calls,
            )
        if st.run is not None and st.run.waiting:
            return self._continue(st, message, calls)
        if NEGATIVE.search(message) and st.last_kind in ("answer", "result", "decline"):
            st.failures += 1
            if st.failures >= self.cfg["guidance"]["offer_human_after_failures"]:
                return self._handoff(st, "support", "previous answers did not help", calls)

        label, conf = self._understand(message, calls)
        st.used_large = any(c.purpose == "understand" and c.tier == "large" and c.ok for c in calls)
        if label is None:  # every model call failed
            return self._handoff(st, "support", "model provider unavailable", calls, error=True)
        st.intent = label
        u = self.cfg["understanding"]
        if label == "vague" or conf < u["clarify_below"]:
            if st.clarifications < u["max_clarifications"]:
                st.clarifications += 1
                ev = [{"type": "clarify", "predicted": label, "confidence": round(conf, 3)}]
                return self._turn(st, AgentTurn("Happy to help. Could you tell me a bit more about what you need?", "clarify", ev), calls)
            return self._handoff(st, "support", "could not understand the request", calls)
        if label in self.answer_to:
            return self._answer(st, message, label, conf, calls)
        if label in self.procedure_for:
            name = self.procedure_for[label]
            st.run = procs.Run(procs.load(name, self.cfg["procedures"][name]))
            return self._continue(st, message, calls, start=True)
        if label in self.handoff_to:
            return self._handoff(st, self.handoff_to[label], f"request: {label}", calls)
        return self._decline(st, message, calls, label)

    # -- understanding ----------------------------------------------------------------------------
    def _call(self, purpose: str, tier: str, tin: int, tout: int, calls: list[Call]) -> bool:
        for t in (tier, "large" if tier == "small" else "small"):  # one fallback to the other tier
            c = self.provider.call(purpose, t, tin, tout)
            calls.append(c)
            if c.ok:
                return True
        return False

    def _understand(self, message: str, calls: list[Call]) -> tuple[str | None, float]:
        m = self.cfg["models"]
        tin = self.models["system_prompt_tokens"] + tokens(message)
        tier = m["understand_tier"]
        if not self._call("understand", tier, tin, 20, calls):
            return None, 0.0
        used = calls[-1].tier
        label, conf = self.nlu.predict(message, used)
        if (
            used == "small"
            and conf < m["escalate_below"]
            and self._call("understand", "large", tin, 20, calls)
            and calls[-1].tier == "large"
        ):
            label, conf = self.nlu.predict(message, "large")
        return label, conf

    # -- answering --------------------------------------------------------------------------------
    def _answer(self, st: ConvState, message: str, label: str, conf: float, calls: list[Call]) -> AgentTurn:
        aid = self.answer_to[label]
        ret = self.cfg["retrieval"]
        # the large tier reads a message with a wider vocabulary, which also finds better passages
        query = expand([message])[0] if st.used_large else message
        inc = self.provider.incident
        hits = [] if inc and inc.retrieval_down else self.index.search(query, ret["top_k"])
        support = next((h.score for h in hits if h.doc == aid), 0.0)
        if ret["require_agreement"] and support < ret["min_score"]:
            return self._decline(st, message, calls, label, reason="not supported by the help centre")
        art = self.kb[aid]
        acc = self.sys.account(st.account)
        plan = acc.plan if self.cfg["personalisation"]["plan_aware"] else None
        text = art.text_for(plan)
        ask = self.cfg["guidance"]["ask_if_resolved"]
        reply = text + (" Did that answer your question?" if ask else "")
        m = self.cfg["models"]
        context = self.models["passage_tokens"] * m["context_articles"]
        tin = self.models["system_prompt_tokens"] + tokens(message) + context + 40
        if not self._call("answer", m["answer_tier"], tin, tokens(reply), calls):
            return self._handoff(st, "support", "model provider unavailable", calls, error=True)
        ev = [
            {
                "type": "answer",
                "article": aid,
                "plan": (plan or "pro") if art.plan_specific else None,
                "confidence": round(conf, 3),
                "support": round(support, 2),
                "sources": [aid],
            }
        ]
        return self._turn(st, AgentTurn(reply, "answer", ev, asks_if_resolved=ask), calls)

    def _decline(
        self, st: ConvState, message: str, calls: list[Call], label: str, reason: str = "no answer in the help centre"
    ) -> AgentTurn:
        ev = [{"type": "decline", "predicted": label, "reason": reason}]
        text = "I'm sorry, I don't have a reliable answer to that. Would you like me to connect you with a member of our team?"
        self._call("answer", "small", self.models["system_prompt_tokens"] + tokens(message), tokens(text), calls)
        return self._turn(st, AgentTurn(text, "decline", ev), calls)

    def _handoff(self, st: ConvState, team: str, why: str, calls: list[Call], error: bool = False) -> AgentTurn:
        self.sys.create_ticket(st.id, st.account, team, redact(st.first_message))
        ev = [{"type": "handoff", "team": team, "why": why}]
        if error:
            ev.insert(0, {"type": "error"})
        text = f"I'm passing this to {TEAM_TEXT.get(team, 'our team')}. They'll reply here; you don't need to repeat anything."
        return self._turn(st, AgentTurn(text, "handoff", ev, done=True), calls)

    # -- procedures -------------------------------------------------------------------------------
    def _continue(self, st: ConvState, message: str, calls: list[Call], start: bool = False) -> AgentTurn:
        run = st.run
        assert run is not None
        conv, acct = st.id, st.account
        if run.waiting == "code":
            code = code_in(message)
            if code and self.sys.check_code(conv, acct, code):
                run.verified = True
                run.waiting = None
                run.at += 1
            else:
                run.attempts += 1
                if run.attempts >= 2:
                    st.run = None
                    return self._handoff(st, "billing", "identity could not be verified", calls)
                ev = [{"type": "verify", "retry": True}]
                return self._turn(
                    st,
                    AgentTurn("That code doesn't match. Please check the latest email from us and send the 6-digit code.", "verify", ev),
                    calls,
                )
        elif run.waiting:
            val = email_in(message) if run.waiting == "new_email" else message.strip()
            if not val:
                run.attempts += 1
                if run.attempts >= 2:
                    st.run = None
                    return self._handoff(st, "support", f"missing {run.waiting}", calls)
                return self._turn(
                    st,
                    AgentTurn(
                        "Sorry, I need that to continue. " + run.proc.steps[run.at]["question"],
                        "ask_slot",
                        [{"type": "ask_slot", "slot": run.waiting}],
                    ),
                    calls,
                )
            run.scope[run.waiting] = val
            run.waiting = None
            run.at += 1
        while run.at < len(run.proc.steps):
            s = run.proc.steps[run.at]
            ev_step = {"type": "procedure_step", "procedure": run.proc.name, "version": run.proc.version, "step": s["id"]}
            st.log.append(ev_step)
            t = s["type"]
            if t == "verify_identity":
                if run.verified:
                    run.at += 1
                    continue
                self.sys.send_verification(conv, acct)
                run.waiting = "code"
                return self._turn(
                    st,
                    AgentTurn(
                        "For your security I've sent a 6-digit code to the email address on your account. What's the code?",
                        "verify",
                        [ev_step, {"type": "verify"}],
                    ),
                    calls,
                )
            if t == "lookup":
                run.scope[s["into"]] = getattr(self.sys, s["call"])(conv, acct)
                run.at += 1
                continue
            if t == "condition":
                run.at = run.proc.index(s["then"] if procs.evaluate(s["if"], run.scope) else s["else"])
                continue
            if t == "ask":
                run.waiting = s["slot"]
                return self._turn(st, AgentTurn(s["question"], "ask_slot", [ev_step, {"type": "ask_slot", "slot": s["slot"]}]), calls)
            if t in ("action", "say"):
                if t == "action":
                    args = [run.scope[a] for a in s.get("args", [])]
                    res = getattr(self.sys, s["call"])(conv, acct, *args)
                    run.scope.update(res)
                text = _fmt(s["say"], run.scope)
                tin = self.models["system_prompt_tokens"] + tokens(message) + 120
                if not self._call("answer", self.cfg["models"]["answer_tier"], tin, tokens(text), calls):
                    return self._handoff(st, "support", "model provider unavailable", calls, error=True)
                ask = self.cfg["guidance"]["ask_if_resolved"]
                st.run = None
                ev = [
                    ev_step,
                    {"type": "result", "procedure": run.proc.name, "outcome": s.get("outcome", "done"), "article": s.get("article")},
                ]
                return self._turn(
                    st, AgentTurn(text + (" Is there anything else?" if ask else ""), "result", ev, asks_if_resolved=ask), calls
                )
            raise ValueError(f"unknown step type {t}")
        st.run = None
        return self._handoff(st, "support", "procedure ended without a result", calls)

    def _turn(self, st: ConvState, turn: AgentTurn, calls: list[Call]) -> AgentTurn:
        turn.calls = calls
        st.last_kind = turn.kind
        return turn


def _fmt(template: str, scope: dict[str, Any]) -> str:
    def rep(m: re.Match[str]) -> str:
        cur: Any = scope
        for part in m.group(1).split("."):
            cur = cur[part]
        return f"{cur:.2f}" if isinstance(cur, float) else str(cur)

    return re.sub(r"\{([\w.]+)\}", rep, template)
