# Architecture

```
                       config/releases/*.yaml  (everything that changes behaviour)
                                   │
 ┌──────────── shipping side (sees what a support team sees) ───────────────────────────────┐
 │                                                                                         │
 │  agent/           understand (small → large router) → answer from the help centre        │
 │                   (retrieval + agreement check, plan-aware), run a procedure (YAML step   │
 │                   graph, verify before write), hand off, or decline. Every reply carries  │
 │                   events and model calls (tokens, € cost, latency).                       │
 │                                                                                         │
 │  review.py        static checks → eval suites → backtest → A/B test → staged rollout      │
 │   ├ evals/        lint, suites, judges (learned, rubric, optional Claude), PPI, backtest  │
 │   ├ experiment/   power analysis, account-level assignment, delta-method analysis         │
 │   └ ship.py       suite runner, backtest, A/B, rollout with health checks and rollback    │
 │  ops/monitor.py   SLO burn-rate alerts, resolution CUSUM, cost per conversation           │
 │  api.py           conversations, releases and diffs, serving split, reviews, /metrics     │
 │                                                                                         │
 └──────────────────────────────┬──────────────────────────────────────────────────────────┘
                                │  platform.py: run a release on conversations, live traffic,
                                │  human review queue, account plans. Nothing else crosses.
 ┌──────────────────────────────┴──── simulator (knows the truth) ──────────────────────────┐
 │  sim/world.py     intents, phrasings (two banks: the second is how next quarter's        │
 │                   customers talk), accounts and plans, injections, impostors             │
 │  sim/customer.py  a customer with patience, who confirms, rephrases, asks for a person,  │
 │                   leaves, reopens, answers CSAT; and the truth: was the need met, was    │
 │                   anything false said, was anything unsafe done                          │
 │  sim/review.py    human labels = truth with reviewer disagreement                         │
 └──────────────────────────────┬──────────────────────────────────────────────────────────┘
                                │
 ┌──────────────────────────────┴──── evaluation (reads the truth) ─────────────────────────┐
 │  study/releases.py  what every release really does                                       │
 │  study/process.py   how often each shipping policy ships something harmful or misses a   │
 │                     real win, on a portfolio of random candidates and a blind held-out set │
 │  ops/drill.py       incidents injected into a fortnight of traffic: detected? how fast?  │
 │  ops/cost.py        router threshold × answer tier: resolution, € per extra resolution   │
 └──────────────────────────────────────────────────────────────────────────────────────────┘
```

## Why a simulator with hidden truth

A real support agent's shipping process is graded by the same instruments it uses: judges, A/B
tests, monitors. If the judge is biased, the A/B test underpowered or the alert slow, nothing tells
you. Here every conversation has a known outcome, so each instrument can be checked against the
truth: the judge's AUC on a new release, the A/B test's false-positive rate (A/A), each shipping
policy's false-ship rate, each alert's time to detect.

The shipping side cannot see that truth. It talks to `platform.SimPlatform`, which in production
would be replay infrastructure, the live router and the review queue. `tests/test_truth_isolation.py`
checks imports statically and runs a full release review with every truth field poisoned.

## Reproducibility

Every run is seeded. Comparisons use common random numbers: the same customers, first messages and
customer behaviour for both releases, so a paired difference is the release's effect rather than
traffic noise. The agent's model calls are simulated with the latency, error and price profile in
`config/models.yaml`; judges can call Claude (`ARC_JUDGE=claude`).
