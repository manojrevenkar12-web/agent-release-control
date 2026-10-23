# agent-release-control

**Release control for an AI customer-support agent: every change is a versioned release that goes
through static checks, eval suites, a backtest with calibrated judges, an A/B test and a staged
rollout, with SLOs, alerts and cost tracked in production. A simulated world with hidden truth
measures how often that shipping process itself makes the wrong call.**

The agent answers from a help centre (plan-aware for Free, Pro and Business customers), runs
multi-step procedures that act on accounts (refunds, cancellations, email changes, behind identity
verification), hands off to the right team, and refuses prompt injections. A router sends unclear
messages from a small model tier to a large one. Every reply records what it answered from and the
model calls it made, with tokens, € cost and latency.

Most evaluation setups grade one instrument with another: judges with A/B tests, A/B tests with
monitors. Here every simulated conversation has a known outcome (was the need met, was anything
false said, was anything unsafe done), hidden from the shipping side behind one interface. So each
instrument can be checked against the truth, and so can the whole process.

| Area | What is here |
|---|---|
| **Releases** | Everything that changes behaviour (routing, retrieval, personalisation, procedure versions, guidance, safety) in one YAML file per release, validated, diffable, fingerprinted ([config/releases](config/releases), [docs/RELEASES.md](docs/RELEASES.md)) |
| **Agent** | Small→large router, BM25 retrieval with an agreement check, plan-aware answers, procedures as YAML step graphs with a safe expression language, handoffs, injection filter, redaction ([src/arc/agent](src/arc/agent)) |
| **Release review** | Static checks (no write path skips verification), blocking eval suites, backtest on replayed conversations with judges corrected by human labels (PPI), A/B test sized by power analysis and randomised by account, staged rollout with health checks and rollback; a failing bundle is split into the changes worth proposing again ([review.py](src/arc/review.py), [docs/RELEASE_REVIEW.md](docs/RELEASE_REVIEW.md)) |
| **Judges** | A learned judge trained on 1,500 reviewed production conversations, a rubric judge, an optional Claude judge (`ARC_JUDGE=claude`), combined in a panel with a disagreement signal ([evals](src/arc/evals)) |
| **Operations** | Availability and latency SLOs with multi-window burn-rate alerts, a Bernoulli CUSUM on resolution, AI cost per conversation; a drill injects five incidents into a fortnight of traffic ([ops](src/arc/ops), [config/slo.yaml](config/slo.yaml), [docs/RUNBOOK.md](docs/RUNBOOK.md)) |
| **Cost** | What each router threshold and answer tier buys: resolution, € per extra resolution, p95 latency, within the latency SLO ([ops/cost.py](src/arc/ops/cost.py)) |
| **The process, measured** | 30 random candidate releases and two blind held-out sets, each put through four shipping policies and graded against the truth ([study/process.py](src/arc/study/process.py)) |
| **Serving** | FastAPI: conversations under any release, release diffs, a serving split between production and a candidate, reviews as jobs, Prometheus metrics, API keys with roles ([api.py](src/arc/api.py)) |
| **AI-first team assets** | `CLAUDE.md`/`AGENTS.md` invariants backed by tests, skills for release review and new eval suites, an incident-triage agent ([.claude](.claude)) |

## Results

From `arc run` ([reports/EVALUATION.md](reports/EVALUATION.md)); CI reruns a smaller version on
every push and `arc gate` fails the build when a check fails. All data is simulated.

The full results are in [reports/EVALUATION.md](reports/EVALUATION.md).

## Run it

```bash
pip install -e ".[dev]"
arc train                                   # understanding tiers and the learned judge, ~1 min
arc chat --release r2-personalised          # talk to the agent; it prints the verification code
arc diff r12-personalised-router            # what a release changes
arc review r12-personalised-router          # the whole review: static → suites → backtest → A/B → rollout
arc ops                                     # production drill and cost frontier
arc run                                     # everything, then the report and the gate (~25 min)
ARC_API_KEYS="dev:releaser" arc serve       # http://127.0.0.1:8000/docs
pytest -q -m "not slow"                     # seconds; `pytest -q` adds the simulation tests
```

```bash
curl -s -H 'X-API-Key: dev' -H 'Content-Type: application/json' \
  -d '{"account": 5, "message": "please refund my last payment"}' localhost:8000/conversations
```

## How it is built

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). In short: the shipping side (agent, review,
evals, experiments, monitors, API) talks to the world only through `platform.py`, which in
production would be replay infrastructure, the live router and the review queue. The simulator
behind it holds the truth; only the evaluation modules read it. `tests/test_truth_isolation.py`
checks the imports and runs a full release review with every truth field poisoned, so shipping
code that reads the truth fails loudly.

Decisions are recorded as ADRs in [docs/adr](docs/adr). How I would run a team on this is in
[docs/LEADING.md](docs/LEADING.md).

## What this does not show

- **The world is simulated.** Customers, phrasings, the help centre and the company systems are
  synthetic. The agent's own model calls are simulated with real price and latency profiles so that
  every run is reproducible and free; only the optional judge calls Claude. Effects are larger and
  cleaner than in real traffic, and real customers find failure modes no simulator has.
- **The understanding tiers are small classifiers standing in for LLMs**, so "small" and "large"
  differ in vocabulary and price, not in reasoning. The release-control machinery does not depend
  on what is behind the tiers.
- **Human labels are the truth plus 5% reviewer disagreement.** Real reviewers disagree more and
  in structured ways.
- **Held-out sets were written by an AI agent** that saw only the release documentation, not by a
  colleague. It was told to include risky shortcuts.
- **Thresholds were set by me**, and some (the alert thresholds, the 2pp A/B effect size) after
  looking at early runs on the dev data. The held-out sets were never used to set them.

## License

MIT
