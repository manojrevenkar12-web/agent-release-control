# Release review: r13-small-only

Never call the large model (cost saving).

**Decision: do not ship** (stopped at suites)

- escalations suite: 81.1% passed, needs 95%

## Changes from r1-prod

| Setting | From | To |
|---|---|---|
| `models.escalate_below` | 0.6 | 0.0 |

## Eval suites

| Suite | Blocking | Passed | Needs |
|---|---|---|---|
| escalations | yes | 81.1% | 95% |
| personalisation | no | 51.4% | 90% |
| safety | yes | 100.0% | 100% |
| unanswerable | no | 100.0% | 90% |
