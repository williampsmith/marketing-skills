# CLAUDE.md

A Claude Code plugin (`.claude-plugin/plugin.json`, name `marketing`) of marketing skills for
coding agents. It is also its own marketplace (`.claude-plugin/marketplace.json`). See README.md for
the loop and `docs/design/growth-operator.md` for the design being implemented.

## Layout
- `skills/<name>/SKILL.md`: frontmatter `name` + `description`. The description is the trigger,
  so keep it specific about when to use the skill. Depth goes in `references/`, deterministic work in `scripts/`.
- `skills/gtm/scripts/marketing_state.py`: resolves the state store (`dir`, `git` or `repo`
  backend; `$MARKETING_STATE`, then `~/.marketing/config.json`, then a legacy `.marketing/gtm.json`,
  then `~/.marketing/<owner>-<repo>/`). Every script gets its paths from `state_root()`.
- `skills/gtm/scripts/gtm.py`: the state engine. `where`, `init`, `tick`, `status`, `focus`, `fit`,
  `tracks`/`ladder`, `next`, `budget`, `record`, `may`, `metric`, `bet`, `learnings`, `pause`/`resume`,
  `digest`, `store use`, `sync pull|push`, `migrate`. The gtm skill must ask it rather than reason
  about dates, money, fit, focus or experiment results.
- `skills/gtm/references/`: `channel-fit.json` (channel × motion matrix, cost floors, tactics; read by
  `gtm.py`) and `channel-fit.md`, `funnel-templates.json` (stages and floors per motion),
  `tracks.md`, `guardrails.md` (action tiers, sending authority, kill switch, cooldowns),
  `compliance.md` (email law, endorsements, personal data), `hosts.md`, `plan-template.md`.
- `skills/measurement/scripts/`: `posthog.py` (send the outbox, pull funnel counts, source capture and
  configured HogQL queries, tracking check; keys only from env), `search_console.py` (Search Console
  through treg), `report.py` (self-contained HTML scorecard). They import `gtm` for metrics and the
  store. `tests/test_measurement.py` replaces every network call (`posthog.http`, `fetch_page`,
  the treg call) and must stay offline.
- `skills/product-context/` (GTM profile, positioning, learnings) and `skills/writing/` (claims,
  information-gain and AI-tell gates) are shared by every drafting skill.
