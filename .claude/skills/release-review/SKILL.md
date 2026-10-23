---
name: release-review
description: Review a candidate release of the support agent before it ships, the way the AI group does it; use when someone proposes a change to a release file or asks whether a release can ship.
---

# Release review

1. Read the candidate file in `config/releases/` and run `arc diff <release>`. Say in one line what
   changes for customers, not which keys changed.
2. Run `arc review <release> --offline`. It stops at the first failing stage:
   - **static**: a setting is out of range or a procedure can write before verifying identity. This
     is never waived; fix the procedure.
   - **suites**: a blocking suite (safety, escalations) is below its pass rate. Open the failing
     scenarios in the JSON and quote one conversation.
   - **backtest**: read `calibrated_resolution` and `calibrated_hallucination` (judges corrected with
     human labels), not `judged_*`. A judged gain without a calibrated one is not a gain.
3. If the offline review passes, say how long the A/B test will run (the plan is in the output:
   power analysis, alpha 1%, whole weeks) and what would stop the rollout.
4. Write the result as: decision, the one number that decided it with its interval, the risk that
   remains, and what would change the decision. Link `reports/reviews/<release>.md` if it exists.

Do not lower a threshold in `config/review.yaml` or `config/experiments.yaml` to get a release
through; that is a separate change with its own review.
