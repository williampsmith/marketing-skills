# Lifecycle flows

Starting shapes for each flow. Adjust to the product's activation event, sales motion and voice;
every number below is a default to test, not a rule.

## Onboarding (toward the activation event)

| when | message | exit when |
|---|---|---|
| right after signup | one line on the first value moment and a link straight to the step that gets there | the user reaches the activation event |
| day 1-2 without activation | the most common blocker (from support tickets or session recordings) and how to clear it | activated |
| day 4-5 without activation | a short example of the result a similar user got (only from the claims ledger or a permitted quote) | activated |
| day 8-10 without activation | ask what's in the way, as a plain reply to a person | activated or replied |

- Trigger on behaviour, not on the calendar alone: someone who activated on day one gets none of these.
- Holdout: 10-20% of new signups receive nothing beyond transactional email. Judge on activation rate.

## Trial conversion

- 3-5 days before the trial ends: what they did, what they haven't tried yet, and what happens at the end.
- 1 day before: the plain facts (date, price, how to keep or cancel). Required in some places for
  auto-renewing trials; check `../gtm/references/compliance.md` and confirm with counsel.
- After an unpaid end: one message with a single way back. Then stop.
- Judge on trial-to-paid against a holdout.

## Failed-payment recovery (dunning)

- Enable the billing platform's automatic retries and card updater first; they recover more than email.
- Emails: on the first failure (what failed, a one-click update link), before the next retry, and a
  final notice before access changes. Transactional, factual, no threats.
- In-app banner for logged-in users while the payment is failing.
- Judge on recovered revenue and involuntary churn.

## Cancel flow and save offers

- One screen: the reason (optional, a short list plus "other"), at most one offer matched to the
  reason (pause instead of cancel for "not using it right now"; a downgrade for "too expensive"; help
  for "missing a feature" when it exists), and a clear "cancel anyway" with equal weight.
- Offers and their limits come from the team. Log reasons; they feed objections in product-context.md.
- Judge on net retention of the people who started cancelling, never on how many were blocked.

## Win-back

- 30 and 90 days after cancellation: what changed since they left (only shipped changes from the
  claims ledger), one way back. Stop after two messages or any reply.
- Skip people who cancelled for a reason the product hasn't fixed.

## Referral program

- Ask at a moment of value (right after the user gets a result, not at signup).
- A two-sided reward is common; rewards and their terms come from the team. Disclose the incentive
  wherever the referral is shared.
- Track a referral event or code so `referral_share` can be computed in PostHog.

## Review requests

- Ask the whole eligible cohort (for example active for 30+ days), not only promoters.
- Link to the review sites that matter for the product's buyers (from customer-research attention).
- Disclose any incentive; never offer one conditional on a positive review.
