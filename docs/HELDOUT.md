# What the held-out candidates taught

## Set v1 (process v1)

Ten candidate releases were written by an agent that saw only `docs/RELEASES.md`, `_base.yaml` and
`r1-prod.yaml`, and were run once (`reports/heldout/FIRST_RUN.md`, not regenerated). The shipping
process was not tuned on them. This page is what we read from that first run.

1. **The full process shipped none of the ten, and that was nearly right.** Five are harmful (two of them
   unsafe), three make no material difference, and one is the bundle in point 2. One (`h10-containment-push`, +0.6pp true resolution) is a
   small real win. The backtest cannot see a change that small (its 95% interval is about ±5pp), and
   neither can a 21-day A/B test powered for 2pp. Missing it costs about 0.6pp. Shipping the
   no-difference ones would have cost churn and risk for nothing.
2. **The biggest win was hidden inside a bundle.** `h01` turns on plan-aware answers (+14.7pp true
   resolution) and moves answers to the large tier with more context (AI cost ×1.8, p95 latency
   ×1.5, no quality gain). The review was right to block the bundle on cost and latency, but it only
   said "no", which would have sent the proposer away. **Change made after this run:** when a
   release with several changes fails the backtest, the review now tries each change on its own and
   lists the ones that pass (`review.split`). On `h01` that names `personalisation.plan_aware`. This
   adds information to the review and does not change any decision, so the first-run table still
   describes the current process.
3. **Reading 20 conversations is how unsafe changes ship.** "P0 read 20" shipped `h05` (a 30-day
   refund window: 375 refunds outside policy in the truth run) because 20 conversations looked fine.
   The safety suite stops it in about a second.
4. **Judges alone ship cost for nothing.** "P1 judges" shipped five: the small win, the costly `h01`
   bundle, and three no better than production, including `h09` (always escalate: AI cost ×1.44 for
   +0.1pp).
5. **The labelling budget, not the judge, limits what offline review can see.** With 150 human
   labels per release the calibrated interval is about ±5pp, so offline review only passes large
   changes; the rest wait for a decision on whether a bigger labelled sample is worth its cost
   (300 labels is about €750 per backtest).

The dev-set process study said the same as point 5 more loudly (none of 30 candidates shipped, six
real wins missed; `reports/process_v1/`). Process v2 labels only the conversations a candidate
changed (`docs/adr/0005-label-only-changed-conversations.md`). Because the process changed, set v1
was retired to `config/releases/heldout_v1/` and a new set, v2, was written blind against the new
production release and run once.
