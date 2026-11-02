# Designing the prompt panel

A panel is a fixed, versioned set of prompts. Treat it like a benchmark: change it rarely,
deliberately, and say so in the run report (`"panel_version"` in the panel file helps).

## Size and mix

20-40 prompts. Fewer can't show a trend; more mostly adds cost and redundancy. A good mix:

| bucket | share | shape | example |
|---|---|---|---|
| `category` | 25% | "what's the best/safest way to …", "best tool for …" | best way to redact a PDF so text can't be recovered |
| `problem` | 25% | a person mid-problem, with context | I blacked out names but someone copy-pasted the text underneath |
| `jobs` | 15% | the task, with no product named | how do I share a contract with an AI assistant without leaking client names |
| `comparison` | 15% | "X vs Y for <who>" | Acrobat redaction vs a dedicated app for a 5-person law firm |
| `alternatives` | 10% | "alternatives to X for <constraint>" | offline alternatives to Acrobat for redaction on Mac |
| `brand` | 10% | "what is <brand>", "is <brand> safe/legit", "<brand> pricing" | is Acme Redact trustworthy |

Write prompts the way people talk to an assistant: one to three sentences with a constraint
(who, platform, budget, compliance), not a two-word keyword. Assistant prompts run much longer
than search queries, and the constraint is often what lets a niche product win.

## Mining real phrasing with treg

Discover each endpoint with `catalog_search "<job in plain words>"`, then `catalog_get` for the
price. Typical costs are fractions of a cent to a few cents.

1. **Keyword ideas** (`catalog_search "related keyword ideas"`, routed `treg.google.keywords.ideas`):
   seed with the category words from `<state>/product-context.md`. Keep the question-shaped and long-tail rows
   and drop pure navigational ones. Volume tells you which intents matter, not what to type.
2. **People Also Ask + AI Overview** (routed `treg.google.serp.organic` with `ai_overview: true`):
   PAA questions are close to how people phrase assistant prompts.
3. **Forums** (`catalog_search "reddit search posts"`, plus Hacker News and Stack Exchange
   through `treg.web.search`): copy how buyers describe the problem in their own words, along
   with their constraints.
4. **Fan-out**: run 3-5 seed prompts on ChatGPT (`cloro.ai-search.chatgpt.scrape` with
   `include.searchQueries: true`). The `searchQueries` are what the engine searched to build the
   answer, so they are intents that already exist and a strong source for panel prompts and pages.
5. **Your own language**: support tickets, sales notes, docs search logs, GitHub issues, and
   Search Console queries if the team has connected it (`google-search-console.performance` via
   treg; free on the team's own connection).

Dedupe by intent, not by wording. Keep one prompt per intent and use samples for variance.

## Competitors

3-5, as the engines see them, which isn't always who sales thinks they are. After the first run,
read `named_instead` across the gaps. A brand the engines keep naming belongs in the panel even
if it is not a "real" competitor, because it is the one taking your answers.

## Engines

As of 2026-10-31 these engines answer through treg (verify with `catalog_get` before use):

| engine | capability | example endpoint | ~$/answer | notes |
|---|---|---|---|---|
| ChatGPT | `ai-search.chatgpt.scrape` | `cloro.ai-search.chatgpt.scrape`, `dataforseo.x.ai-optimization-chat-gpt-llm-scraper-live-advanced` | 0.004 | live consumer UI; sources, citation pills, entities, fan-out |
| Perplexity | `ai-search.perplexity.answer` | routed `treg.ai-search.perplexity.answer` | 0.002-0.006 | `source_kind`: website and model API cite different sources |
| Google AI Mode | `google.serp.ai_mode` | `cloro.google.serp.ai_mode` | 0.0024 | uses `gl`, not `country` |
| Google AI Overview | `google.serp.organic` | routed `treg.google.serp.organic` with `ai_overview: true` | varies | only some queries trigger one |
| Gemini | `ai-search.gemini.scrape` | `cloro.ai-search.gemini.scrape` | 0.0024 | consumer answer |
| Claude | `ai-search.claude.answer` | `dataforseo.x.ai-optimization-claude-llm-responses-live` | 0.025 | model API; 500-char prompt cap |
| Bulk mention index | `ai-search.mentions.*` | `dataforseo.x.ai-optimization-llm-mentions-*` | 0.10 | aggregate mentions of a domain/keyword; a cross-check, not the panel |

For anything not in this table, search the catalog (`catalog_search "AI visibility"`) and,
if it isn't there, `catalog_request` it.
