# 5. In a paired backtest, label only the conversations the candidate changed

Status: accepted (process v2)

Process v1 labelled a random sample of 150 replayed conversations for both releases. Most of them
were identical under both releases, so their labels carried only reviewer disagreement, and the
calibrated interval on a resolution change was about ±5pp. On the dev portfolio of 30 candidates
the review shipped nothing and missed six real wins between +0.6 and +4.4pp
(`reports/process_v1/`).

Where both releases produce the same conversation, the difference is zero for any judge and any
reviewer, so it needs no label. v2 spends the labels only on conversations that changed and scales
the estimate by the changed share (`ppi.paired_diff_changed`). For typical candidates (2–5% of
conversations change) the interval shrinks to about ±0.5–1pp at the same labelling cost.

Consequences: candidates that change most conversations (for example removing "Did that answer
your question?") still get wide intervals; that is honest, not a defect. The held-out set v1 was run
under v1 and retired; v2 was written blind for the new process.
