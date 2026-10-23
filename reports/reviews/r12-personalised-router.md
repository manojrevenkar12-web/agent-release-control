# Release review: r12-personalised-router

Plan-aware answers and the 0.8 router together.

**Decision: ship**

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `models.escalate_below` | 0.6 | 0.8 |
| `personalisation.plan_aware` | False | True |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 98.9% | 95% |
| personalisation | no | 95.5% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 150 human-labelled, eval cost €789)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.6084 | 0.6889 | +0.0805 | +0.0657 to +0.0953 | judges |
| judged_hallucination | 0.0881 | 0.0342 | -0.0539 | -0.0630 to -0.0447 | judges |
| calibrated_resolution | 0.6084 | 0.7407 | +0.1323 | +0.1148 to +0.1497 | judges + human labels on changed conversations (PPI) |
| calibrated_hallucination | 0.0881 | -0.0433 | -0.1314 | -0.1430 to -0.1198 | judges + human labels on changed conversations (PPI) |
| confirmed | 0.3210 | 0.4000 | +0.0790 | +0.0623 to +0.0957 | observed |
| handoff | 0.2320 | 0.1570 | -0.0750 | -0.0922 to -0.0578 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0041 | 0.0045 | +0.0003 | +0.0003 to +0.0004 | observed |
| latency_p95_s | 5.5002 | 5.6799 | +0.1797 | +0.0009 to +0.5116 | observed, bootstrap |

## A/B test (21 days, 28,347 conversations, alpha 0.01)

Primary (resolved_obs): 0.6658 → 0.7782, +0.1124 (+0.0982 to +0.1266), p = 1.1e-92. Decision: ship.

| Guardrail | Control | Treatment | Change |
|---|---|---|---|
| hallucination_judged | 0.1493 | 0.0398 | -0.1095 |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 |
| csat | 3.6416 | 3.9597 | +0.3181 |
| cost_eur | 0.0042 | 0.0044 | +0.0003 |
| latency_p95_s | 5.5396 | 5.7514 | +0.2118 |

## Rollout

| Stage | Days | Treated | Failed checks |
|---|---|---|---|
| dark | 1 | 1,500 | none |
| 1% | 2 | 28 | none |
| 10% | 2 | 243 | none |
| 50% | 3 | 2,360 | none |
