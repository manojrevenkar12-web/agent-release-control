# How I would run an AI product workstream

This repository is a working version of the practices below, so each one points at the code or
report that shows it. The team I describe is a senior team of product engineers in a growing
office, working with PMs, AI designers and ML scientists on capabilities of a support agent
(procedures, personalisation, safety, skills).

## What ships, and how we know

- **A release is a file.** Everything that changes behaviour (model routing, retrieval, procedures,
  guidance, safety) is a versioned release that can be diffed, reviewed and rolled back
  (`config/releases/`, `arc diff`).
- **One review path for every change**, cheapest stage first: static checks, eval suites, a backtest
  with calibrated judges, an A/B test, a staged rollout (`docs/RELEASE_REVIEW.md`). Engineers can
  run all of it from a laptop in minutes before asking anyone for traffic.
- **Measure the measuring.** Judges are checked against human labels on every new release type; an
  A/A test runs with every change to the experiment code; the process study counts how often our
  own process ships something harmful or misses a real win (`reports/EVALUATION.md`). When the
  numbers say the process is too strict or too loose, we change the process deliberately, in a
  reviewed change to `config/`.
- **Held-out sets are written by someone who has not seen the code** and run once. Their first run is
  kept even when it is embarrassing (`reports/heldout/FIRST_RUN.md`).

## Operating what we own

- SLOs for availability and latency with burn-rate pages; resolution watched with a CUSUM because
  it has no error budget in the SRE sense; AI cost per conversation as a ticket (`config/slo.yaml`).
- Every alert has a runbook entry with one first action, usually a rollback (`docs/RUNBOOK.md`).
- A drill injects the incidents we fear into a fortnight of traffic every time the alerts change,
  and records time to detect and false alarms (`arc ops`).
- Cost is a product decision, not an afterthought: the router frontier shows what one extra
  resolution costs at each threshold (`reports/cost_frontier.json`), next to latency.

## AI-first as the default

- `CLAUDE.md` / `AGENTS.md` hold the invariants an agent (or a new hire) must not break, each
  backed by a test.
- Shared skills for the work we repeat (`.claude/skills/release-review`, `new-eval-suite`) and an
  incident-triage agent (`.claude/agents/incident-triage.md`).
- AI writes code and drafts; people own what ships. Review time goes to the decision a change
  makes (thresholds, policies, what a check reads), not to formatting, which CI handles.

## First 90 days

1. **Weeks 1–4: learn the system by shipping in it.** Pair with each engineer on a real change; take
   an on-call shift; read the last quarter's A/B tests and how their decisions were made.
2. **Weeks 5–8: one improvement to how we decide.** Usually the slowest or least trusted step:
   judge calibration on new capabilities, or the time from idea to first backtest.
3. **Weeks 9–12: grow the team.** A hiring loop with a practical exercise close to the work (review a
   release, find the flaw in an eval), interviewers calibrated on the same scorecard, and an
   onboarding path where a new engineer ships to production in the first two weeks.

## How I lead

I have led a team of 8 engineers inside a large bank: priorities, coaching, performance reviews
with ratings, and about 50 interviews. I stay hands-on: I build tools the team uses and review
the changes that matter most. I have not been an engineering manager of product engineers at a
fast-growing product company. I would expect to learn that context from the team, and to earn
trust by shipping alongside them first.
