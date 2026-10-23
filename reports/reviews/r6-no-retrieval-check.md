# Release review: r6-no-retrieval-check

Answer from the recognised intent without checking the passages.

**Decision: do not ship** (stopped at backtest)

- hallucination may rise (upper bound +0.027)

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `retrieval.require_agreement` | True | False |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 97.2% | 95% |
| personalisation | no | 36.8% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 97.5% | 90% |

## Backtest (1000 replayed conversations, 74 human-labelled, eval cost €409)

| Metric | Production | Candidate | Change | 95% interval | Method |
|---|---|---|---|---|---|
| judged_resolution | 0.5945 | 0.6202 | +0.0257 | +0.0170 to +0.0344 | judges |
| judged_hallucination | 0.0950 | 0.1150 | +0.0200 | +0.0143 to +0.0257 | judges |
| calibrated_resolution | 0.5945 | 0.6195 | +0.0250 | +0.0140 to +0.0360 | judges + human labels on changed conversations (PPI) |
| calibrated_hallucination | 0.0950 | 0.1140 | +0.0190 | +0.0114 to +0.0266 | judges + human labels on changed conversations (PPI) |
| confirmed | 0.3320 | 0.3470 | +0.0150 | +0.0056 to +0.0244 | observed |
| handoff | 0.2470 | 0.2320 | -0.0150 | -0.0230 to -0.0070 | observed |
| writes_without_verification | 0.0000 | 0.0000 | +0.0000 | +0.0000 to +0.0000 | action log |
| cost_per_conversation | 0.0041 | 0.0042 | +0.0001 | +0.0000 to +0.0001 | observed |
| latency_p95_s | 5.4950 | 5.6152 | +0.1202 | -0.1952 to +0.4579 | observed, bootstrap |
