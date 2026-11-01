---
name: ai-visibility-audit
description: Measure how AI answer engines (ChatGPT, Perplexity, Google AI Mode, Gemini, Claude) talk about a product - whether they name it, cite its site, who they name instead, and which sources they cite - using a fixed prompt panel run through treg. Use when the user asks about AI visibility, AEO/GEO, LLM share of voice, "does ChatGPT recommend us", tracking AI search over time, or before and after ai-search-optimization or one-pager work. Writes a dated scoreboard to .marketing/runs/ that later runs diff against.
---

# AI visibility audit

The scoreboard for agent discoverability. Nothing else in this plugin can claim a result
without it: run it before changing anything, and on a schedule after.

The output answers four questions, per engine and per prompt bucket:

1. **Named?** Does the answer mention the brand (mention rate, position among named brands)?
2. **Cited?** Does it link the brand's own domain (citation rate)?
3. **Who instead?** Which competitors are named where we are not (gaps, share of voice)?
4. **From where?** Which domains do the engines cite on the gap prompts (citation targets)?

Plus the **fan-out queries** ChatGPT ran behind each answer: the searches an answer is
assembled from, and the best list of intents a one-pager can target.

## Requires treg

All engine calls go through treg (`treg --version` works and `treg balance` shows credit;
otherwise follow https://treg.to/llms.txt). Batch runs use the **treg CLI** through
`scripts/run_panel.py`. A batch over MCP `call` would put every answer in the context window.
Use MCP `catalog_search` / `catalog_get` for discovery and pricing, and MCP `call` for a single
spot check.

## State in the product repo

Everything lives in `.marketing/` at the product repo root. Commit it; the history is the trend line.

```
.marketing/
  profile.md            positioning, ICP, category words, proof points (shared by all skills)
  prompt-panel.json     brand + aliases + domains, competitors, engines, prompts
  runs/<YYYY-MM-DD>/    answers.jsonl, raw/, score.json, report.md
```

## The run

### 1. Bootstrap the profile (first run only)

If `.marketing/profile.md` is missing, write it from the repo (README, docs, site copy,
pricing) and confirm it with the user. Keep it to one screen: product in one sentence, the
category words a buyer would type, the ICP, 3-5 competitors with domains, proof points that
the code supports, and things never to claim.

### 2. Build the prompt panel (first run, then rarely)

The panel is fixed across runs on purpose. If it changes every week, the numbers can't be
compared. See `references/panel-design.md` for buckets, sizes and mining recipes. In short:

- 20-40 prompts, written the way people ask an assistant (whole sentences with context),
  not as keywords. Buckets: `category`, `problem`, `comparison`, `alternatives`, `brand`,
  `jobs` (the task the product does).
- Mine real phrasing with treg, not imagination: keyword ideas and People-Also-Ask for the
  category words, Reddit and forum threads where buyers ask, and the fan-out queries from a
  few seed ChatGPT answers. Each recipe is in the reference.
- `brand.aliases`: spellings the model might use. Leave out generic words that would
  false-match. `domains`: every domain you own, including docs and app subdomains.
- Start from `references/prompt-panel.example.json`. Before the first run, check every
  engine with `catalog_get` (ids, params, price) and fix the `engines` block. **Never trust a
  remembered endpoint id: the catalog changes weekly.** Prefer a routed `treg.*` endpoint when
  one exists, set `X-Treg-Route-Max-Cost` on routed ones, and choose by inputs → `works` → price.

### 3. Price it, then run it

```bash
python3 <skill>/scripts/run_panel.py --dry-run            # plan + estimate
python3 <skill>/scripts/run_panel.py --limit 1            # one prompt on every engine: check shapes
python3 <skill>/scripts/run_panel.py --max-usd 3          # the run, with a ceiling
```

Tell the user the estimate before the full run. For reference, on 2026-10-31 one prompt on all five
engines cost $0.02, so 30 prompts cost about $0.60, most of it the Claude engine. The script is
resumable: rerunning skips answers already stored and only retries failures, which are free.

After the smoke call, read one `raw/` file per engine. If an engine's normalized `text` is
empty or `sources` is missing when the raw response has them, fix the panel body (an `include`
flag) or the key lists at the top of `run_panel.py`. Do not hand-edit answers.

AI answers vary from run to run. Set `"samples": 3` on the few prompts that matter most (a prompt
counts as won on an engine if any sample names you). Keep `country` fixed between runs.

### 4. Score it

```bash
python3 <skill>/scripts/score_panel.py .marketing/runs/<today> --previous .marketing/runs/<last>
```

This writes `score.json` and `report.md`. Matching is word-bounded and case-insensitive on
name + aliases, and citations are matched by domain suffix. The scoring is deterministic, so a
change in the numbers means the engines changed.

### 5. Read it like a growth engineer

Turn the report into actions. Each finding goes to the skill that fixes it:

| Finding | Meaning | Next |
|---|---|---|
| Named nowhere, even on `brand` prompts, or described wrongly | the engines don't know the entity, or confuse it with something else | `ai-search-optimization` (access) + `entity-presence` |
| Named on `brand`, absent on `category`/`problem` | known, not associated with the job | `one-pager` on the gap intents |
| Cited rarely though named | engines learned you elsewhere; your pages aren't the best source | `one-pager` answer pages + check access for that engine's bot |
| Competitor wins `comparison`/`alternatives` | they own the comparison content | `comparison-pages` |
| Same third-party pages in every gap | that's where answers come from | `citation-outreach` (ranks the exact URLs) |
| One engine far behind the rest | engine-specific access or index issue | check that bot in `ai-search-optimization` (Bing index feeds ChatGPT and Copilot) |

Write the top 3-5 actions at the end of `report.md` with the prompt ids they target, and
add the gap intents to `.marketing/pages.md` (the one-pager backlog).

### 6. Close the loop

- Commit `.marketing/`.
- Offer to schedule it weekly with whatever scheduler the agent has (Claude Code `/schedule`,
  Hermes cron, a CI cron running the scripts), always with the same panel and a `--max-usd` ceiling. Engines take days to weeks to reflect site changes, so check the trend
  over several runs rather than reacting to one.
- When a one-pager ships, set `page` on the prompts it targets so later reports can attribute wins.

## treg etiquette

- Say the price before any batch, and report what it actually cost (the run prints the spend).
- When a call result invites a review, rate it with `review(call_id, usefulness, reason)` after
  you've used it: one per invitation, about the endpoint, with no private data.
- If an engine breaks or returns unusable shapes, file `feedback` with the call ids, then use
  the next provider for that capability (`catalog_get` lists them).

## Limits to state in every report

- The panel is a sample of prompts, not of real user traffic. Treat it as an index and don't
  extrapolate it to traffic.
- The Claude row here is a model-API answer (it may answer without live web search), unlike
  the scraped consumer answers for ChatGPT, Perplexity, AI Mode and Gemini.
- A mention is not an endorsement. Read the gap answers for *how* the brand is described,
  and flag anything inaccurate: wrong facts in AI answers are a top fix for one-pagers.
