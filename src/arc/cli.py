"""arc: the command line.

arc train                      train the understanding tiers and the learned judge
arc review <release> [--offline]   run the release review against production
arc diff <release> [--against r1-prod]
arc chat [--release r1-prod] [--account 5]   talk to the agent
arc study [--candidates 30]    how often each shipping policy makes the wrong call
arc heldout                    run the blind held-out candidates (first run is kept)
arc ops                        production drill (incidents and alerts) and cost frontier
arc run [--quick]              everything above except heldout, then the report and the gate
arc report | arc gate          rebuild the report / re-check the gate from existing reports
arc serve [--port 8000]        HTTP API
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="arc", description="Release control for an AI support agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train")
    r = sub.add_parser("review")
    r.add_argument("release")
    r.add_argument("--baseline", default="r1-prod")
    r.add_argument("--offline", action="store_true", help="stop before the A/B test")
    r.add_argument("--seed", type=int, default=0)
    d = sub.add_parser("diff")
    d.add_argument("release")
    d.add_argument("--against", default="r1-prod")
    c = sub.add_parser("chat")
    c.add_argument("--release", default="r1-prod")
    c.add_argument("--account", type=int, default=5)
    s = sub.add_parser("study")
    s.add_argument("--candidates", type=int, default=30)
    s.add_argument("--truth", type=int, default=20000)
    s.add_argument("--seed", type=int, default=11)
    ho = sub.add_parser("heldout")
    ho.add_argument("--version", default=None, help="default: the latest set")
    sub.add_parser("ops")
    ru = sub.add_parser("run")
    ru.add_argument("--quick", action="store_true")
    ru.add_argument("--skip-train", action="store_true")
    sub.add_parser("report")
    sub.add_parser("gate")
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)

    if a.cmd == "train":
        from arc.train import train

        print(json.dumps(train(), indent=1))
    elif a.cmd == "review":
        from arc.agent.release import load
        from arc.platform import SimPlatform
        from arc.review import markdown, review

        rv = review(SimPlatform(), load(a.baseline), load(a.release), a.seed, online=not a.offline)
        print(markdown(rv))
        return 0 if rv.decision in ("ship", "ready for A/B test") else 1
    elif a.cmd == "diff":
        from arc.agent.release import load

        for k, (x, y) in load(a.release).diff(load(a.against)).items():
            print(f"{k}: {x} -> {y}")
    elif a.cmd == "chat":
        return _chat(a.release, a.account)
    elif a.cmd == "study":
        from arc.pipeline import study
        from arc.platform import SimPlatform

        study(a.candidates, a.truth, a.seed, SimPlatform())
    elif a.cmd == "heldout":
        from arc.pipeline import run_heldout
        from arc.platform import SimPlatform

        run_heldout(SimPlatform(), a.version)
    elif a.cmd == "ops":
        from arc.config import load as load_cfg
        from arc.pipeline import ops
        from arc.platform import SimPlatform

        c = load_cfg("pipeline")["full"]
        ops(c["drill_seeds"], c["frontier_conversations"], SimPlatform())
    elif a.cmd == "run":
        from arc.pipeline import run

        res = run("quick" if a.quick else "full", a.skip_train)
        _print_gate(res)
        return 0 if res["passed"] else 1
    elif a.cmd == "report":
        from arc.report import write_report

        write_report()
    elif a.cmd == "gate":
        from arc.gate import gate

        res = gate()
        _print_gate(res)
        return 0 if res["passed"] else 1
    elif a.cmd == "serve":
        import uvicorn

        uvicorn.run("arc.api:app", host=a.host, port=a.port)
    return 0


def _print_gate(res: dict) -> None:
    for c in res["checks"]:
        print(f"{'PASS' if c['passed'] else 'FAIL'}  {c['check']}: {c['detail']}")
    print("gate:", "passed" if res["passed"] else "FAILED")


def _chat(release: str, account: int) -> int:
    from arc.agent.core import Agent
    from arc.agent.release import load
    from arc.runner import env

    e = env()
    ag = Agent(load(release), e.nlu, e.world.systems)
    st = ag.start("cli", account)
    acc = e.world.systems.account(account)
    print(f"Talking to {release} as account {account} ({acc.plan} plan). Empty line to stop.")
    while True:
        try:
            msg = input("you> ").strip()
        except EOFError:
            break
        if not msg:
            break
        t = ag.respond(st, msg)
        print(f"agent> {t.text}")
        if t.kind == "verify":
            print(f"       (the code emailed to the owner is {e.world.systems.code_for('cli', account)})")
        if t.done:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
