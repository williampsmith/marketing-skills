# Design: the growth operator (next version)

Status: draft for review · 2026-11-01 · targets plugin 0.4 → 1.0 in phases (section 13)

Today the plugin is an AI-search operator: seven skills, one entry point (`gtm`), and a state
engine (`gtm.py`) that schedules jobs, enforces a budget and works up one ladder. This spec makes it
a growth operator for the whole funnel without giving up what makes it runnable unattended.

Background: the comparison with `coreyhaines31/marketingskills` (a 53-skill consultative library)
concluded that we should match its coverage with fewer skills, keep execution in code, and adopt
its product-context file, loop anatomy, guardrails and writing rules.

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
| `motion` | `self_serve` · `sales_assisted` · `enterprise` · `consumer_app` · `ecommerce` · `open_source_devtool` | picks the funnel template |
| `acv_usd` | number (annual contract value; for consumer, lifetime value) | bounds what each channel may cost per customer |
| `buyer` / `user` | roles, seniority, team | who the content and outreach address |
| `buying_committee` | 1 · 2-4 · 5+ | multi-stakeholder deals favour proof, comparisons and sales material |
| `cycle_days` | typical days from first touch to paid | sets experiment horizons; long cycles need leading indicators |
| `attention` | where buyers look, ranked, with evidence (e.g. "LinkedIn: 0.8, from customer-research") | the strongest fit input; measured, not assumed |
| `regulated` | none · light · heavy (finance, health, legal, gov) | restricts claims, channels and creative formats |
| `geo` | markets | channel availability and compliance (cold email rules differ by country) |
| `stage` | prelaunch · launched · scaling | what is measurable yet |

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
| open_source_devtool | reach → repo/docs visit → install → active project → paid/enterprise lead | active installs |

Floors start from benchmarks in `references/benchmarks.md` for the motion and are replaced by the
product's own baseline after 30 days of data.

### 4.3 Channel fit

`references/channel-fit.md` holds a matrix of channel × motion with a default fit from 0 to 1 and
hard exclusions. `gtm.py fit` combines it with the profile:

```
fit(channel) = matrix[motion][channel]
             × attention_weight(channel)          # from customer-research; 0.5 if unknown
             × economics(channel, acv_usd)        # typical cost per customer vs acv; 0 if it can never pay back
             × cycle_factor(channel, cycle_days)  # fast-feedback channels lose value when results land months later
             × compliance(channel, regulated, geo)
```

- **Eligible** if `fit ≥ 0.25` and no hard exclusion applies. Ineligible channels never get
  improvement jobs; their sensors don't run.
- **Prior** for experiment allocation (section 8.4) is the fit score.
- The digest lists ineligible channels once a month with the reason, so a human can override
  (`gtm.json → fit.overrides`).

Two examples, using the default matrix:

| channel | self-serve consumer tool, $10/mo | enterprise compliance product, $60k ACV |
|---|---|---|
| AI search and comparison pages | 0.8 | 0.9 (buyers research and shortlist with AI) |
| SEO content | 0.8 | 0.6 |
| Outbound to named accounts | 0 (economics) | 0.9 |
| LinkedIn thought leadership | 0.3 | 0.8 |
| Analyst and review sites (G2, Gartner) | 0.4 | 0.8 |
| Short-form UGC (TikTok, Reels) | 0.8 | 0.05 (attention) → ineligible |
| Founder or demo video on LinkedIn and YouTube | 0.4 | 0.6 |
| Paid social | 0.6 | 0.3 (ABM-targeted LinkedIn only) |

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
5. **Hysteresis.** The focus holds until its rung is met, the monthly `strategy_review`, or another
   stage falls below half its floor.

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
| `output` | `".marketing/conversion/…"`, `"pr"`, `"draft"` | digest |

### 7.2 Dispatch

- `tick` returns due jobs, each self-contained: inputs, output paths under `.marketing/<track>/`,
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

`.marketing/experiments.jsonl`, one record per bet, written by `gtm.py bet open` and closed by
`gtm.py bet close`:

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

- The focus track gets about 80% of improvement work; the rest goes to the secondary track and to
  exploration.
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

### 9.1 Shared files

