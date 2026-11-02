---
name: paid
description: Run paid search and paid social for the product once a human turns the paid track on - read-only account audits first (structure, wasted search terms, conversion tracking that actually reaches PostHog and the ad platforms, CAC payback against the product's economics), competitor ad research through treg's ad libraries, creative from the creative skill, and every change as a proposal, except that with bounded spend authority it may move an existing campaign's daily budget inside the cap, per-change limit and once-a-day limit enforced by gtm.py spend check. Use when the user asks about Google Ads, Meta, LinkedIn or other ads, ad spend, ROAS, CAC, search terms, "should we run ads", or "increase/decrease our ad budget"; and when gtm's focus or exploration lands on the paid track. creative makes the ads; measurement owns conversion tracking; channel fit decides whether paid is worth trying at all.
---

# Paid

Paid media is the only track where a wrong call costs money every hour it stays live. So this skill
reads before it touches anything, judges every change on payback rather than on clicks, and
changes spend only inside limits a human set.

`<state>` is the directory printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
every script from the product repo root by absolute path. Audit checklists are in
`references/audits.md`.

## Is paid on?

The paid track is off by default. Check `gtm.py tracks` (`paid.enabled`) and `gtm.py fit`
(`paid_search`, `paid_social`). If the track is off, the most this skill does is an audit or a
proposal for the digest; turning it on (`gtm.py track paid on --quote "<their words>"`) is the human's
call. If a channel is ineligible on fit (for example economics: the deal size can't pay back the
cost per customer), say so with the numbers and stop.

## Rungs and the metrics behind them

| rung | metric | how it's met |
|---|---|---|
| `tracked` | `paid_conversions_tracked` ≥ 1 | paid conversions reach PostHog and the ad platform, attributed to campaign |
| `profitable` | `cac_payback_months` ≤ 12 | blended CAC on paid against gross margin per customer per month |
| `scaling` | `paid_scaling_ok` ≥ 1 | spend went up under the caps and payback held for a full cycle |

Record each with `gtm.py metric add … --source "<platform report or PostHog query>" --track paid`.

## 1. Audit (read-only, always first)

Read the account through treg's connected ad accounts (checked 2026-11-02; verify with
`catalog_get`; free calls on the team's own account): `google-ads.query` (GAQL),
`google-ads.x.gaql-search-term-view` (search terms that triggered ads), `meta-ads.insights` and
`meta-ads.x.account` (spend, conversions, the account spend cap). If the account isn't connected,
ask the human for an export and work from that.

Write `<state>/paid/audit-<date>.md`:

1. **Tracking**: does each conversion action the account optimises for exist in PostHog too, with
   matching counts within a reasonable gap? Broken tracking makes every other finding unreliable;
   fix it first through `../measurement`, as a PR.
2. **Waste**: search terms with spend and no conversions, broad match pulling irrelevant queries,
   overlap with organic rankings the product already holds, audiences far outside the ICP.
3. **Structure**: campaigns per intent, budgets limited by budget versus by bid, landing pages that
   match the ad's promise (`../cro`).
4. **Economics**: CAC per campaign and blended, against the payback target in channel-fit
   (`gross_margin` × `payback_target_months`). A campaign with a fine CPA and no revenue is a loss.

Findings go to the digest as proposals, ranked by money at stake.

## 2. Competitor ads research

Use treg's ad libraries (checked 2026-11-02; verify with `catalog_get` and state the price before
batching): `adyntel.google.ads.transparency` or `serpapi.google.ads.transparency` (a competitor's
Google ads), `spyfu.google.domain.paid_keywords` and `spyfu.google.domain.ad_history` (keywords and
ad copy over time), `treg.meta-ads.library.advertiser` and `meta-ad-library.meta-ads.library.search`
(Meta ads by advertiser or keyword), `adyntel.linkedin.search.ads.company` (LinkedIn ads). Note what
they test repeatedly (long-running ads usually work) and what they promise; claims about them are
quoted and dated, as in `../competitive-intel`.

## 3. Creative

Ads come from `../creative`: briefs tied to one claim row, formats bound to the channel, a review
page, human approval. This skill never writes ad copy that skips the claims gate.

## 4. Changing spend

| authority on the channel (`gtm.py authority show`) | what the agent may do |
|---|---|
| `draft` (default) | propose: the change, the reason, the expected effect on payback, the bet it opens. A human makes it in the platform. |
| `bounded` (a human ran `gtm.py authority grant paid_search --level bounded --daily-spend-cap 50 --max-change-pct 20 --quote "<their words>"` and `gtm.py track paid on --quote "<their words>"`) | change an existing campaign's daily budget itself, inside the caps, through the connected account |

Under bounded authority, every change follows the same steps:

1. `python3 ../gtm/scripts/gtm.py spend check <channel> --current-daily-usd <today's daily budget> --new-daily-usd <the budget after the change>`.
   Exit 3 means don't: the program is paused, the paid track is off, the channel isn't bounded, a
   number isn't finite or is negative, the current budget is 0 (starting spend stays with the
   human), the new budget is over `daily_spend_cap_usd` (the highest daily budget allowed), the
   change is larger than `max_change_pct`, or the channel already had `max_changes_per_day`
   (default 1) changes today. Put it in the digest instead.
2. Make the change. Open a bet first (`gtm.py bet open`) with the payback metric and a check date at
   least one conversion cycle out.
3. `python3 ../gtm/scripts/gtm.py spend log <channel> --current-daily-usd <before> --new-daily-usd <after> --note "<what changed>"`.
   `log` runs the same checks and refuses (exit 3) a change the gate wouldn't allow, so log right
   after the check, before any other change.

Also set the platform's own limits (account spend cap, campaign budgets) at or below the gtm caps,
so a mistake outside this skill is capped too. Ad spend never draws on the treg budget.

## Judge on payback

- Don't optimise a proxy into a revenue loss: CTR, CPC and platform-reported CPA are diagnostics.
  Decisions use revenue or qualified pipeline from PostHog and the revenue source.
- Give changes a full learning period and conversion cycle before judging; one change per campaign
  per bet.
- Revenue or spend anomalies are alerts: report them, don't self-correct.

## Don't

- Don't hold ad-account write access unless a human granted it, and never raise caps yourself.
- Don't launch new campaigns, audiences or countries without the human, even under bounded authority.
- Don't use customer lists for targeting without the consent rules in `../gtm/references/compliance.md`.
- Don't run ads with claims outside the ledger, or AI-generated people without disclosure.
