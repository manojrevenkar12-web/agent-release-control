# Runbook

## Alerts (config/slo.yaml)

| Alert | Severity | Likely cause | First action |
|---|---|---|---|
| availability burn rate | page | model provider errors (both tiers failing) | check provider status; if a candidate is serving, set its share to 0 |
| latency burn rate | page / ticket | provider slow, or the large tier unavailable and every call retrying | fall back to the small tier for understanding (`escalate_below: 0`) as a hot release |
| resolution drop (CUSUM) | page | help-centre search down, a bad config push, an article change | `GET /serving`; roll back any candidate; check retrieval health |
| AI cost per conversation | ticket | routing change (more large-tier calls), longer contexts | diff what is serving against production; roll back |

Rolling back is `PUT /serving {"production": "<previous>", "candidate": null, "share": 0}`; it
takes effect on the next conversation. The drill (`arc ops`) replays each of these incidents and
records how long the alerts took; `reports/EVALUATION.md` has the numbers.

## Running locally

```bash
pip install -e ".[dev]"
arc train                       # about a minute
arc chat --release r2-personalised --account 5
arc review r12-personalised-router --offline
ARC_API_KEYS="dev:releaser" arc serve
```

## Rebuilding the reports

`arc run` (about 30 minutes) rewrites everything under `reports/` except
`reports/heldout/first_run.json` and `FIRST_RUN.md`, which are written once.
