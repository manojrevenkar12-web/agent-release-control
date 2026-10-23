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

**How often does the shipping process make the wrong call?** 30 candidate releases, each a random
change to production (the personalised release) of the kind a team proposes in a quarter, put
through five policies. True effects measured on 20,000 conversations: 6 are better, 20 harmful
(17 lower resolution by 0.5pp or more, 5 act unsafely on accounts, some both), 4 make no difference.

| Policy | Shipped | Truly better | Harmful | Unsafe | Wins missed | True resolution gained |
|---|---|---|---|---|---|---|
| P0: a person reads 20 replayed conversations | 7 | 1 | **4** | **2** | 5 | −0.8pp |
| P1: LLM-judge backtest, ship if judged better | 7 | 5 | 0 | 0 | 1 | +6.7pp |
| P2: static checks, eval suites, calibrated backtest | 3 | 3 | 0 | 0 | 3 | +3.4pp |
| P3: P2, then A/B test (2pp, alpha 1%) and rollout | **0** | 0 | 0 | 0 | 6 | 0 |
| P4: P2, then staged rollout without the A/B test | 3 | 3 | 0 | 0 | 3 | +3.4pp |

- **Process v1 shipped nothing and missed six real wins.** Its backtest labelled 150 random
  conversations, most of them identical under both releases, so the calibrated interval was about
  ±5pp ([reports/process_v1](reports/process_v1)). **Process v2 labels only the conversations a
  candidate changed**: the same 150 labels give intervals of about ±0.5–1pp
  ([ADR 0005](docs/adr/0005-label-only-changed-conversations.md)).
- **Then the A/B test became the bottleneck.** Powered for 2pp over 21 days, it rejected all three
  wins (+0.7 to +1.6pp) the backtest had already established. Sending those straight to the staged
  rollout (P4) shipped all three and nothing harmful. P4 is a dev-set result; it has not had a
  held-out run yet.
- **Judges alone did well here, for a reason that does not generalise.** From the personalised
  baseline the agent rarely says anything false, so the judges' blind spot (below) has little to
  hide. P1 runs no safety checks: one of its wins fails 5.6% of the escalation suite (bug, privacy and
  security reports reaching the right team), which blocks it in P2. Reading 20 conversations shipped
  two releases that act unsafely on accounts (refunds outside policy, refunds without verification).

**Blind held-out candidates.** Ten releases written by an agent that saw only
[docs/RELEASES.md](docs/RELEASES.md), run once; the first runs are kept as written
([v1](reports/heldout/v1/FIRST_RUN.md), [v2](reports/heldout/v2/FIRST_RUN.md),
[what they taught](docs/HELDOUT.md)).

| Set (process) | Full process shipped | Truly better among them | Harmful or unsafe shipped | Wins missed |
|---|---|---|---|---|
| v1 (process v1, against `r1-prod`) | 0 | 0 | 0 | 1 (+0.6pp) |
| v2 (process v2, against `r2-personalised`) | 1 | 1 (+1.6pp) | 0 | 0 |

In v1 the biggest win (+14.7pp, plan-aware answers) came bundled with a large-tier change that
cost ×1.8 and added 50% p95 latency. The review now splits a failing bundle into the changes that
pass on their own, and names the plan-aware change.

**Judges drift with the release they score.** The learned judge (trained on 1,500 reviewed
production conversations) ranks production well: AUC 0.92 for resolution, 0.96 for hallucination.
On the personalised release its hallucination AUC is **0.48**, and it reports 4.2% hallucination
where reviewers find 1.9%. That is why backtests are calibrated with human labels.

**Release reviews of known changes** ([reports/reviews](reports/reviews)): the personalised
release ships (A/B +11.2pp, 95% interval 9.8–12.7, 28,000 conversations); the refund window typo
stops at the safety suite in a second; skipping verification for small refunds stops at the static
check before any traffic; always using the large tier stops at the backtest (cost ×1.9, p95
latency ×1.5, no gain); an A/A test does not ship (p = 0.86).

**Production drill** (five incidents in a fortnight, three seeds): every incident is alerted on
while it is still happening. The provider latency spike pages in 25–30 min; the error burst
in 5–40 min; the large-tier outage in 20–45 min; the help-centre search outage is caught by the
resolution CUSUM in 74–94 min; a bad config push raises the cost ticket in 15–40 min. There are
**0 false alarms** on the same fortnights without incidents.

**Cost.** AI spend is about €0.004 per conversation against €4 for a person, so the router
threshold is a latency decision more than a cost one. Moving the threshold from 0.6 to 0.7
costs €0.05 per extra resolution, and 0.8 to 0.9 costs €1.60. Answering on the large tier
adds 2.5s p95 for no gain and breaks the latency SLO above a 0.3 threshold
([cost frontier](reports/EVALUATION.md#router-threshold-and-cost)).

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
