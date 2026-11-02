# Research recipes with treg

Discover endpoints by job (`catalog_search "<job in plain words>"`), then `catalog_get` for the
current id, parameters, price and measured reliability. The ids below were correct on 2026-10-31
and are examples, not contracts. Prefer routed `treg.*` endpoints, send `X-Treg-Route-Max-Cost`
on routed calls, and use the CLI (`treg --json call …`) for anything over about 5 calls so answers
stay out of the context window.

## Intent mining (phase 1)

| question | job to search | example | ~cost |
|---|---|---|---|
| What do people search around this topic? | "related keyword ideas" | `treg.google.keywords.ideas` (routed) | <$0.02 |
| How much demand per phrasing? | "keyword search volume" | `treg.google.keywords.volume` (routed; seranking is ~$0.002) | <$0.01 |
| What follow-up questions does Google show? | "google serp organic" | `treg.google.serp.organic` with `ai_overview: true`; read `people_also_ask` and the AI Overview | ~$0.002-0.01 |
| How do buyers describe it in their own words? | "reddit search posts", "reddit post comments" | ScrapeCreators / TikHub endpoints | cents |
| What did ChatGPT search to answer it? | "chatgpt answer" | `cloro.ai-search.chatgpt.scrape` with `include.searchQueries` | $0.0036 |
| What does the team's own site already rank for? | "search console performance" | `google-search-console.performance` (team connection) | free |

Fan-out queries are the most valuable here. They are the sub-questions the engine itself
decided the answer needs. A page that answers all of them directly is close to the ideal source.

## Recon (phase 2)

Run each target prompt on:

- ChatGPT: `cloro.ai-search.chatgpt.scrape`, body `{"prompt": …, "country": "US", "include": {"markdown": true, "searchQueries": true}}`
- Perplexity: `treg.ai-search.perplexity.answer`, body `{"prompt": …}` (`source_kind` tells you
  website vs API answers, which cite differently)
- Google AI Mode: `cloro.google.serp.ai_mode`, body `{"prompt": …, "gl": "US"}`

The audit skill's `run_panel.py` can do this with a throwaway panel file
(`--panel <state>/pages/<slug>/panel.json --out <state>/pages/<slug>/recon`), which gives the
same normalized `answers.jsonl` the audit uses.

Then read the cited pages: `treg.web.extract` with header `X-Treg-Route-Prefer: tinyfish` (free),
or `tinyfish.web.fetch` with up to 10 `urls` in one free call. Cut navigation and footers before
analyzing.

## Evidence (phase 3)

| need | job to search | example |
|---|---|---|
| A cited answer to a factual sub-question | "answer a question with citations" | `exa.web.answer` (~$0.005), `you.web.answer` |
| Deep multi-source research on a hard question | "research a web question" | `you.web.research` (~$0.05) |
| Recent incidents, rulings, launches | `treg.web.search.news` | dated results |
| Papers and standards | "search research publications" | |
| Competitor facts (pricing, features) | read their pages | `treg.web.extract` on their pricing or docs URL |

An answer engine's output is a **lead, not a source**. Follow its citation, read the primary page,
and quote that.

## Optional — distribution signals

- `catalog_search "ads library"`: competitor ad copy shows the positioning they pay to defend,
  which is useful for a comparison angle.
- `catalog_search "app store reviews"`, "trustpilot reviews", "g2 reviews": real complaints about
  the incumbent make the most honest "when X isn't enough" sections. Quote patterns with counts,
  never an individual's personal data.

## Hygiene

- Keep the source URL next to every fact you carry forward.
- Rate calls that invite a `review` once you've used the result. Send `feedback` for broken or
  misleading endpoints, with call ids.
- Public data only. Don't log in as anyone or get around paywalls.
