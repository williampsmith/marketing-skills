# PostHog setup

The reference setup for the measurement skill. A human does steps 1-2 and 7; the agent does the
rest through PRs and the scripts. Facts about PostHog plans and UI checked 2026-11-01; verify
anything marked "verify" in the product itself.

## 1. Project and region

Create a project in PostHog Cloud. Pick the EU region when most users are in the EU or the company
needs EU data residency, otherwise US. The region sets `POSTHOG_HOST` (`eu` or `us`). One project
per product; the free plan includes one project.

## 2. Keys

| key | where to find it | scope | env var |
|---|---|---|---|
| Project API key (`phc_…`) | project settings | sends events only; it is public by design (it ships in the site's JavaScript) | `POSTHOG_PROJECT_API_KEY` |
| Personal API key (`phx_…`) | the human's account settings, personal API keys | read queries only, limited to this one project. Verify the scope names in PostHog's personal API key UI; pick the query read scope and nothing that writes. | `POSTHOG_PERSONAL_API_KEY` |
| Project id | project settings | numeric | `POSTHOG_PROJECT_ID` |

Put them in the agent host's environment (secrets for a cloud routine, the agent's env for Hermes).
Then run `python3 scripts/posthog.py check`.

## 3. The tracking PR

A checklist for the PR the agent opens in the product repo:

- [ ] `posthog-js` snippet or package on every page of the site and app, pointed at the right region.
- [ ] Autocapture on, so page views and clicks arrive without extra code.
- [ ] `identify(<product user id>)` right after signup and login. The id is the product's own user
      id, never an email address.
- [ ] One `capture("<event>")` per funnel stage the snippet can't infer (table below).
- [ ] The "how did you hear about us" answer set as the person property `heard_from`.
- [ ] Consent handling for EU visitors agreed with whoever owns privacy (e.g. start opted out).
- [ ] No personal data in event properties.
- [ ] After deploy: `python3 scripts/posthog.py tracking-check --url <site>` passes.

## 4. Event names per funnel template

Stage ids are fixed by `../gtm/references/funnel-templates.json`. Event names are the product's
choice; these are examples. Use past-tense snake case and keep them stable.

| motion | stage id → example event |
|---|---|
| `self_serve` | `visit` → `$pageview` · `signup` → `signed_up` · `activated` → `<first value moment>` · `paid` → `subscription_started` · `retained` → `weekly_active` |
| `sales_assisted` | `visit` → `$pageview` · `trial_or_demo` → `demo_requested` · `qualified` → `opportunity_qualified` · `won` → `deal_won` · `retained` → `renewed` |
| `enterprise` | `engaged_account` → `target_account_engaged` · `meeting` → `meeting_booked` · `opportunity` → `opportunity_created` · `won` → `deal_won` · `expanded` → `account_expanded` |
| `consumer_app` | `visit` → `$pageview` · `install` → `app_installed` · `activated` → `<first value moment>` · `paying` → `subscription_started` · `retained_d30` → `day_30_active` |
| `ecommerce` | `visit` → `$pageview` · `add_to_cart` → `added_to_cart` · `purchase` → `order_completed` · `repeat` → `repeat_order` |
| `oss_devtool` | `visit` → `$pageview` · `install` → `cli_installed` · `active_project` → `project_active` · `paid_or_lead` → `plan_started` · `retained` → `project_active_30d` |

Sales-side stages (qualified, won, meeting) usually live in a CRM. Send them to PostHog as events
from the CRM's webhooks or record them with `gtm.py metric add` until that exists.

## 5. The `measurement` block in gtm.json

```json
"measurement": {
  "stage_events": {
    "visit": "$pageview",
    "signup": "signed_up",
    "activated": "first_redaction",
    "paid": "subscription_started",
    "retained": "weekly_active"
  },
  "source_properties": ["$initial_referring_domain", "$initial_utm_source", "heard_from"],
  "queries": {
    "leads_28d": "SELECT count(DISTINCT person_id) FROM events WHERE event = 'demo_requested' AND timestamp > now() - INTERVAL 28 DAY"
  },
  "query_tracks": {"leads_28d": "demand"}
}
```

`stage_events` drives `stage:<id>` counts (distinct people in the last 28 days). `source_properties`
drives `source_capture_rate`: the share of people reaching the first step with any of them set (a
referrer that isn't `$direct`, a UTM source, or a "how did you hear" answer). Each `queries` entry
must return one number; preview it with `python3 scripts/posthog.py pull --dry-run` and run it once
with `posthog.py query` before saving. Event and property names are checked against a safe pattern
before they reach a query.

## 6. The Growth dashboard

Build one dashboard called "Growth" with:

- a funnel insight over the stage events, last 28 days;
- signups (or the first step) broken down by `$initial_referring_domain`, with the AI referrers
  (`chatgpt.com`, `perplexity.ai`, `gemini.google.com`, `claude.ai`, `copilot.microsoft.com`; checked
  2026-11-01) highlighted;
- trends of `marketing_metric` events, the operator's own numbers (AI mention and citation rates,
  rung status, spend), filtered by the `metric` property;
- `marketing_bet` events as a table: bets opened and closed with their results.

Add a weekly subscription to the dashboard by email or Slack for the team. The free plan allows up
to 5 dashboard or insight subscriptions; one weekly subscription is enough.

## 7. Billing

The free plan covers an early-stage product (1M events a month, one project) with one year of data
retention. Pay-as-you-go has no base fee, keeps 7 years and allows more projects. Move to
pay-as-you-go with billing limits set before the first year of history would start to expire, so
year-on-year comparisons stay possible. Verify current allowances on PostHog's pricing page.
