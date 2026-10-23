"""Plays one conversation between the agent and a simulated customer."""

from __future__ import annotations

from collections.abc import Iterable

from arc.agent.core import Agent
from arc.sim.customer import Customer
from arc.sim.world import Spec, World
from arc.types import Outcome

MAX_TURNS = 12


def run(agent: Agent, spec: Spec, world: World) -> Outcome:
    cust = Customer(spec, world, agent.sys, agent.r.id)
    st = agent.start(spec.id, spec.account)
    msg = cust.first_message()
    cust.o.transcript.append({"role": "customer", "text": msg})
    for _ in range(MAX_TURNS):
        turn = agent.respond(st, msg)
        reply = cust.react(turn)
        if reply is None or turn.done:
            break
        msg = reply
    o = cust.finish()
    agent.sys.forget(spec.id)
    return o


def run_many(agent: Agent, specs: Iterable[Spec], world: World) -> list[Outcome]:
    return [run(agent, s, world) for s in specs]
