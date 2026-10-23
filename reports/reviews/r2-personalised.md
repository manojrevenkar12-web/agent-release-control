# Release review: r2-personalised

Answers use the section of the help article for the customer's plan.

**Decision: ship**

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `personalisation.plan_aware` | False | True |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 97.8% | 95% |
| personalisation | no | 95.9% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 150 human-labelled, eval cost €789)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.6138 | 0.6950 | +0.0813 | +0.0671 to +0.0954 | judges |
| judged_hallucination | 0.0886 | 0.0331 | -0.0556 | -0.0647 to -0.0464 | judges |
| calibrated_resolution | 0.6126 | 0.7514 | +0.1389 | +0.0842 to +0.1935 | judges + human labels (PPI) |
| calibrated_hallucination | 0.1529 | 0.0184 | -0.1345 | -0.1758 to -0.0933 | judges + human labels (PPI) |
| confirmed | 0.3390 | 0.4190 | +0.0800 | +0.0632 to +0.0968 | observed |
| handoff | 0.2340 | 0.1570 | -0.0770 | -0.0935 to -0.0605 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0041 | 0.0039 | -0.0002 | -0.0002 to -0.0001 | observed |
| latency_p95_s | 5.4336 | 5.3475 | -0.0861 | -0.3072 to +0.1493 | observed, bootstrap |

## A/B test (21 days, 28,347 conversations, alpha 0.01)

Primary (resolved_obs): 0.6663 → 0.7788, +0.1125 (+0.0983 to +0.1267), p = 1.7e-92. Decision: ship.

| Guardrail | Control | Treatment | Change |
|---|---|---|---|
| hallucination_judged | 0.1746 | 0.0415 | -0.1331 |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 |
| csat | 3.6570 | 3.9536 | +0.2966 |
| cost_eur | 0.0041 | 0.0039 | -0.0002 |
| latency_p95_s | 5.5744 | 5.5335 | -0.0409 |

## Rollout

| Stage | Days | Treated | Failed checks |
|---|---|---|---|
| dark | 1 | 825 | none |
| 1% | 2 | 26 | none |
| 10% | 2 | 320 | none |
| 50% | 3 | 1,911 | none |
