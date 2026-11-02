---
name: measurement
description: Set up and run the numbers every growth decision depends on - analytics and conversion tracking, attribution (including AI referrers), funnel stage counts, the revenue source, the Search Console sensor, and the monthly scorecard - with PostHog Cloud as the system of record. Use when the user wants to set up or check tracking, analytics, attribution or funnel metrics, connect PostHog, Stripe, RevenueCat or another revenue source, connect Search Console, asks "is our tracking working", "where do our signups come from", or wants a growth scorecard; and when gtm's tracking_check, metrics_sync, search_console or monthly_report job is due. gtm decides what to work on from these numbers; product-context holds the sales motion that picks the funnel.
---

# measurement

This skill owns the measurement track and the metrics every other track's rungs read. If a number
here is wrong or stale, `gtm.py focus` works on the wrong thing, so treat tracking as product code:
changes go in as PRs and get checked after they ship.

`<state>` is the store root printed by `gtm.py where`. Run every script from the **product repo
root**, calling the plugin's scripts by absolute path (`scripts/…` below is this skill's folder,
`../gtm/scripts/gtm.py` the state engine).

## What it owns

| metric (exact name) | written by | read by |
|---|---|---|
| `tracking_ok` | `posthog.py tracking-check` | measurement rung `instrumented` |
| `source_capture_rate` | `posthog.py pull` | measurement rung `attributed` |
| `stage:<id>` (one per stage in the motion's funnel template) | `posthog.py pull` | `funnel_visible`, conversion rungs, the bottleneck rule |
| `search_clicks_28d`, `nonbrand_clicks_28d` | `search_console.py` | digest, demand reporting |
| `query_top10_share`, `indexed_ratio` | `search_console.py` | demand rungs `ranking`, `indexed` |
| `leads_28d` | a `measurement.queries` entry | demand rung `pipeline` |
| `churn_rate_monthly`, `nrr`, `referral_share` | `measurement.queries` (revenue source) | retention rungs |
| `paid_conversions_tracked`, `cac_payback_months`, `paid_scaling_ok` | `measurement.queries` | paid rungs (when the paid track is on) |

Stage ids come from `../gtm/references/funnel-templates.json` for the profile's `motion` (for
self-serve: `visit`, `signup`, `activated`, `paid`, `retained`). Each `stage:<id>` is a 28-day
count of distinct people.

## Setup (once, with the human)

PostHog Cloud is the reference setup. Full steps: `references/posthog-setup.md`.

1. **Project.** The human creates a PostHog Cloud project in the US or EU region (EU if most users
   are in the EU or the company needs EU data residency).
2. **Tracking PR.** Open a PR in the product repo that installs the `posthog-js` snippet on the site
   and app with autocapture on, calls `identify` at signup with the product's own user id (never an
   email as the id), and captures one named event per funnel stage the snippet can't infer (e.g.
   `signed_up`, `first_redaction`). Keep the event names in `references/posthog-setup.md`'s table
   style: verb in the past tense, snake case.
3. **Source capture.** PostHog stores the first referrer and UTM values as person properties
   (`$initial_referring_domain`, `$initial_utm_source`). Add a "how did you hear about us" field at
   signup and set it as the person property `heard_from`. AI assistants show up as referrers such as
   `chatgpt.com`, `perplexity.ai`, `gemini.google.com`, `claude.ai` and `copilot.microsoft.com`
   (checked 2026-11-01; the list changes, so keep it in the dashboard filter, not in code).
4. **Map the funnel** in `<state>/gtm.json`:
   ```json
   "measurement": {
     "stage_events": {"visit": "$pageview", "signup": "signed_up", "activated": "first_redaction",
                      "paid": "subscription_started", "retained": "weekly_active"},
     "source_properties": ["$initial_referring_domain", "$initial_utm_source", "heard_from"]
   }
   ```
5. **Keys**, in the agent host's environment only:

   | variable | value |
   |---|---|
   | `POSTHOG_PROJECT_API_KEY` | the project key (`phc_…`), which can only send events |
   | `POSTHOG_PERSONAL_API_KEY` | a personal key (`phx_…`) limited to reading queries on this one project |
   | `POSTHOG_PROJECT_ID` | the numeric project id |
   | `POSTHOG_HOST` | `us` (default), `eu`, or an `https://` URL for a self-hosted instance |

6. `python3 scripts/posthog.py check` must show all three variables set and `ok: true` (exit 0). Then
   `gtm.py connect posthog`, which turns on the `tracking_check` and `metrics_sync` jobs.
