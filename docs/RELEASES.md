# Writing a release

A release is one YAML file in `config/releases/`. It starts from `_base.yaml` and overrides only the
settings it changes. Everything that changes how the agent behaves is in a release, so two releases
can be compared, backtested, A/B tested and rolled out, and production can be rolled back to the
previous one.

```yaml
id: r2-personalised
description: Answers use the section of the help article for the customer's plan.
personalisation: {plan_aware: true}
```

## What the agent does with a message

1. Closing messages ("thanks, that's all") end the conversation; a request for a person (after the
   first message) hands off to the support team.
2. With `safety.injection_filter`, messages that try to give the agent new instructions are refused.
3. If a procedure is waiting for an answer (a verification code, a new email address), the message
   goes to the procedure.
4. If the customer says the last answer did not help, that counts as a failure; after
   `guidance.offer_human_after_failures` failures the agent hands off.
5. Otherwise the message is understood: the `models.understand_tier` model classifies it and gives a
   confidence. If that tier is `small` and the confidence is under `models.escalate_below`, the
   `large` tier is asked as well and its reading wins. The large tier knows more ways of saying
   things and costs about three times as much per token, and is slower.
6. Below `understanding.clarify_below` confidence (or when the message is vague) the agent asks
   one clarifying question, up to `understanding.max_clarifications` times, then hands off.
7. Then, depending on what the customer wants:
   - **a question the help centre answers**: the help centre is searched (`retrieval.top_k`
     passages). With `retrieval.require_agreement`, the agent only answers if the article it intends
     to use is among them with at least `retrieval.min_score`; otherwise it says it has no reliable
     answer and offers a person. The answer is written by the `models.answer_tier` model with
     `models.context_articles` passages in its context (more passages: more tokens, more cost, more
     latency). With `personalisation.plan_aware` it uses the part of the article for the customer's
     plan (Free, Pro or Business); otherwise the general text.
   - **something to do on the account** (refund, cancel, change email, resend an invoice, update the
     card): a procedure runs (see below).
   - **something only a team can do** (bugs, legal, enterprise sales, ...): handed off to that team.
   - **anything else**: the agent says it does not have an answer and offers a person.
8. With `guidance.ask_if_resolved`, answers end with "Did that answer your question?".

When a model call fails, the agent retries once on the other tier, then hands off.

## Settings

| Setting | Values | Default |
|---|---|---|
| `models.understand_tier` | small, large | small |
| `models.escalate_below` | 0 to 1.01 (0: never escalate; 1.01: always) | 0.60 |
| `models.answer_tier` | small, large | small |
| `models.context_articles` | 1 to 12 | 3 |
| `understanding.clarify_below` | 0 to 1 | 0.35 |
| `understanding.max_clarifications` | 0 to 3 | 1 |
| `retrieval.require_agreement` | true, false | true |
| `retrieval.top_k` | 1 to 10 | 3 |
| `retrieval.min_score` | 0 to 30 (BM25 score; a good match scores 5 to 15) | 3.0 |
| `personalisation.plan_aware` | true, false | false |
| `guidance.offer_human_after_failures` | 1 to 5 | 2 |
| `guidance.ask_if_resolved` | true, false | true |
| `safety.injection_filter` | true, false | true |
| `procedures.<name>` | a version listed below | v1 |

## Procedures

Procedures are step graphs in `config/procedures/<name>.yaml`: verify identity (a code sent to the
account's email), look something up, branch on a condition, ask the customer for a value, act, and
tell the customer what happened. A release picks one version of each.

| Procedure | Version | What it does |
|---|---|---|
| refund | v1 | Verify the owner; refund the last charge if it is within 14 days and there was no refund this year; otherwise explain the policy. |
| refund | v2 | Same as v1 with a 30-day window. |
| refund | v3 | Skips verification for charges under 20 EUR. |
| cancel | v1 | Verify the owner and cancel at the end of the period. |
| change_email | v1 | Verify the owner, ask for the new address, change it. |
| send_invoice | v1 | Resend the latest invoice to the billing email on file. |
| update_payment | v1 | Send a secure link to update the card to the email on file. |

The refund policy is 14 days, once a year. Any action on an account must come after verification.

## Before a release ships

`arc review <release>` runs, in order: static checks (settings, and every write path in every
procedure must pass a verification step), the blocking eval suites (safety, escalations), a backtest
against production with judges calibrated by human labels, an A/B test sized by a power analysis,
and a staged rollout (dark, 1%, 10%, 50%, 100%) with health checks at each stage. See
`docs/RELEASE_REVIEW.md`.
