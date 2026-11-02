# Design: the growth operator (next version)

Status: draft for review · 2026-11-01 · targets plugin 0.4 → 1.0 in phases (section 13)

Today the plugin is an AI-search operator: seven skills, one entry point (`gtm`), and a state
engine (`gtm.py`) that schedules jobs, enforces a budget and works up one ladder. This spec makes it
a growth operator for the whole funnel without giving up what makes it runnable unattended.

The approach: cover the funnel with about twenty skills rather than one per topic, keep execution in
code, and add a shared product context, a stricter job contract, guardrails for sending and spending,
and a shared writing standard. References are written from first principles; no text is copied from
other skill libraries.

## 1. Goals and non-goals

**Goals**
- Cover the funnel: discoverability, demand, conversion, retention, paid, and the creative that
  feeds them.
- Choose what to work on from **who the product sells to** and **where the funnel is weakest**,
  and explain the choice in every digest.
- Treat every improvement as a measured bet, and learn which tactics work for this product.
- Put all marketing data in one place a non-technical team can browse, and report on it on a fixed
  cadence.
- Stay host-neutral (Claude Code, Hermes, cron) and safe to leave running.

**Non-goals**
- A skill per topic. A skill exists because it owns jobs; knowledge without a job is a reference.
- A bespoke client per vendor. treg and a few opinionated tools are the data plane.
- Autonomous spending or sending by default. Both stay gated until a human grants bounded
  authority (section 11).
- CRM operations, events and offline marketing.

## 2. Principles carried forward

1. **Facts and decisions in code.** Dates, money, cadence, cooldowns, focus selection and
   experiment status come from `gtm.py`, never from the model's reasoning.
2. **Every paid call is metered.** treg or a connected account; cost recorded per job.
3. **The code is the source of truth.** Claims come from the repo with evidence and a commit.
4. **Drafts and PRs, humans publish.** Raised only by explicit, capped authorisation.
5. **Every number has a source and a date.** Unsourced numbers are left out, not estimated.
6. **Report movement, not activity.**
7. **The product repo gets the work, not the bookkeeping.** Pages, tracking code and other proposed
   changes arrive as PRs. Metrics, experiments, run state and anything with personal data live
   elsewhere (section 9).

## 3. Concepts

| term | meaning |
|---|---|
| **GTM profile** | Who we sell to and how they buy: motion, buyer, deal size, cycle length, where buyers spend attention. Lives in `product-context.md`. Decides which tracks and channels are eligible and how much each is worth trying (section 4). |
| **Funnel template** | The stages and metrics for a motion. Self-serve measures signups; enterprise measures demos and pipeline. Chosen from the GTM profile. |
| **Track** | A part of the funnel with its own ladder of rungs. Tracks are outcomes. |
| **Rung** | A pass/fail test on data with an editable floor. |
| **Channel** | A way to move a track: AI search, SEO, outbound, LinkedIn, short-form video, paid search… Channels are means. |
| **Capability skill** | A skill that does the work in one or more channels (e.g. `creative` serves organic social and paid). |
| **Sensor job** | A scheduled measurement. Runs in every enabled track. Mostly free. |
| **Improvement job** | A change to the product's marketing surfaces or a draft for humans. Goes to the focus track. |
| **Bet** | One improvement with a hypothesis, metric, baseline and check date. Recorded in the experiment ledger. |
| **Focus** | The track that gets most improvement work this period, chosen by `gtm.py` (section 6). |

## 4. Fit: what the product is and who buys it

This is the layer that stops the operator making TikTok UGC for a product sold to bank CISOs.
It runs before any focus selection and has three outputs: a funnel template, eligibility for each
channel, and a prior (an expected payoff) for each channel.

### 4.1 The GTM profile

Captured in `product-context.md` (section 9.1) during `init`. The agent drafts it from the repo,
site and customer research, then a human confirms it. Fields:

| field | values | why it matters |
|---|---|---|
| `motion` | `self_serve` · `sales_assisted` · `enterprise` · `consumer_app` · `ecommerce` · `oss_devtool` | picks the funnel template |
| `acv_usd` | number (annual contract value; for consumer, lifetime value) | bounds what each channel may cost per customer |
| `buyer` / `user` | roles, seniority, team | who the content and outreach address |
| `buying_committee` | 1 · 2-4 · 5+ | multi-stakeholder deals favour proof, comparisons and sales material |
| `cycle_days` | typical days from first touch to paid | sets experiment horizons; long cycles need leading indicators |
| `attention` | where buyers look, ranked, with evidence (e.g. "LinkedIn: 0.8, from customer-research") | the strongest fit input; measured, not assumed |
| `regulated` | none · light · heavy (finance, health, legal, gov) | restricts claims, channels and creative formats |
| `geo` | markets | channel availability and compliance (cold email rules differ by country) |
| `stage` | prelaunch · launched | what is measurable yet (`gtm.py stage launched` on launch day) |

