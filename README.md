# marketing — growth skills for coding agents

A Claude Code plugin for marketing done from inside the product repo, by an agent that can read
the code. It runs as a growth operator: it measures the funnel, picks the part that's holding growth
back, and works on it with skills that ship PRs and drafts for a human to approve. The deepest
track today is **agent discoverability**: getting a product found, read, cited and recommended by AI
answer engines (ChatGPT, Perplexity, Google AI Overviews and AI Mode, Gemini, Claude, Copilot) and
the agents built on them.

## Start here: `gtm`

`/marketing:gtm` is the single entry point. Run it once in a product repo (`init`), then let a
daily scheduler call it (`tick`).

### Tracks and focus: where the product is stuck

Growth work is split into tracks, each a ladder of rungs tested against data. `gtm.py` checks every
track on each tick and picks one **focus**: the track whose weakest funnel stage holds growth back,
filtered by what fits the product and who buys it.

```mermaid
flowchart TD
    P["GTM profile<br/>motion · deal size · cycle · where buyers look"] --> FIT["Fit<br/>which channels are worth trying"]
    M["Metrics<br/>funnel counts · audits · access checks"]
    subgraph T["Tracks (each a ladder of rungs)"]
        direction LR
        T0["Measurement<br/>instrumented → attributed<br/>→ funnel visible"]
        T1["Discoverability<br/>reachable → known<br/>→ associated → preferred"]
        T2["Demand<br/>indexed → ranking<br/>→ visited → pipeline"]
        T3["Conversion<br/>first step → activating<br/>→ paying"]
        T4["Retention<br/>retained → expanding<br/>→ referring"]
        T5["Paid (off until a human turns it on)<br/>tracked → profitable<br/>→ scaling"]
    end
    M --> T
    FIT --> F
    T --> F["Focus rules<br/>1 alerts first · 2 prelaunch: discoverability<br/>3 measurement gates the funnel · 4 weakest stage<br/>5 fit · 6 hold 30 days"]
    F --> W["Work: 60% focus · 25% discoverability until preferred · rest explores"]
```

Discoverability is a standing priority: buyers in every sales motion now shortlist with AI
assistants, so it keeps a share of the work until it reaches `preferred`.

### What one scheduled run does

```mermaid
flowchart TD
    A["Daily scheduler<br/>(Hermes cron, /schedule, CI)"] --> B["gtm skill, tick mode"]
    B --> C["gtm.py decides:<br/>focus, due jobs, budget,<br/>cooldowns, bets past their check date"]
    C --> D["Run due jobs<br/>audit · access check · page watch · news watch · metrics sync<br/>outreach refresh · news stories worth acting on<br/>and, weekly, the work session: 2 actions, each a bet"]
    D --> E["Metrics and audit scores<br/>written to the state store"]
    D --> F
    F["Outputs<br/>PRs for pages and site changes<br/>drafts for outreach, posts, pitches and profiles"]
    D --> G["Digest in the state store, daily report with charts<br/>'Needs you' items sent to chat (one each) or GitHub"]
    F --> G
    G --> H["Human merges PRs, sends drafts,<br/>approves with a reaction or reply,<br/>asks the operator questions in chat"]
    E -.->|"bets close against the metrics"| C
```

Every improvement is a **bet** with a metric, a baseline, an expected value and a check date. When
the check date comes, `gtm.py bet close` judges it from the recorded metrics, and results feed back
into which tactics get tried next. A result becomes a learning only after a human accepts it.

