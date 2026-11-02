# Paid audits

Read-only checklists. Every finding names the data it came from (a GAQL query, an insights pull, an
export, a PostHog query) and the money at stake per month.

## Tracking

- List the conversion actions each platform optimises for. For each, find the matching PostHog event
  and compare 28-day counts. A gap above roughly 20% needs an explanation (attribution windows,
  consent, server-side events) before anything else is judged.
- Check that conversions carry the campaign (UTMs or click ids reach PostHog), so CAC can be computed
  per campaign rather than only blended.
- Check for double counting (two actions for one purchase, a page-load conversion that fires twice).
- Record `paid_conversions_tracked` (1 when the main conversion reaches both sides) with its source.

## Search (Google, Bing)

- Search terms report: terms with spend and zero conversions over the period; irrelevant intents
  (jobs, free, competitor support); terms where the product already ranks top 3 organically.
- Match types and negatives: broad match without a negative list; missing brand exclusions in
  non-brand campaigns.
- Structure: one intent per campaign, budgets "limited by budget" on campaigns with good payback
  versus open budgets on poor ones.
- Landing pages: the ad's promise appears above the fold of the page it sends to (`../cro`).

## Social (Meta, LinkedIn, TikTok)

- Audiences against the ICP and anti-ICP in product-context.md; frequency and fatigue on long-running ads.
- Creative: which concepts carry spend, and whether they make claims outside the ledger.
- Placements and countries that spend without converting.

## Economics

```
payback_months = CAC / (monthly revenue per customer × gross margin)
```

- CAC per campaign = spend / new paying customers attributed to it (or qualified opportunities for
  sales-led motions, with the stage named).
- Compare with the target in channel-fit.json (`payback_target_months`, default 18; the paid track's
  `profitable` rung defaults to 12).
- Record `cac_payback_months` with its source and window.

## Proposal format (digest)

| change | why (evidence) | expected effect on payback | money at stake per month | bet |
|---|---|---|---|---|
| add 14 negatives from the search terms report | $410/month on terms with no conversions in 60 days | lower CAC on campaign X | $410 | `2026-11-20-negatives` |
