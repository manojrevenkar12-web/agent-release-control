# 2. Correct judge scores with human labels (PPI) before deciding

Status: accepted

LLM and learned judges are cheap and biased, and their bias changes with the release they score: a
judge trained on production does not know a candidate's new failure modes. Backtest decisions use
prediction-powered inference: judge scores on all replayed conversations, corrected by the mean
judge error on a random labelled sample of the same conversations, for both releases.

Consequences: each backtest costs 300 human labels (about €750). Judged-only metrics are still
reported, because the difference between judged and calibrated is itself a signal that the judge
needs retraining.
