# Release review

`arc review <release>` (or `POST /reviews`) runs these stages against production and stops at the
first one that fails. Thresholds are in `config/review.yaml` and `config/experiments.yaml`.

| Stage | What it checks | Fails when | Cost / time |
|---|---|---|---|
| Static | settings in range; every procedure path that writes passes identity verification first | any problem | seconds |
| Eval suites | targeted simulations: refunds, cancellations, email changes, impostors, injections (safety, blocking); bugs, privacy, phishing reach the right team (escalations, blocking); plan-specific answers; unanswerable questions | a blocking suite under its pass rate | ~1 min |
| Backtest | 1,000 replayed conversations through both releases; two judges; up to 150 of the conversations the candidate changed labelled by people for both releases; PPI-corrected difference | the 95% interval of the resolution gain touches 0, hallucination may rise ≥1pp, any write without verification, cost ×1.3, p95 latency ×1.25 | ~€790 of judging and labelling |
| A/B test | randomised by account, sized for a 2pp change at alpha 1% and 80% power, whole weeks; delta-method intervals; guardrails on monitor-judged hallucination, writes without verification, CSAT, cost, latency | no significant gain, a guardrail breached, or a sample-ratio mismatch | 21 days |
| Rollout | dark (shadow) → 1% → 10% → 50% → 100% with health checks; rollback on failure | writes without verification, error rate, p95 latency, judged hallucination, resolution drop after 2,000 treated | 8 days |

## Reading a review

- Look at **calibrated** metrics, not **judged** ones. Judges are trained on production
  conversations and can be blind to a new release's kind of mistake (see `reports/EVALUATION.md`,
  Judges). The labelled sample corrects them.
- A release that passes offline but shows no significant gain in the A/B test is **not** shipped.
  The process trades missed small wins (under the 2pp it is powered for) for few false ships; the
  process study measures how many wins that costs.
- A stopped rollout is a rollback, not a failure of the process: dark and 1% stages exist so that
  rare problems (a refund without verification on a small charge) meet few customers.
