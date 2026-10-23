# Release review: r3-router-0.8

Ask the large model whenever the small one is less than 80% sure.

**Decision: do not ship** (stopped at backtest)

- resolution gain not established (95% interval -0.031 to +0.029)

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `models.escalate_below` | 0.6 | 0.8 |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 96.1% | 95% |
| personalisation | no | 40.5% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 150 human-labelled, eval cost €789)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.6143 | 0.6174 | +0.0031 | -0.0010 to +0.0072 | judges |
| judged_hallucination | 0.0899 | 0.0913 | +0.0014 | +0.0004 to +0.0024 | judges |
| calibrated_resolution | 0.6257 | 0.6249 | -0.0008 | -0.0307 to +0.0291 | judges + human labels (PPI) |
| calibrated_hallucination | 0.1530 | 0.1205 | -0.0324 | -0.0613 to -0.0036 | judges + human labels (PPI) |
| confirmed | 0.3490 | 0.3500 | +0.0010 | -0.0034 to +0.0054 | observed |
| handoff | 0.2310 | 0.2300 | -0.0010 | -0.0054 to +0.0034 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0039 | 0.0046 | +0.0007 | +0.0006 to +0.0008 | observed |
| latency_p95_s | 5.5680 | 5.8408 | +0.2728 | -0.0721 to +0.6484 | observed, bootstrap |
