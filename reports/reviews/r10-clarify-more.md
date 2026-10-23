# Release review: r10-clarify-more

Ask up to two clarifying questions, and ask more readily.

**Decision: do not ship** (stopped at backtest)

- resolution gain not established (95% interval -0.058 to +0.051)
- hallucination may rise (upper bound +0.051)

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `understanding.clarify_below` | 0.35 | 0.5 |
| `understanding.max_clarifications` | 1 | 2 |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 96.1% | 95% |
| personalisation | no | 40.0% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 150 human-labelled, eval cost €789)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.5929 | 0.5984 | +0.0054 | -0.0001 to +0.0109 | judges |
| judged_hallucination | 0.0962 | 0.0980 | +0.0018 | +0.0003 to +0.0032 | judges |
| calibrated_resolution | 0.5996 | 0.5958 | -0.0038 | -0.0582 to +0.0506 | judges + human labels (PPI) |
| calibrated_hallucination | 0.1349 | 0.1489 | +0.0141 | -0.0231 to +0.0512 | judges + human labels (PPI) |
| confirmed | 0.3460 | 0.3450 | -0.0010 | -0.0054 to +0.0034 | observed |
| handoff | 0.2400 | 0.2320 | -0.0080 | -0.0163 to +0.0003 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0041 | 0.0042 | +0.0001 | +0.0001 to +0.0002 | observed |
| latency_p95_s | 5.7301 | 5.7762 | +0.0461 | -0.2028 to +0.2801 | observed, bootstrap |
