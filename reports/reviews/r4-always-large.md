# Release review: r4-always-large

Use the large model for understanding and answers.

**Decision: do not ship** (stopped at backtest)

- resolution gain not established (95% interval -0.001 to +0.011)
- cost per conversation x1.94
- p95 latency x1.53

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `models.answer_tier` | small | large |
| `models.understand_tier` | small | large |

## Each change on its own

| Setting | Value | Passes offline | Why not |
|---|---|---|---|
| `models.answer_tier` | large | no | resolution gain not established (95% interval +0.000 to +0.000); cost per conversation x1.72; p95 latency x1.46 |
| `models.understand_tier` | large | no | resolution gain not established (95% interval -0.003 to +0.008) |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 98.9% | 95% |
| personalisation | no | 33.2% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 19 human-labelled, eval cost €134)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.5853 | 0.5850 | -0.0003 | -0.0047 to +0.0040 | judges |
| judged_hallucination | 0.0871 | 0.0892 | +0.0021 | +0.0007 to +0.0034 | judges |
| calibrated_resolution | 0.5853 | 0.5904 | +0.0051 | -0.0006 to +0.0108 | judges + human labels on changed conversations (PPI) |
| calibrated_hallucination | 0.0871 | 0.0893 | +0.0023 | -0.0005 to +0.0050 | judges + human labels on changed conversations (PPI) |
| confirmed | 0.3230 | 0.3230 | +0.0000 | -0.0039 to +0.0039 | observed |
| handoff | 0.2480 | 0.2500 | +0.0020 | -0.0035 to +0.0075 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0041 | 0.0080 | +0.0039 | +0.0037 to +0.0041 | observed |
| latency_p95_s | 5.4130 | 8.2853 | +2.8723 | +2.5459 to +3.1476 | observed, bootstrap |