```
.marketing/
  product-context.md     # GTM profile, positioning, ICP, objections, customer language, voice, proof, learnings
  claims.md              # claims ledger (unchanged)
  gtm.json               # state: tracks, floors, fit, focus, jobs, budget, notify
  metrics/<metric>.jsonl # {"date","value","source","track","cost_usd"} one row per observation
  experiments.jsonl      # the bet ledger
  spend.jsonl            # unchanged
  <track>/…              # each track's working files
  digests/, reports/     # weekly digest, monthly review
```

The repo is the audit trail. `gtm.py` computes rungs, focus and bet results from `metrics/`.

### 9.2 Tool choices (opinionated)

| need | tool | notes |
|---|---|---|
| Product and web analytics, funnels, experiments, flags, surveys | **PostHog** | system of record for the funnel and the team's dashboard; self-hostable |
| Search data | Search Console, GA4 via treg connected accounts | free |
| AI visibility, SERP, backlinks, social, ads library, enrichment | **treg** | metered |
| Revenue | Stripe (read-only key) | MRR, churn, expansion |
| Creative generation | treg (Seedance, image models, voice) | via the `make-ugc` treg skill where it fits |

To verify before building: whether treg proxies PostHog and Stripe, and which PostHog plans
include scheduled dashboard emails.

### 9.3 Where people see it

- **PostHog dashboard, "Growth":** the operator sends its own metrics as `marketing_metric`
  events (AI mention, citation and share of voice per engine, rung status, focus, spend, bet
  results) next to the product funnel. One link for the team.
- **Fallback for teams without PostHog:** `gtm.py report` renders a self-contained HTML scorecard
  into `.marketing/reports/`; on Claude Code it may also be published as an Artifact.
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
| 1 · autonomous | read, measure, research, draft, stage, open PRs, write `.marketing/` | allowed |
| 2 · gated | publish, send, spend, change ad or email settings, contact a person, delete | human approves each, via the digest or a review page |
| 2 · bounded | a tier-2 action with explicit authority in `gtm.json → authority` | allowed within caps: per-run and daily volume, spend, allowlist of accounts or lists |

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
| 1 · foundations | 0.4 | `product-context` with GTM profile, fit (`gtm.py fit`), tracks and focus (`gtm.py focus`), job contract, `metrics/` store, bet ledger, `writing`, guardrails references, eval harness | an Obscript-like fixture picks the right focus with a stated reason; an enterprise fixture marks UGC ineligible |
| 2 · measurement | 0.5 | `measurement` with PostHog setup and sync, Search Console and Stripe sensors, monthly report, HTML fallback | the dashboard shows AI visibility and the funnel side by side; a bet closes from metrics alone |
| 3 · demand | 0.6 | `customer-research`, `competitive-intel`, `seo`, `outbound` (drafts), `creative`, `social`, `content` rename | attention scores come from data; one creative asset goes from brief to review page to measured |
| 4 · conversion | 0.7 | `cro`, `activation`, `experiments` with PostHog flags | an A/B test runs end to end as a PR plus flag |
| 5 · send and spend | 0.8+ | `lifecycle`, `paid`, bounded authority | a capped send and a capped budget change run with the kill switch tested |

## 14. Migration from 0.3

- `gtm.py init` becomes idempotent over existing state: it adds `tracks`, `fit` and `focus` to
  `gtm.json`, keeps `last_run` and spend, and maps the current ladder onto Discoverability.
- `profile.md` folds into `product-context.md`; the GTM profile section is drafted and needs one
  human confirmation before fit is used. Until then, fit defaults to the motion matrix alone.
- Existing jobs keep their names and gain `track` and `kind`.

## 15. Open questions

1. Read `.agents/product-marketing.md` when it exists, for teams already using the other library?
   Proposed: yes, import into `product-context.md` at init.
2. Which track and channel order for Obscript after Discoverability? Its profile decides; to be
   confirmed in its init.
3. When to grant bounded send authority, and from which inbox?
4. Borrowed frameworks: write references from first principles and credit sources where a
   specific framework is adopted (e.g. loop anatomy).
5. PostHog cloud or self-hosted for the reference setup?