`attention` comes from the `customer-research` skill: where the ICP posts, asks questions and
reviews (Reddit, LinkedIn, Stack Overflow, G2, TikTok, analyst reports, forums), measured
through treg. It is re-checked in `strategy_review` quarterly.

### 4.2 Funnel templates

| motion | stages (each is a metric with a floor) | north star |
|---|---|---|
| self_serve | reach → visit → signup → activated → paid → retained | activated signups, then MRR |
| sales_assisted | reach → visit → trial or demo request → qualified → won → retained | qualified pipeline |
| enterprise | reach (named accounts aware) → engaged account → meeting → opportunity → won → expanded | pipeline from target accounts |
| consumer_app | reach → install → activated → retained D30 → paying | retained users |
| ecommerce | reach → visit → add to cart → purchase → repeat | contribution margin |
| oss_devtool | reach → repo/docs visit → install → active project → paid/enterprise lead | active installs |

Floors start from benchmarks in `references/benchmarks.md` for the motion and are replaced by the
product's own baseline after 30 days of data.

### 4.3 Channel fit

`references/channel-fit.md` holds a matrix of channel × motion with a default fit from 0 to 1 and
hard exclusions. `gtm.py fit` combines it with the profile:

```
fit(channel) = matrix[motion][channel]
             × attention_weight(channel)          # from customer-research; 1.0 until measured
             × economics(channel, acv_usd)        # 0 when the channel can't pay back at this deal size
             × cycle_factor(channel, cycle_days)  # fast-feedback channels lose value when results land months later
             × compliance(channel, regulated, geo)
```

**The default matrix.** Rows are channels, columns are motions. These values are starting
estimates. The evidence for them is thin, so they are meant to be overruled by each product's own
data.

