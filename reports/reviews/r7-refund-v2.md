# Release review: r7-refund-v2

Refund procedure v2.

**Decision: do not ship** (stopped at suites)

- safety suite: 88.9% passed, needs 100%

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `procedures.refund` | v1 | v2 |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 97.8% | 95% |
| personalisation | no | 46.8% | 90% |
| safety | yes | 88.9% | 100% |
| unanswerable | no | 100.0% | 90% |
