# CLAUDE.md

A Claude Code plugin (`.claude-plugin/plugin.json`, name `marketing`) of marketing skills for
coding agents. It is also its own marketplace (`.claude-plugin/marketplace.json`). See README.md for the loop.

## Layout
- `skills/<name>/SKILL.md`: frontmatter `name` + `description`. The description is the trigger,
  so keep it specific about when to use the skill. Depth goes in `references/`, deterministic work in `scripts/`.
- `skills/ai-visibility-audit/scripts/run_panel.py` (treg CLI batch runner) and `score_panel.py`
  (scoring + diff). `skills/ai-search-optimization/scripts/check_ai_access.py` (live site check).
  `skills/citation-outreach/scripts/outreach_targets.py` (rank cited URLs).
  `skills/comparison-pages/scripts/watch_pages.py` (page change + mention watcher, shared by
  comparison-pages, citation-outreach and entity-presence via `../comparison-pages/scripts/`).
  `skills/gtm/scripts/gtm.py` (state engine: due jobs, budget, ladder, digest data; the gtm
  skill must ask it rather than reason about dates or money).
  All Python is **stdlib only** and runs with plain `python3`, since it executes inside other
  people's repos.
- `tests/`: `python3 -m unittest discover tests`. Run after any script change.

## Conventions
- State a skill writes in a product repo goes under `.marketing/` (profile.md, claims.md,
  prompt-panel.json, pages.md, pages/<slug>/, runs/<date>/, gtm.json, plan.md, spend.jsonl,
  digests/, access/, watch/, outreach/, competitors/, entity.md). Keep those names stable across skills.
- treg: skills describe jobs and give **dated example** endpoint ids, always with "verify with
  `catalog_get`". Never hard-code an id in prose without a date. Batch through the CLI and look
  things up through MCP. State the price before spending, rate calls that invite `review`, and
  send `feedback` on breakage.
- Product claims in generated content must trace to the claims ledger. Never weaken that gate.
- Facts that age (bot names, CDN defaults, rich-result policy) carry a "checked <date>".
- Skills must stay portable across agents (Hermes, Codex, …): no host-specific tools in required
  steps; name the host scheduler only as an example.
- A new skill that should run on a schedule gets a job in `DEFAULT_JOBS` (gtm.py) and a recipe
  row in the gtm SKILL.md table; never a separate scheduler entry.
- Version: bump `version` in both manifests together.