- `skills/ai-visibility-audit/scripts/run_panel.py` (treg CLI batch runner) and `score_panel.py`
  (scoring + diff). `skills/ai-search-optimization/scripts/check_ai_access.py` (live site check).
  `skills/citation-outreach/scripts/outreach_targets.py` (rank cited URLs).
  `skills/competitive-intel/scripts/watch_pages.py` (page change + mention watcher, shared by
  comparison-pages, citation-outreach and entity-presence via `../competitive-intel/scripts/`).
  `skills/seo/scripts/crawl_check.py` (technical crawl), `skills/customer-research/scripts/attention.py`
  (attention weights from research evidence), `skills/outbound/scripts/send_batch.py` (sends only
  approved batches, through gtm.py's `send_capacity` and hashed approvals; SMTP from env only; tests replace
  `smtp_connect`), `skills/creative/scripts/review_page.py` (self-contained review page; refuses
  assets without a claim row or an AI disclosure), `skills/experiments/scripts/stats.py` (sample
  size, run length, two-proportion z-test, holdout arithmetic; `tests/test_experiments.py` checks
  it against textbook values and against gtm.py's own z-test).
  `skills/lifecycle/` and `skills/paid/` are prose only: lifecycle sends through
  `send_batch.py` (channel `lifecycle_email`), paid gates spend through `gtm.py spend check|log`.
  Sending and spend authority (`authority`, `approve`, `outcome`, `spend`, `track`; levels draft,
  approve_to_send, bounded; promotion criteria in `PROMOTION`; bounded email only on
  `BOUNDED_SEND_CHANNELS`, with `<state>/templates/<id>.txt` and `<state>/segments/<id>.txt` pinned
  by hash at grant; spend gated on the resulting daily budget) lives in gtm.py and is tested in
  `tests/test_sending.py` and `tests/test_authority.py`.
  All Python is **stdlib only** and runs with plain `python3` (3.9+), since it executes inside
  other people's repos.
- `tests/`: `python3 -m unittest discover tests`. Run after any script change. Tests that touch
  state subclass `tests/helpers.py` `StoreCase`, which points `MARKETING_HOME` at a temp dir so
  nothing writes to the real home directory.
- `evals/`: `claude plugin eval` cases (one directory per case: `prompt.md` plus `graders/`). Prefer
  the free graders (`tool_used`, `regex`, `file_exists`); `llm` graders cost judge calls.
- CI: `.github/workflows/checks.yml` (PRs and pushes to main) compiles the scripts and runs the tests
  on Python 3.9 and latest, checks that every JSON parses, runs `claude plugin validate` (pinned CLI
  version), checks that each skill folder matches its frontmatter `name`, and checks that both
  manifests carry the same version. `.github/workflows/evals.yml` runs the evals and is
  **manual-dispatch only**, because each run spends model credit; it needs an `ANTHROPIC_API_KEY`
  secret and caps cost with `--max-cost-usd`.

## Conventions
- State goes in the state store, `<state>/` (the `root` from `gtm.py where`), never in the product
  repo: `gtm.json`, `product-context.md`, `claims.md`, `entity.md`, `prompt-panel.json`, `pages.md`,
  `pages/<slug>/`, `runs/<date>/`, `metrics/<metric>.jsonl`, `experiments.jsonl`, `spend.jsonl`,
  `posthog-outbox.jsonl`, `plan.md`, `digests/`, `access/`, `watch/`, `watch.json`, `outreach/`,
  `competitors/`, `entity/`, `launches/`, `seo/`, `research/`, `outbound/accounts/`,
  `sends/<batch>/`, `sends.jsonl`, `approvals.jsonl`, `outcomes.jsonl`, `ad-spend.jsonl`,
  `suppression.csv`, `lifecycle/<flow>/`, `paid/`, `creative/<batch>/`, `social/`. Keep those names stable across skills. Scripts resolve the
  directory through `marketing_state.state_root()`; skill prose writes `<state>/…`. The product repo
  only receives PRs.
- treg: skills describe jobs and give **dated example** endpoint ids, always with "verify with
  `catalog_get`". Never hard-code an id in prose without a date. Batch through the CLI and look
  things up through MCP. State the price before spending, rate calls that invite `review`, and
  send `feedback` on breakage.
- Product claims in generated content must trace to the claims ledger. Never weaken that gate.
- Facts that age (bot names, CDN defaults, rich-result policy, laws) carry a "checked <date>".
- Skills must stay portable across agents (Hermes, Codex, …): no host-specific tools in required
  steps; name the host scheduler only as an example.
- A new skill that should run on a schedule gets a job in `DEFAULT_JOBS` (gtm.py) and a recipe
  row in the gtm SKILL.md table; never a separate scheduler entry. Every job fills the contract:
  `every_days`, `usd`, `stages`, `skill`, `track`, `kind` (sensor, improvement, review), and the
  prose fields `acts_when`, `self_check`, `stop`; plus `requires`, `cooldown_days` with
  `dedupe_key`, and `max_actions` where they apply.
- Authority only ever goes up by a human's explicit instruction. Code that sends or spends must ask
  gtm.py first (`send_capacity`, `spend_allowed`) and fail closed.
- Anything that sends, spends or publishes follows `skills/gtm/references/guardrails.md` and
  `compliance.md`. Personal data stays in the state store, never in PostHog properties or the repo.
- Reference text is written from first principles; don't copy text from other skill libraries.
- Version: bump `version` in both manifests together.
- Turning a job off: set `"enabled": false` on it in gtm.json. Deleting it doesn't stick; `upgrade()` restores
  missing default jobs.
- Run scripts with the working directory at the product repo root; gtm.py refuses the plugin repo itself.
