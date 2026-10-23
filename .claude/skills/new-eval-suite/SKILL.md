---
name: new-eval-suite
description: Add an eval suite (targeted simulations with checks) for a new agent capability or a bug that reached customers; use when a procedure, intent or failure mode has no suite yet.
---

# New eval suite

1. Find the gap: which intent or procedure, and which customers (plan, injection, impostor). Look at
   `config/suites/*.yaml` for the shape and `src/arc/evals/suites.py` for the checks that exist.
2. Prefer existing checks (`no_write_without_verification`, `no_writes`, `refund_within_policy`,
   `answer_matches_plan`, `no_answer`, `{handoff: team}`). A new check must read only what the
   company can see (events, action log, account attributes), never the simulator's truth.
3. Write the suite file with `blocking` and `min_pass_rate`. A blocking suite needs a pass rate that
   production meets today: run `python -c "from arc import ship; ..."` on `r1-prod` and on a release
   that should fail, and show both numbers.
4. Add a test in `tests/test_shipping.py` that the suite passes production and fails the bad release.
