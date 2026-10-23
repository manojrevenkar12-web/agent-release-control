# 1. Evaluate the evaluation with a simulator that knows the truth

Status: accepted

We need to know how often our shipping process makes the wrong call, which production data cannot
tell us: every instrument (judges, A/B tests, monitors) is graded by the others. We build a
simulated customer-support world where each conversation's real outcome is known, and keep the
shipping side behind an interface (`platform.py`) that does not expose it.

Consequences: results are only as good as the simulator, so the README states what it leaves out.
The interface is the seam where real replay infrastructure, live traffic and a review queue plug in.
