# Release review: r11-long-context

Send eight passages with every answer.

**Decision: do not ship** (stopped at backtest)

- resolution gain not established (95% interval +0.000 to +0.000)

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `models.context_articles` | 3 | 8 |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 98.9% | 95% |
| personalisation | no | 32.3% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 0 human-labelled, eval cost €39)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.6003 | 0.6003 | +0.0000 | +0.0000 to +0.0000 | judges |
| judged_hallucination | 0.0915 | 0.0915 | +0.0000 | +0.0000 to +0.0000 | judges |
| calibrated_resolution | 0.6003 | 0.6003 | +0.0000 | +0.0000 to +0.0000 | judges + human labels on changed conversations (PPI) |
| calibrated_hallucination | 0.0915 | 0.0915 | +0.0000 | +0.0000 to +0.0000 | judges + human labels on changed conversations (PPI) |
| confirmed | 0.3270 | 0.3270 | +0.0000 | +0.0000 to +0.0000 | observed |
| handoff | 0.2370 | 0.2370 | +0.0000 | +0.0000 to +0.0000 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0041 | 0.0051 | +0.0010 | +0.0009 to +0.0011 | observed |
| latency_p95_s | 5.4027 | 5.8299 | +0.4272 | +0.2965 to +0.5922 | observed, bootstrap |