7. **Revenue source**: `gtm.py connect revenue <stripe|revenuecat|paddle|chargebee|polar|events>`
   and the matching setup in `references/revenue-sources.md`.
8. **Search Console** (optional, free): the human connects the property in treg's connected
   accounts. Add `"brand_terms": ["acme", "acme app"]` to gtm.json, then `gtm.py connect
   search_console sc-domain:acme.com` (or the URL-prefix form `https://acme.com/`), which stores
   the property for the weekly job.

## Revenue source

Revenue always reaches the agent through PostHog, whatever the billing system. The agent never holds
a billing key.

| `connect revenue …` | how revenue reaches PostHog |
|---|---|
| `stripe` (the usual choice for web billing) | PostHog's Stripe data warehouse source, connected once by a human with a restricted key and webhook sync. PostHog's revenue analytics computes MRR and churn from it. |
| `revenuecat` | RevenueCat data warehouse source. PostHog's revenue analytics doesn't read it yet (checked 2026-11-01), so metrics come from HogQL over the imported tables. |
| `paddle`, `chargebee`, `polar` | Their data warehouse sources, read with HogQL. |
| `events` | Own billing or a license server: a PR adds `purchase`, `renewal` and `refund` capture with revenue properties, sent to the same PostHog person as the visitor. |

Revenue metrics go in `measurement.queries` as HogQL returning one number, e.g.
`"churn_rate_monthly": "SELECT …"`, with `measurement.query_tracks` naming each one's track. Table
and column names differ between projects and sources: **verify against your project's schema**
(`python3 scripts/posthog.py query "SELECT …"`) before saving a query. Examples per source are in
`references/revenue-sources.md`.

## Jobs (scheduled by gtm)

| job | recipe |
|---|---|
| `tracking_check` (daily) | `python3 scripts/posthog.py tracking-check` → `gtm.py record tracking_check`. Exit 1 means PostHog received no events in 2 days: alert now; its notes say whether the site's HTML lacks the snippet (bundled or proxied posthog-js is fine). A quiet first step alone is not a failure. |
| `metrics_sync` (daily) | `python3 scripts/posthog.py sync` (sends the outbox, then pulls stage counts, source capture and the configured queries) → `gtm.py record metrics_sync`. On an error the outbox is kept; retry tomorrow and report it. |
| `search_console` (weekly) | `python3 scripts/search_console.py` (the property stored by `gtm.py connect search_console sc-domain:acme.com`) → `gtm.py record search_console`. A treg or Search Console error exits 1 and writes nothing: record the failure, retry next week. |
| `monthly_report` (monthly) | `python3 scripts/report.py` → link `<state>/reports/<date>.html` in the digest → `gtm.py record monthly_report`. |

Before acting on a pulled number, apply the job's self-check: a stage count that halves or doubles
overnight is usually a tracking change, so check the tracking PRs and PostHog's event volume first.

## Without PostHog

The rungs only need the metric names above. A team on another analytics tool records them by hand,
daily, from that tool:

```
python3 ../gtm/scripts/gtm.py metric add tracking_ok 1 --source "GA4 realtime check" --track measurement
python3 ../gtm/scripts/gtm.py metric add stage:signup 412 --source "GA4 signups, last 28 days" --track conversion
```

Name the source on every row. A metric older than its rung's `max_age_days` counts as unknown, so a
by-hand setup needs a daily habit or it stalls the measurement track.

## The scorecard

`scripts/report.py` writes one self-contained HTML page from the store: focus and why, every rung
with its evidence, the funnel against its floors, AI visibility over time, bets, and spend. It makes
no network calls. Teams on PostHog also get a "Growth" dashboard and a weekly email or Slack
subscription to it (`references/posthog-setup.md`).

## Guardrails

- Keys live only in the host's environment. Never write them to the store, the repo, a PR or a
  digest.
- No personal data goes to PostHog from this plugin. `posthog.py` sends only an allowlist of
  properties per event (metric name, value, date, source, track; bet id, tactic, status, dates and
  effect), redacts emails and phone numbers in any text it does send, and identifies the operator's
  own events with a fixed `marketing-operator:<repo>` id and no person profile.
- Tracking code changes are PRs a human merges. Check them after deploy with `tracking-check`.
- EU traffic: tracking usually needs consent first. Use PostHog's consent options (e.g. starting
  opted out until the banner is accepted) and confirm the setup with whoever owns privacy; a
  consent banner lowers the counts, which floors should reflect.
- A query you didn't verify against the schema doesn't go into `measurement.queries`.
