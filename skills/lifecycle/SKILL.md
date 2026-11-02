---
name: lifecycle
description: Keep and grow the customers the product already has. Owns the retention track (retained, expanding, referring) and the lifecycle_email and referral channels - onboarding emails toward activation, trial conversion, failed-payment recovery, a fair cancel flow with save offers, win-back, the referral program and review requests. Flows are written as templates and code in the product repo or as drafts for a human to load into the email platform; the agent sends to users only through the sending-authority gates. Use when gtm's focus is retention or the conversion rung needs an onboarding or trial email, or the user asks for onboarding emails, a drip or nurture sequence, churn, dunning, failed payments, cancel flow, win-back, referrals, or review requests. activation owns in-product onboarding; outbound owns email to people who aren't users yet.
---

# Lifecycle

Customers who stay, pay more and bring others are the cheapest growth there is. This skill writes
the messages and flows that move them, measures each flow against a metric, and leaves the email
platform and the decision to send with the team until the team says otherwise.

`<state>` is the directory printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
every script from the product repo root by absolute path. Copy passes the `../writing` gates:
claims from the ledger, one idea per email, no AI-tell phrasing. Flow patterns and timing are in
`references/flows.md`.

## What it moves

| rung (retention track) | metric | read from |
|---|---|---|
| `retained` | `churn_rate_monthly` (≤ 0.05 by default) | PostHog revenue analytics or a cohort query (`../measurement`) |
| `expanding` | `nrr` (≥ 1.0) | the revenue source through PostHog |
| `referring` | `referral_share` (≥ 0.1 of new customers) | a referral event or a "how did you hear" answer |

It also serves the conversion track: onboarding and trial emails move `first_step → activated` and
`activated → paid` alongside `../activation`, which owns the product side.

## Requires

- The events that define the funnel stages (`../measurement`) and the activation event (`../activation`).
  An email aimed at activation is judged on the activation rate, not on opens.
- `<state>/product-context.md` (voice, objections, customer language) and `<state>/claims.md`.
- To know which email platform (ESP) the product uses and where its templates live. Ask once and
  record it in plan.md. The agent holds no ESP admin credentials by default.

## 1. Find the leak

Before writing anything, name the flow the numbers point at:

| symptom | flow |
|---|---|
| signups who never reach the activation event | onboarding sequence, triggered by what the user hasn't done yet |
| trials that end unpaid | trial conversion: value recap, the missing step, a clear ask before the end |
| involuntary churn (card declines) | failed-payment recovery (dunning) |
| voluntary churn spikes after a period or a price change | cancel flow with a save offer, then win-back |
| happy, active users and few referrals | referral prompt at a moment of value; review requests |

Use PostHog cohorts and funnels to size each one (how many people, how much revenue). Pick the
largest one the team can ship, and open a bet on its metric before writing (`gtm.py bet open`,
method from `../experiments`: most flows can hold out 10-20% of the eligible users as a control).

## 2. Write the flow

For each flow write, in the product repo or in `<state>/lifecycle/<flow>/`:

- the trigger (an event or the absence of one, with the delay), the audience and the exit condition
  (the user did the thing, upgraded, cancelled or unsubscribed);
- each message: subject, body, one call to action that goes to the feature or step, the claim rows
  it relies on;
- the holdout and the metric the bet watches.

Where the product sends email from its own code (templates in the repo), the change is a **PR**.
Where it uses an ESP (Customer.io, Loops, Mailchimp, Klaviyo, …), write the flow as drafts the human
loads, with exact trigger settings, or as a PR to the ESP's templates repo if the team keeps one.

## 3. Rules that don't bend

- **Consent and suppression.** Marketing email goes only to users who agreed to it, per
  `../gtm/references/compliance.md`. Transactional email (receipts, password resets, failed-payment
  notices) is fine without marketing consent but must stay transactional. Honour every unsubscribe
  and the product's own suppression list.
- **Cancel flows don't obstruct.** Cancelling must be as easy as signing up. Show one save offer at
  most, with a clear "cancel anyway" next to it; no guilt copy, no extra screens, no phone-only
  cancellation. US online cancellation rules have been in flux (the FTC's negative-option rule was
  vacated in 2025; several states require online one-click cancellation): verify the current rules
  and confirm with counsel (checked 2026-11-02).
- **Dunning is a service.** Say what failed and how to fix it in one click; never threaten.
- **Referrals and reviews.** Incentives are disclosed in the request and in any resulting post or
  review; review requests go to everyone in the cohort, not only the happy ones (FTC rules on review
  gating, checked 2026-11-02; confirm with counsel). Never write or seed reviews.
- **Price, plans and data.** Discounts beyond what the team set, plan changes and anything that
  touches a user's data or billing are the human's call.

## 4. Sending

Most lifecycle email is sent by the ESP or the product once a human ships the flow. The agent sends
itself only on the `lifecycle_email` channel, and only through the sending-authority gates
(`../gtm/references/guardrails.md`):

- `draft` (the default): the agent writes; a human loads or sends.
- `approve_to_send`: one-off batches to existing users, such as review requests, through
  `../outbound/scripts/send_batch.py` with channel `lifecycle_email`, after the human approves the
  batch (`gtm.py approve <batch> --count N`). The sending address must be the one the team chose for
  user email (set `SMTP_FROM` accordingly); never the cold-outreach domain.
- `bounded`: the same, without per-batch approval, for drafts that are exactly an approved template
  (`<state>/templates/<id>.txt`) sent to an address on an approved segment
  (`<state>/segments/<id>.txt`), after the promotion criteria are met. A human grants it; the agent
  never does. See `../outbound/SKILL.md` "Bounded sending" for the file formats.

## 5. Measure and close

- Per flow: the bet's metric (activation, trial-to-paid, recovered revenue, churn, referral share)
  against the holdout, read through `../measurement`. Opens and clicks are diagnostics, not results.
- Record outcomes on the `lifecycle_email` channel when the agent sent the batch:
  `gtm.py outcome lifecycle_email --replies N --complaints N`.
- Close the bet on its check date (`gtm.py bet close <id>`); learnings only through
  `gtm.py learnings`.

## Don't

- Don't email users who didn't consent to marketing, or anyone on a suppression list.
- Don't change prices, offer unapproved discounts, or touch billing settings.
- Don't hide the cancel button, add friction to cancelling, or gate reviews.
- Don't import contacts into an ESP or hold its admin credentials unless a human set that up.