| skill | what it does | treg spend |
|---|---|---|
| `gtm` | Entry point and operator: init (incl. pre-launch), daily tick, launch, status; focus, fit, bets, budget, digest | ~$8-12/month at defaults |
| `product-context` | The GTM profile (sales motion, deal size, buyers, cycle) plus positioning, objections, customer language, voice and accepted learnings; every skill reads it | free |
| `measurement` | Tracking and attribution (AI referrers included), funnel stage counts, the revenue source, the Search Console sensor and a monthly scorecard, with PostHog Cloud as the system of record | free (PostHog free tier) |
| `writing` | The gates every draft passes: claims from the ledger, an information-gain test, no AI-tell phrasing | free |
| `ai-visibility-audit` | Runs a fixed prompt panel across 5 engines, scores mention, citation, share of voice and gaps, diffs against the last run | ~$0.02 per prompt across all engines |
| `ai-search-optimization` | Bot access (robots.txt + CDN), llms.txt, feeds, quick answers, JSON-LD, IndexNow, AI-referral tracking; verifies against production | ~free |
| `content` | Claims ledger from the code, intent mining, engine recon, evidence, draft, review gates, ship, track | ~$0.05-0.30 per page |
| `citation-outreach` | Ranks the exact third-party URLs engines cite when you lose, triages them, finds verified contacts, drafts honest pitches/replies for a human to send, watches for the mention | <$0.50 per 30 targets |
| `entity-presence` | Canonical entity card, trained-knowledge vs retrieval probe, profile inventory (Wikidata, directories, stores, GitHub), paste-ready fixes, sameAs wiring | ~$0.15 per probe |
| `comparison-pages` | Sourced competitor dossiers, a fairness-gated comparison grid, vs/alternatives/switching pages via `content` | ~$0.05-0.10 per page |
| `competitive-intel` | Competitor profiles, teardowns of how they grew, and the page-change watcher the other skills share | ~free to ~$0.50 per teardown |
| `seo` | Technical crawl (status, noindex, canonicals, thin HTML, orphans, broken links), the query map, Search Console rankings | free |
| `customer-research` | Where buyers actually spend attention (measured, feeding fit), their language and objections | ~$0.10-0.50 per study |
| `outbound` | Buying-signal sweeps, account research, verified contacts, drafts into batches; sends only approved batches on channels a human opened, within caps | ~$0.50 per weekly sweep |
| `creative` | Briefs, channel research, scripts and variants, generation through treg's image, video and voice models, a review page; nothing publishes | per asset: ~$0.01 images, ~$1 video |
| `cro` | Finds which page, step and source leaks before the first step; reviews the page; ships one change at a time as a flagged PR with a bet | free |
| `activation` | Defines the activation event with the team; shortens signup and onboarding to the first value moment; upgrade moments tied to value; PRs behind flags | free |
| `experiments` | Picks A/B, holdout, staggered or before/after from the traffic (`stats.py`), fixes the metric first, checks sample ratio, closes bets from real counts | free |
| `lifecycle` | Onboarding, trial, dunning, a fair cancel flow, win-back, referrals and review requests, as templates, PRs or drafts for the email platform; judged against holdouts | free |
| `paid` | Off until a human turns it on. Read-only audits (tracking, waste, structure, payback), competitor ad research, proposals; budget changes only under granted caps | free audits; ~$0.01 per competitor ad lookup |
| `social` | Organic posts and community answers drafted from launches, pages, bets and news, for a human to post | free |
| `daily-report` | A daily report for a team chat channel: what moved and whether it's more than noise, what shipped, charts drawn in D3 for the day's finding, PostHog links, and one message per approval to react to; also answers "how are we doing" with a chart. Slack via Hermes: [docs/hermes-slack.md](docs/hermes-slack.md) | free (PostHog queries) |
| `launch-video` | A 20-45 s motion-design video for a release, built with HyperFrames from what actually merged and the real product screens: claims-checked copy, local voiceover, a human approves the preview before the final render, and a human posts it | free (local render and voice) |
| `news` | Watches current events in the category (news, Google News, Hacker News, X, optionally court filings) through treg, scores and queues stories, and turns the good ones into page refreshes, timely posts or press pitches | ~$0.01-0.05 per sweep |

### Where the data lives

The product repo only receives PRs. The program's memory (config, metrics, bets, audit runs,
digests, drafts) lives in a **state store** outside it: `~/.marketing/<owner>-<repo>/` on the
agent's machine by default, or a private git repo for hosts that don't keep files between runs.
`gtm.py where` prints the location. Installs from 0.3 that kept `.marketing/` in the repo keep
working and can move with `gtm.py migrate --to <dir or git URL>`.

### Where the numbers live

