# Release review: r3-router-0.8

Ask the large model whenever the small one is less than 80% sure.

**Decision: do not ship** (stopped at A/B test)

- no significant gain: do not ship

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

## Backtest (1000 replayed conversations, 18 human-labelled, eval cost €129)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.6143 | 0.6174 | +0.0031 | -0.0010 to +0.0072 | judges |
| judged_hallucination | 0.0899 | 0.0913 | +0.0014 | +0.0004 to +0.0024 | judges |
| calibrated_resolution | 0.6143 | 0.6220 | +0.0077 | +0.0027 to +0.0127 | judges + human labels on changed conversations (PPI) |
| calibrated_hallucination | 0.0899 | 0.0909 | +0.0010 | -0.0014 to +0.0034 | judges + human labels on changed conversations (PPI) |
| confirmed | 0.3490 | 0.3500 | +0.0010 | -0.0034 to +0.0054 | observed |
| handoff | 0.2310 | 0.2300 | -0.0010 | -0.0054 to +0.0034 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0039 | 0.0046 | +0.0007 | +0.0006 to +0.0008 | observed |
| latency_p95_s | 5.5680 | 5.8408 | +0.2728 | -0.0721 to +0.6484 | observed, bootstrap |

## A/B test (21 days, 28,347 conversations, alpha 0.01)

Primary (resolved_obs): 0.6704 → 0.6687, -0.0017 (-0.0172 to +0.0137), p = 0.77. Decision: no significant gain: do not ship.

| Guardrail | Control | Treatment | Change |
|---|---|---|---|
| hallucination_judged | 0.1486 | 0.1416 | -0.0071 |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 |
| csat | 3.6783 | 3.6441 | -0.0342 |
| cost_eur | 0.0041 | 0.0046 | +0.0005 |
| latency_p95_s | 5.5542 | 5.7814 | +0.2272 |
