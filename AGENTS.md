# Working in this repository

- `pytest -q -m "not slow"` runs in seconds; `pytest -q` adds the simulation tests (trains the models
  once if missing). `arc run --quick` is what CI runs; `arc run` rebuilds the committed reports.
- Shipping code (`ship.py`, `review.py`, `evals/`, `experiment/`, `ops/monitor.py`, `api.py`, `agent/`)
  decides from what a support team can see. It never imports `arc.sim` or `arc.study` and never reads
  an `Outcome`'s truth fields; `tests/test_truth_isolation.py` runs the review on poisoned truth.
- Thresholds live in `config/` (review.yaml, experiments.yaml, slo.yaml, release.yaml), not in code.
- Everything that changes the agent's behaviour is a release in `config/releases/`. Do not change
  behaviour in code behind a flag that a release cannot see.
- Never change the shipping process to get a better result on `config/releases/heldout/`. Its first
  run is `reports/heldout/FIRST_RUN.md` and is not rewritten. If you study those failures, move the
  set into the dev releases and have someone who has not seen the code write a new held-out set
  from `docs/RELEASES.md` only.
- The agent's own model calls are simulated (reproducible, free); only judges may call Claude
  (`ARC_JUDGE=claude`). Conversations sent to a model are redacted first (`agent/safety.redact`).