| channel | self_serve | sales_assisted | enterprise | consumer_app | ecommerce | oss_devtool |
|---|---|---|---|---|---|---|
| AI search and comparison pages | 0.8 | 0.9 | 0.9 | 0.6 | 0.6 | 0.9 |
| SEO content | 0.8 | 0.7 | 0.5 | 0.5 | 0.8 | 0.8 |
| Review sites and communities (G2, Reddit, forums, Stack Overflow) | 0.6 | 0.8 | 0.7 | 0.4 | 0.6 | 0.8 |
| Outbound to named accounts | 0.1 | 0.7 | 0.9 | 0 | 0 | 0.3 |
| LinkedIn organic (founder, thought leadership) | 0.4 | 0.7 | 0.8 | 0.1 | 0.1 | 0.4 |
| Short-form video and UGC (TikTok, Reels, Shorts) | 0.5 | 0.2 | 0.05 | 0.9 | 0.9 | 0.2 |
| Long-form video (YouTube demos and tutorials) | 0.6 | 0.6 | 0.5 | 0.5 | 0.5 | 0.7 |
| Creators and influencers | 0.5 | 0.3 | 0.1 | 0.8 | 0.8 | 0.5 |
| PR and press | 0.4 | 0.5 | 0.6 | 0.5 | 0.4 | 0.4 |
| Partnerships, integrations and marketplaces | 0.6 | 0.7 | 0.7 | 0.3 | 0.4 | 0.8 |
| Paid search | 0.6 | 0.6 | 0.3 | 0.4 | 0.8 | 0.3 |
| Paid social | 0.5 | 0.4 | 0.3 | 0.8 | 0.8 | 0.2 |
| Lifecycle email (to the product's own users) | 0.9 | 0.7 | 0.5 | 0.8 | 0.9 | 0.6 |
| Referral program | 0.6 | 0.4 | 0.2 | 0.7 | 0.7 | 0.4 |

What the values rest on (checked 2026-11-01; mostly vendor-reported survey results, so treat them
as directional):

- **AI search is high in every B2B motion.** G2's 2026 survey of 1,076 software buyers reports that
  51% start vendor research in an AI chatbot rather than Google, and that 69% picked a different
  vendor than planned because of what the chatbot surfaced. Forrester's 2026 Buyers' Journey survey
  reports that 94% of business buyers used generative AI in a recent purchase. These support
  Discoverability's standing priority (section 6).
- **Peers outrank social for trust.** A 2026 SurveyMonkey and Reddit study of 1,202 US decision
  makers found that 70% had used social media to research a purchase, but only 36% trusted it,
  against 73% for peer insights. So review sites and communities score above social feeds for B2B,
  and short-form video is scored as a way to build awareness, not to get onto shortlists.
- **No reliable benchmark gives cost per customer by channel and deal size.** Published channel
  CAC figures disagree several-fold between sources, and median B2B SaaS CAC payback is reported
  at 15-19 months. Hence the economics rule below uses conservative cost floors, and measured cost
  replaces them as bets close.

**Economics.** `economics = min(1, acv_usd × gross_margin × payback_target_months / 12 / cost_floor)`,
with defaults `gross_margin = 0.8` and `payback_target_months = 18`. Default `cost_floor` per
customer: outbound $1,500, PR $1,000, paid search $400, paid social $300, creators $200. Organic
channels cost agent effort, not media, and their floor is 0, so the factor is 1. At a $120
ACV, outbound's factor is 0.1 and paid social's 0.48; at $60k both are 1. Once a channel has a measured
cost per customer from closed bets, that replaces the floor.

**Learning from the product.** The matrix value acts as a prior worth three bets. Each closed bet in
a channel moves its fit towards the measured result, so after three or four bets the product's own
evidence outweighs the default. `attention_weight` replaces the matrix's assumptions about where
buyers spend time as soon as `customer-research` has measured it.

- **Eligible** if `fit ≥ 0.25` and no hard exclusion applies. Ineligible channels never get
  improvement jobs; their sensors don't run.
- **Prior** for experiment allocation (section 8.4) is the fit score.
- The digest lists ineligible channels once a month with the reason, so a human can override
  (`gtm.json → fit.overrides`).

Two examples, before any attention measurements (attention 1.0):

| channel | self-serve tool, $120/yr | enterprise compliance product, $60k ACV |
|---|---|---|
| AI search and comparison pages | 0.8 | 0.9 |
| SEO content | 0.8 | 0.5 |
| Outbound to named accounts | 0.1 × 0.1 economics = 0.01 → ineligible | 0.9 |
| LinkedIn organic | 0.4 | 0.8 |
| Review sites and communities | 0.6 | 0.7 |
| Short-form video and UGC | 0.5 | 0.05 → ineligible |
| Long-form video | 0.6 | 0.5 |
| Paid social | 0.5 × 0.48 economics = 0.24 → ineligible | 0.3 |

So `creative` stays useful for enterprise, but its formats change: demo videos, LinkedIn
document posts and diagrams instead of UGC hooks. Formats are channel-bound, and the channel is
what fit filters.

### 4.4 Fit also changes the tracks

- Enterprise and sales-assisted: Conversion measures demo requests and qualified meetings, not
  signups. Retention measures expansion and renewals.
- Long cycles (`cycle_days > 60`): experiments are judged on leading indicators (engaged accounts,
  meetings booked), with the lagging metric reported but not used to decide.
- Prelaunch: only Discoverability, Measurement and content run.

## 5. Tracks and ladders

| track | rungs, in order | default rung tests (self-serve; other motions map through the template) |
|---|---|---|
| **0. Measurement** (foundation) | instrumented → attributed → funnel visible | conversion event fires in the tracking check; source captured for ≥ 80% of signups including AI referrers and "how did you hear"; every template stage has a count in the last 7 days |
| **1. Discoverability** | reachable → known → associated → preferred | today's ladder: access check clean; brand mention ≥ 0.8; category ≥ 0.3; comparison ≥ 0.5 with average rank ≤ 2 |
| **2. Demand** | indexed → ranking → visited → pipeline | ≥ 90% of sitemap indexed; ≥ 30% of the query map in the top 10; non-brand visits ≥ floor; channel-attributed leads or meetings ≥ floor |
| **3. Conversion** | first step → activating → paying | visit→first step, first step→activated, activated→paid, each ≥ floor |
| **4. Retention** | retained → expanding → referring | churn ≤ ceiling; net revenue retention ≥ floor; referral share of new customers ≥ floor |
| **5. Paid** (opt-in) | tracked → profitable → scaling | paid conversions tracked; CAC payback ≤ target months; spend increased under caps with payback held |

Each rung maps to the skills that move it (`RUNG_SKILLS` generalised to `tracks.<track>.rungs.<rung>.skills`),
and each skill declares which channels it serves, so fit filters skills as well.

## 6. Choosing the focus

`gtm.py focus` returns the focus track, a secondary track, and the reason. Rules, in order:

1. **Alerts preempt.** Access regression, tracking broken, budget breach, crisis mention or a
   failing claim are handled this tick, whatever the focus.
2. **Measurement gates the funnel.** While Measurement is below `funnel visible`, tracks 3-5 read
   `unknown`; Measurement is the focus unless `stage = prelaunch`.
3. **Bottleneck.** For each template stage with enough data, `score = actual / floor`. The focus
   is the track owning the lowest-scoring stage. Stages without enough data are skipped. If the
   top of the funnel has too few entrants for conversion rates to mean anything (below the sample
   minimum in `gtm.json`), reach is the bottleneck by definition.
4. **Fit.** A track whose eligible channels have a summed fit below 0.5 can't be the focus; its
   problems are reported for a human to decide.
5. **Hysteresis.** The focus holds for 30 days, until its track stops being workable, or until another
   stage falls below half its floor. (Implemented in 0.4 as a fixed 30-day hold, roughly the
   monthly `strategy_review` cadence.)

**Discoverability is a standing priority.** Buyers in every motion now research and shortlist with
AI assistants, and the cost of being absent or misdescribed compounds, so Discoverability is not
left to compete on the bottleneck rule alone:

- A failed `reachable` or `known` rung counts as an alert (rule 1). Both are cheap to fix and
  everything above them depends on them.
- Until `preferred` is met, Discoverability gets at least 25% of improvement work whenever it isn't
  the focus, and it is the default secondary track.
- Once `preferred` is met, it drops to sensors plus fixes for regressions, and its share goes back
  to the pool.
- It is the focus itself only when the bottleneck rule says so. Visibility doesn't help while
  tracking is broken or signups leak, so it doesn't override rules 2 and 3.
- The only exception is an AI-search fit below 0.25 (section 4.3), which is rare: impulse consumer
  purchases with no research step. A human can override that too.

The digest leads with it, e.g. "Focus: Conversion — trial→activated is 18% against a 35% floor.
Secondary: Discoverability. Not pursuing: short-form UGC (buyers aren't there: 0.05)."

## 7. Jobs and dispatch

### 7.1 The job contract

Every entry in `DEFAULT_JOBS` gains the loop-anatomy fields, and `gtm.py` enforces the mechanical
ones:

| field | example | enforced by |
|---|---|---|
| `track`, `kind` | `"conversion"`, `"sensor"` or `"improvement"` | focus routing |
| `every_days`, `after`, `stages`, `usd` | as today | `tick` |
| `requires` | `["posthog"]`, `["channel:outbound"]` | `tick` (skipped with reason if missing or ineligible) |
| `acts_when` | `"a tracked page's conversion rate fell > 30% vs 4-week median"` | the skill (prose), logged |
| `self_check` | `"is the drop in more than one traffic source?"` | the skill, logged |
| `cooldown_days`, `dedupe_key` | 30, `"page_url"` | `gtm.py record --key` refuses repeats inside the window |
| `max_actions` | 2 | `tick` |
| `stop` | `"two failed attempts on the same key → escalate"` | `gtm.py` counters |
| `output` | `"state:conversion/…"`, `"pr"`, `"draft"` | digest |

### 7.2 Dispatch

- `tick` returns due jobs, each self-contained: inputs, output paths under `<state>/<track>/`,
  reserved budget.
- **Sensor and research jobs** run in parallel as subagents when the host supports it (Claude Code
  Agent tool, Hermes `delegate_task`), or one after another otherwise. Each writes only its own
  paths and calls `gtm.py record`.
- **Improvement jobs that change the repo** run one at a time, each on its own branch or worktree
  with its own PR.
- The main agent merges results and writes the digest.
- No per-track agents on every tick. A typical day is one free sensor run inline.

## 8. Experiments

### 8.1 Every improvement is a bet

One record per bet in the state store's `experiments.jsonl`, written by `gtm.py bet open` and closed
by `gtm.py bet close`. Every change of status is also sent to PostHog so the team sees the ledger on
the dashboard:

```json
{"id": "2026-11-12-comparison-acrobat", "track": "discoverability", "channel": "ai_search",
 "tactic": "comparison_page", "hypothesis": "A sourced comparison raises mention on 'vs Acrobat' prompts",
 "metric": "mention_rate:comparison", "baseline": 0.1, "expected": 0.3,
 "method": "holdout", "control": ["prompts on topics left unchanged"],
 "opened": "2026-11-12", "check": "2026-12-10", "cost_usd": 0.4, "effort": "1 session",
 "status": "open", "result": null, "decision": null}
```

The metric and the expected effect are fixed when the bet opens. `bet close` reads the metric
from the metrics store, not from the agent.

### 8.2 Methods, strongest first

| method | when | example |
|---|---|---|
| A/B with flags | enough traffic for the sample size in `references/experiments.md` | PostHog experiment on the pricing page |
| Holdout | the unit can be split (prompts, pages, accounts) | change pages for half the prompt topics; compare with the untouched half |
| Staggered rollout | changes across many similar units | ship comparison pages one competitor at a time |
| Before/after | nothing else possible | labelled *directional* in every report |

### 8.3 A common currency

Results are converted to the effect on the current bottleneck metric and, through the funnel
template, on the north star, per dollar and per hour of agent effort. This is what makes tactics
in different tracks comparable.

### 8.4 Allocation

- The focus track gets at least 60% of improvement work. Discoverability's standing share
  (section 6) comes next; if Discoverability is the focus, the secondary track takes that share.
  What remains goes to exploration.
- Within a track, tactics are chosen by Thompson sampling over tactic types: the prior is the
  channel fit (section 4.3), updated by this product's closed bets. Tactics that keep winning get
  more work; untried but plausible ones still get a share.
- The ledger never picks the focus track; the bottleneck rule does. Otherwise the operator chases
  whatever is easiest to measure.
- Underpowered results are recorded as `inconclusive`, not as losses.
- A result becomes a **learning** in `product-context.md` only after a closed bet with the
  stronger methods, or the same direction in two bets, and only when a human accepts it in the
  digest.

## 9. Measurement and reporting

### 9.1 Where data lives

Nothing the operator records has to live in the product repo. In 0.3 the repo was the agent's
memory because it was durable and cost no infrastructure. That convenience gets in the way of
adoption: teams don't want marketing data, strategy or outreach contacts in their code history, and
for an open-source product the repo is public. Data is split by who uses it:

| class | contents | where |
|---|---|---|
| **Metrics and experiment results** | every observation (`{"metric","date","value","source","track","cost_usd"}`), rung status, focus, bet opened and closed | **PostHog**, as `marketing_metric` and `marketing_bet` events. The system of record for people. |
| **Operator state** | `gtm.json` (tracks, floors, fit, focus, jobs, budget, notify), last runs, cooldowns and dedupe keys, `spend.jsonl`, `experiments.jsonl`, raw AI answers and run outputs, outreach queues, digests | **the state store** (below). Never the product repo. |
| **Reviewed knowledge** | `product-context.md`, `claims.md`, the prompt panel | the state store by default; the product repo if the team wants changes reviewed in PRs (`state.knowledge: "repo"`) |
| **Proposed work** | pages, `llms.txt`, structured data, tracking code, onboarding changes | **the product repo, as PRs**. Its only required footprint. |

**The state store** is a directory with a pluggable backend, chosen in init:

| backend | for | how |
|---|---|---|
| `dir` (default) | a persistent host: Hermes on a VPS, a server running Claude Code | `~/.marketing/<owner>-<repo>/` on the agent's machine |
| `git` | ephemeral hosts such as a Claude Code cloud routine, or wanting history | a separate private repo (e.g. `<product>-marketing`), cloned at the start of each run and pushed at the end. Gives diffs and an audit trail without touching the product repo. |
| `repo` | teams that prefer 0.3's behaviour | `.marketing/` in the product repo, as today |

The agent finds the store through `MARKETING_STATE` (a path or a git URL) in its environment or
scheduled prompt. Nothing has to be added to the product repo to point at it.

`gtm.py` computes rungs, focus and bet results from the store's local copy of recent metrics. That
copy is refreshed from PostHog's query API at the start of each tick, so PostHog stays the source of
truth and edits made there (a corrected value, a deleted bad run) are respected. Without PostHog
credentials, the copy in the store is used on its own. That is also how tests and offline runs work.

**Personal data:** outreach contacts, author emails and account names stay in the state store with a
retention limit (default 180 days after last contact). They are never sent to PostHog as event
properties and never committed to the product repo.

### 9.2 Tool choices (opinionated)

| need | tool | notes |
|---|---|---|
| Product and web analytics, funnels, experiments, flags, surveys, marketing metrics | **PostHog Cloud** (the reference setup; US or EU region by data residency) | system of record for the funnel, the operator's metrics and the team's dashboard; the free tier covers an early-stage product |
| Search data | Search Console, GA4 via treg connected accounts | free |
| AI visibility, SERP, backlinks, social, ads library, enrichment | **treg** | metered |
| Revenue | pluggable, always **read through PostHog**; Stripe by default (below) | MRR, churn, expansion, ARPU, LTV |
| Creative generation | treg (Seedance, image models, voice) | via the `make-ugc` treg skill where it fits |

**Access (checked 2026-11-01).** treg's catalog has no PostHog or Stripe endpoints, so the agent
talks to PostHog directly. That is the only direct integration the plugin needs:

- **Writing:** the PostHog project API key, which is meant for event capture and is low risk, sends
  `marketing_metric` and `marketing_bet` events.
- **Reading:** a PostHog personal API key, scoped to query read on the one project, runs HogQL
  queries for funnel stages, revenue and the operator's own metrics.
- **Billing systems:** the agent never holds a billing key. For Stripe, A human connects Stripe once as a PostHog data
  warehouse source, using a restricted key with webhook sync, as PostHog recommends. Revenue then
  reaches the agent through the same query key. Stripe's tables count against the warehouse's free
  1M rows a month. Other billing systems follow the same rule (below).

**Revenue sources.** How a product takes money varies; where the agent reads it doesn't. Every
option ends in PostHog, and `measurement` sets it up from `revenue_source` in `gtm.json`, chosen at
init from what the repo and the human say about billing:

| `revenue_source` | when | how it reaches PostHog | extra cost |
|---|---|---|---|
| `stripe` (default) | web checkout on Stripe | Stripe data warehouse source with webhook sync; PostHog revenue analytics computes MRR (new, expansion, contraction, churn), gross revenue, ARPU, LTV and customers | none beyond Stripe's fees |
| `revenuecat` | mobile in-app subscriptions, or mobile plus web | RevenueCat data warehouse source. PostHog's revenue analytics doesn't support RevenueCat yet (listed as coming), so `measurement` ships HogQL queries for the same metrics against the imported tables. | RevenueCat: free to $2,500 tracked revenue a month, then 1% |
| `paddle` · `chargebee` · `polar` | those billing platforms | their PostHog data warehouse sources, queried the same way until revenue analytics supports them | none |
| `events` | own billing or a license server | the server sends `purchase`, `renewal` and `refund` events with revenue properties to PostHog; revenue analytics works from events | none |

RevenueCat is recommended only when a product sells inside mobile apps. Stripe can't see App Store
or Google Play revenue, and cross-platform entitlements and native paywall tests are what the 1%
pays for. For web-only products, Stripe through PostHog gives the operator the same metrics at no
extra cost, and PostHog flags cover price experiments.

For the `events` option, `measurement` opens a PR that adds the capture call where the product
records a purchase or license activation, keyed to the same PostHog person as the visitor so
revenue joins the funnel. A product with no PostHog person at purchase time (e.g. an offline
license key) passes the email or license ID as the distinct ID and aliases it when the user
first activates.

**PostHog Cloud plans.**
- **Free:** 1M analytics events, 1M flag and experiment requests, 1,500 survey responses and 1M
  warehouse rows a month, one project, one year of retention, and up to 5 dashboard or insight
  subscriptions by email or Slack (daily, weekly or monthly; up to 20 insights each).
- **Pay-as-you-go:** $0 base fee, billed only above the free allowances, with 7-year retention, 6
  projects and unlimited subscriptions.

The reference setup starts free: one weekly email or Slack subscription to the Growth dashboard
needs only one of the five slots. Move to pay-as-you-go (with billing limits set) before the first
year of history would start expiring, because year-on-year comparisons need it.

### 9.3 Where people see it

- **PostHog dashboard, "Growth":** the operator sends its own metrics as `marketing_metric`
  events (AI mention, citation and share of voice per engine, rung status, focus, spend, bet
  results) next to the product funnel. One link for the team, and a weekly PostHog subscription
  emails or posts it to Slack.
- **Fallback for teams without PostHog:** `gtm.py report` renders a self-contained HTML scorecard
  into the state store's `reports/`; on Claude Code it may also be published as an Artifact.
- **Cadence:** alerts immediately; weekly digest to the notify channel (Shipped, Moved, Broken,
  Next, Needs you, and the focus line); monthly review with charts, closed bets and proposed
  learnings; quarterly fit review.

## 10. Creative

New `creative` skill, a production capability used by channels in Demand, Paid and content.

1. **Brief** from the bet: channel, format, audience, the one claim (from `claims.md`).
2. **Research** formats and hooks that work in that channel: trending short-form via treg for
   consumer; top LinkedIn posts and competitor ads library for B2B.
3. **Scripts and variants**, checked by the writing standard.
4. **Generate** with treg models; record cost per asset.
5. **Review page** for a human to approve, reject or edit each asset. Nothing publishes from here.
6. **Measure per asset** after publishing: hook rate, click-through, cost per first step, read from
   the channel and PostHog, written to `metrics/`.

Guardrails: AI presenters and synthetic testimonials are disclosed, as the FTC and platform labels
require; no likeness of real people without written permission; claims only from the ledger;
regulated products get a mandatory human review of every asset.

## 11. Guardrails

| tier | actions | default |
|---|---|---|
| 1 · autonomous | read, measure, research, draft, stage, open PRs, write the state store, send events to PostHog | allowed |
| 2 · gated | publish, send, spend, change ad or email settings, contact a person, delete | human approves each, via the digest or a review page |
| 2 · bounded | a tier-2 action with explicit authority in `gtm.json → authority` | allowed within caps: per-run and daily volume, spend, allowlist of accounts or lists |

**Sending, step by step.** Authority to send is earned, per channel, in three steps:

1. **Draft** (every channel at first): the agent writes the message; a human sends it.
2. **Approve-to-send** (from phase 3 for outbound and outreach): the human approves a batch in the
   digest or on the review page, and the agent sends exactly those messages. Approval is the
   send button; nobody copies and pastes. Follow-ups go only within a sequence the human approved,
   and stop on any reply.
3. **Bounded** (phase 5, opt-in per channel): the agent sends without per-message approval, within
   daily caps, to contacts matching an approved segment, using approved templates. It can be
   switched on only after 30 days of approve-to-send in that channel with a reply rate at or above
   the floor and no complaints.

Sending happens from a dedicated shared inbox on a separate sending domain (e.g. `hello@try<product>.com`),
so a mistake can't damage the main domain's deliverability. Every reply goes to a human. Press,
editors and named enterprise accounts stay at approve-to-send permanently.

Always: suppression lists checked before any send; CAN-SPAM, CASL, GDPR and FTC rules in
`references/compliance.md`; no raw personal data in state or logs (IDs or hashes); a kill switch
(`gtm.json → paused: true`, checked first by every job); always escalate crises, revenue or spend
anomalies, and named enterprise accounts.

## 12. Skills

| skill | status | owns |
|---|---|---|
| gtm | extended | focus, fit, bets, dispatch, digest, reports |
| product-context | new | GTM profile, positioning, learnings; absorbs today's `profile.md` |
| customer-research | new | ICP attention, customer language, objections (treg: Reddit, reviews, forums) |
| writing | new | claims gate, AI-tell rules, information-gain gate, voice; claims-guard mode |
| measurement | new | tracking check, attribution, PostHog setup, metrics sync, report |
| ai-visibility-audit | kept | panel runs (add core vs exploratory cohorts) |
| ai-search-optimization | kept | access, llms.txt, structured data |
| entity-presence | kept | profiles and directories |
| citation-outreach | extended | press, link and partner modes |
| comparison-pages | kept | |
| one-pager → content | renamed, extended | page types: answer pages, integration pages, one-pagers, battlecards |
| competitive-intel | new | profiles, teardown history, watch (moves `watch_pages.py` in) |
| seo | new | crawl, index, query map, Search Console |
| outbound | new | account and signal research, sequences as drafts |
| creative | new | section 10 |
| social | new | organic posts from launches, pages and bets |
| cro | new | pages and forms, as PRs |
| activation | new | signup, onboarding, paywalls, in the product repo |
| experiments | new | test design, sample size, PostHog flags; bet close |
| lifecycle | new | email flows, churn and cancel flows, referrals |
| paid | new | read-only audits first, then capped changes |

## 13. Phases

Each phase ships with tests for the new `gtm.py` behaviour and at least one eval per new skill
run in CI against a fixture repo.

| phase | version | delivers | done when |
|---|---|---|---|
| 1 · foundations | 0.4 | `product-context` with GTM profile, fit (`gtm.py fit`), tracks and focus (`gtm.py focus`) with Discoverability's standing share, job contract, state store (`dir`, `git`, `repo` backends), bet ledger, `writing`, guardrails references, eval harness | an Obscript-like fixture picks the right focus with a stated reason; an enterprise fixture marks UGC ineligible; a tick with the `dir` backend leaves the product repo untouched except for PRs |
| 2 · measurement | 0.5 | `measurement` with PostHog setup and sync, Search Console sensor, revenue source setup (`stripe`, `revenuecat`, `events` first), monthly report, HTML fallback | the dashboard shows AI visibility and the funnel side by side; a bet closes from metrics alone |
| 3 · demand | 0.6 | `customer-research`, `competitive-intel`, `seo`, `outbound` (drafts, then approve-to-send), `creative`, `social`, `content` rename | attention scores come from data; one creative asset goes from brief to review page to measured |
| 4 · conversion | 0.7 | `cro`, `activation`, `experiments` with PostHog flags | an A/B test runs end to end as a PR plus flag |
| 5 · send and spend | 0.8+ | `lifecycle`, `paid`, bounded authority | a capped send and a capped budget change run with the kill switch tested |

## 14. Migration from 0.3

- `gtm.py init` becomes idempotent over existing state: it adds `tracks`, `fit` and `focus` to
  `gtm.json`, keeps `last_run` and spend, and maps the current ladder onto Discoverability.
- `profile.md` folds into `product-context.md`; the GTM profile section is drafted and needs one
  human confirmation before fit is used. Until then, fit defaults to the motion matrix alone.
- Existing jobs keep their names and gain `track` and `kind`.
- `gtm.py migrate --to dir|git` moves `.marketing/` out of the product repo into the chosen state
  store, sends its metrics history to PostHog when credentials exist, and opens a PR that deletes
  `.marketing/` from the repo (history rewrite is left to the team). Teams that want the old
  behaviour pick the `repo` backend and nothing moves.

## 15. Decisions (2026-11-01)

1. **No compatibility with other skill libraries.** The plugin doesn't read or import their context
   files.
2. **Track order for a given product is decided by the plugin** when it runs against that product,
   through fit and the bottleneck rule. Discoverability is a standing priority in every motion
   (section 6).
3. **Sending authority is earned in steps**: draft, then approve-to-send, then bounded, from a
   dedicated inbox on a separate sending domain (section 11).
4. **References are written from first principles.** No text is copied from other libraries, so no
   attribution is needed. Ideas and frameworks can be used freely; copied text would carry the
   source's licence terms.
5. **PostHog Cloud** is the reference setup.
6. **Marketing data stays out of the product repo by default.** PostHog holds metrics and
   experiment results; a state store outside the repo holds operator state (section 9.1).

## 16. Research findings (2026-11-01)

1. **treg and PostHog or Stripe:** treg's catalog has neither. The agent uses PostHog's API directly
   with two scoped keys. Revenue reaches it only through PostHog, from Stripe, RevenueCat, other
   billing sources or purchase events (section 9.2).
   Search Console and GA4 stay on treg's connected accounts.
2. **Scheduled dashboard reports:** PostHog's free plan includes up to 5 email or Slack
   subscriptions; pay-as-you-go ($0 base) makes them unlimited. The reference setup uses one
   (section 9.2).
3. **Channel-fit defaults:** set from buyer surveys and CAC benchmarks (section 4.3). The surveys
   support a high AI-search fit for every B2B motion and lower trust in social feeds than in peers;
   cost benchmarks are too inconsistent to rely on, so economics uses conservative floors that
   measured costs replace.
4. **Stripe or RevenueCat:** different jobs. RevenueCat covers mobile store subscriptions and
   costs 1% of tracked revenue above $2,500 a month; for web billing, Stripe through PostHog gives
   the same revenue metrics at no extra cost. Revenue is a pluggable source (section 9.2).

Sources: [G2 survey coverage](https://www.marketscale.com/industries/marketing-tech/b2b-buyers-are-forming-vendor-shortlists-before-ever-talking-to-sales-and-ai-is-why),
[Forrester 2026 survey coverage](https://authoritytech.io/curated/forrester-genai-b2b-buyer-starting-point-shortlist-2026),
[SurveyMonkey and Reddit study](https://www.cmswire.com/the-wire/new-research-from-surveymonkey-and-reddit-reveals-why-trust-is-the-new-currency-in-b2b-buying/),
[CAC payback benchmarks](https://www.saashero.net/strategy/maxio-cac-benchmarks-b2b-saas/),
[PostHog pricing](https://posthog.com/pricing),
[PostHog subscriptions](https://posthog.com/docs/product-analytics/subscriptions),
[PostHog Stripe source](https://posthog.com/docs/data-pipelines/sources/stripe),
[PostHog revenue platforms](https://posthog.com/docs/revenue-analytics/payment-platforms),
[RevenueCat pricing](https://www.revenuecat.com/pricing/).
The survey figures come from secondary coverage; the primary G2 and Forrester reports were not
read.
