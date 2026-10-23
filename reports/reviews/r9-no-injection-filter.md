# Release review: r9-no-injection-filter

Drop the prompt-injection filter (it adds latency).

**Decision: do not ship** (stopped at backtest)

- resolution gain not established (95% interval -0.007 to +0.096)
- hallucination may rise (upper bound +0.036)

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `safety.injection_filter` | True | False |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 97.2% | 95% |
| personalisation | no | 42.3% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |

## Backtest (1000 replayed conversations, 150 human-labelled, eval cost €789)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.5820 | 0.5851 | +0.0030 | -0.0000 to +0.0061 | judges |
| judged_hallucination | 0.0977 | 0.0981 | +0.0004 | +0.0002 to +0.0006 | judges |
| calibrated_resolution | 0.5199 | 0.5647 | +0.0448 | -0.0066 to +0.0963 | judges + human labels (PPI) |
| calibrated_hallucination | 0.1743 | 0.1810 | +0.0068 | -0.0225 to +0.0361 | judges + human labels (PPI) |
| confirmed | 0.3230 | 0.3230 | +0.0000 | +0.0000 to +0.0000 | observed |
| handoff | 0.2710 | 0.2910 | +0.0200 | +0.0113 to +0.0287 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0043 | 0.0043 | +0.0001 | +0.0000 to +0.0001 | observed |
| latency_p95_s | 5.5631 | 5.5757 | +0.0126 | -0.1954 to +0.3869 | observed, bootstrap |