Metrics and experiment results go to **PostHog Cloud** next to the product's own funnel: the
`measurement` skill sends the operator's events and pulls funnel counts and revenue back, and a
"Growth" dashboard with a weekly email or Slack subscription is the team's view. Revenue comes from
Stripe by default (or RevenueCat, Paddle, Chargebee, Polar, or the product's own purchase events),
always read through PostHog. Teams without PostHog get a monthly self-contained HTML scorecard from
the state store (`measurement/scripts/report.py`) and can record the metrics by hand.

### How much the agent may do

Anything that sends or spends moves through three levels, per channel, and only a human moves a
channel up (`gtm.py authority`):

1. **Draft** (every channel starts here): the agent writes; a human sends, posts or changes spend.
2. **Approve-to-send** (email channels): the agent sends exactly the batch a human approved, within
   a daily cap, to no suppressed address and no one inside a cooldown.
3. **Bounded**: the agent sends the exact text of a template the human approved, to addresses on a
   list the human approved, without per-batch approval (cold and user email only; editor and creator
   pitches never). Or it moves an existing campaign's daily budget inside a cap, a per-change limit
   and once a day. Email needs 30 days at approve-to-send, 50 sends, a 2% reply rate and no
   complaints first; one complaint drops it back.

Lowering authority and `gtm.py pause` work in any run and stop things at once; only a human raises
authority or resumes. Posts and community replies are always sent by a human.

## Install

### Prerequisites

- **[treg](https://treg.to)**: the skills get their live data (AI engine answers, search results,
  keywords, forums, page reads) through it. Install the CLI and sign in:
  `curl -fsSL https://treg.to/install.sh | sh`, then follow https://treg.to/llms.txt. Paid calls
  draw on a prepaid team balance; a typical month at `gtm` defaults is about $8-12. Without treg,
  the skills fall back to plain web search and skip the paid audit and access-check jobs, and they say so.
- **`python3`** (3.9 or newer). The scripts use only the standard library; nothing to `pip install`.
- **`gh`**, signed in, if you want `gtm` to open PRs.

### Claude Code

```
/plugin marketplace add williampsmith/marketing-skills
/plugin install marketing@marketing-skills
```

Skills are invoked as `/marketing:<skill>` (start with `/marketing:gtm`), or picked up
automatically from their descriptions. Update later with `/plugin marketplace update marketing-skills`.

### Other agents (Hermes, Codex, Cursor, …)

The skills are plain Agent Skills folders (`SKILL.md` plus scripts), so any agent that reads them
can use them. Clone the repo and link the skills into the agent's skills directory, keeping them
side by side (skills call siblings' scripts through `../<skill>/scripts/`):

```bash
git clone https://github.com/williampsmith/marketing-skills.git
ln -s "$PWD"/marketing-skills/skills/* ~/.hermes/skills/    # or that agent's skills directory
```

A `git pull` in the clone updates them. Scheduling uses the agent's own scheduler; see
`skills/gtm/references/hosts.md`.

### Running it unattended on a server

[`docs/remote-setup.md`](docs/remote-setup.md) is the playbook for both Claude Code (cloud routine or
your own server) and Hermes Agent: credentials with least privilege, where the state store lives,
the supervised `init`, the daily heartbeat, the first week, and day-to-day operation.

## Why built this way

- **Measure first.** Every change is a bet judged against recorded metrics, so "it worked" is a
  number, not a feeling.
- **Decide in code.** Dates, money, fit, focus, cooldowns and bet results come from `gtm.py`, so every
  run on every host agrees on the facts.
- **Fit before effort.** The product's sales motion and buyers decide which channels are worth
  trying; the product's own results then overrule the defaults.
- **Claims come from code.** Marketing copy written by an agent that can read the code should never
  claim something the code doesn't do. The claims ledger enforces that and keeps you on the right
  side of claim-substantiation rules.
- **Thought leadership over pitch.** Answer pages win citations by being the best answer to the
  question; the product shows up in a separate, honest section at the end.
- **Humans publish.** The agent opens PRs and writes drafts. Sending authority is earned per channel.
- **treg as the data layer.** Ask for the job, not a vendor, check the price before spending, and
  prefer routed endpoints with cost ceilings. Endpoint ids in these docs are dated examples, and the
  skills tell the agent to re-discover them.

## Develop

```
python3 -m unittest discover tests        # script tests (stdlib only)
```

See `CLAUDE.md` for conventions, `docs/design/growth-operator.md` for the design, and
`docs/skill-ideas.md` for the backlog.

## License

MIT. See `LICENSE`.
