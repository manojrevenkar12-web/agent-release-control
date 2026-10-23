# Release review: r5-strict-retrieval

Answer only with strong retrieval support (fewer wrong answers, more declines).

**Decision: do not ship** (stopped at backtest)

- resolution gain not established (95% interval -0.147 to -0.047)

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `retrieval.min_score` | 3.0 | 7.0 |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 95.6% | 95% |
| personalisation | no | 42.3% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 150 human-labelled, eval cost €789)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.5801 | 0.5021 | -0.0781 | -0.0926 to -0.0635 | judges |
| judged_hallucination | 0.0930 | 0.0737 | -0.0193 | -0.0247 to -0.0139 | judges |
| calibrated_resolution | 0.5906 | 0.4935 | -0.0971 | -0.1470 to -0.0471 | judges + human labels (PPI) |
| calibrated_hallucination | 0.1688 | 0.1319 | -0.0369 | -0.0602 to -0.0135 | judges + human labels (PPI) |
| confirmed | 0.3210 | 0.2750 | -0.0460 | -0.0614 to -0.0306 | observed |
| handoff | 0.2510 | 0.2870 | +0.0360 | +0.0241 to +0.0479 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0041 | 0.0040 | -0.0000 | -0.0001 to +0.0000 | observed |
| latency_p95_s | 5.3645 | 5.6320 | +0.2675 | +0.0405 to +0.4990 | observed, bootstrap |
