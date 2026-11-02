# Teardown: method, sources and output

A teardown is a history: what the competitor did, when, and what their numbers did around it.
Endpoint ids below were checked on 2026-11-02 and are examples. Verify each with `catalog_get`
(parameters, current price, measured reliability) before calling, prefer routed `treg.*` ids where
they exist, and use the CLI (`treg --json call …`) for batches so results stay out of the context.

## Sources

| signal | job to search | example endpoint (checked 2026-11-02) | ~cost per call |
|---|---|---|---|
| Monthly traffic history | "website traffic estimate history for a domain" | `dataforseo.x.dataforseo-labs-google-historical-bulk-traffic-estimation-live` (up to 1,000 domains per call) | ~$0.12 |
| Keywords they rank for | "keywords a domain ranks for" | `serpstat.google.domain.ranked_keywords`, `dataforseo.google.domain.ranked_keywords` | $0.0005-0.012 |
| Keywords they buy | "google ads keywords a domain bids on" | `spyfu.google.domain.paid_keywords` | ~$0.002 |
| Google ads they run | "find a company's google ads" | `adyntel.google.ads.transparency`, `serpapi.google.ads.transparency` | ~$0.01-0.015 |
| Meta ads they run | "ads library ads a company is running" | `treg.meta-ads.library.advertiser` (routed) | under $0.01 |
| Backlinks and referring domains | "backlinks for a domain" | `treg.web.backlinks.summary`, `treg.web.backlinks.list` (routed) | under $0.001 |
| Hiring | "company job postings" | `treg.companies.jobs.search` (routed) | ~$0.02 |
| Reviews | "trustpilot reviews" | `dataforseo.x.business-data-trustpilot-reviews-task-post` (async), `crawl4ai.trustpilot.business.reviews` | ~$0.0015 |
| Launches and press | news search | `treg.web.search.news` | cents |
| Content cadence | their sitemap and blog index | `treg.web.extract` (free via TinyFish) | free |
| Community buzz | "reddit search posts", "search hacker news" | `scrapecreators.reddit.search.posts`, `crawl4ai.hackernews.search.stories` | ~$0.001-0.002 |

Not in the catalog on 2026-11-02: G2 and Capterra reviews, and archived page history (Wayback).
Read G2 pages through `treg.web.extract` if they render; skip archive history rather than guess it.
If a source would materially change the teardown, file a `catalog_request`.

## Method

1. **Pull the curve first** (one call): monthly traffic for the competitor's domain, plus your own
   and one or two peers for scale. Mark inflections: months where growth clearly changed slope.
2. **Collect moves for the window.** For each signal, keep only dated items. Ranked keywords: group
   by when they entered the top 10 if the provider gives history; otherwise note today's top pages
   and their publish dates. Ads: first-seen dates and the claims in the copy. Content: publish dates
   from the sitemap's `lastmod` or the post pages.
3. **Line moves up against inflections.** For each inflection, list what happened in the 60 days
   before it. Rate each candidate cause:
   - **strong**: several independent signals point to the same move (a launch, ads on its claim,
     new rankings for its keywords, press);
   - **some**: one signal;
   - **coincidence**: only the timing lines up.
4. **Turn candidates into plays.** A play names the move, why it might work here, the gtm tactic and
   skill that would run it, the channel's fit for this product, and a first bet (metric, method,
   check date). Skip plays whose channel `gtm.py fit` marks ineligible; list them under "not for us"
   with the reason.

## Output: `<state>/competitors/<slug>/teardown.md`

```markdown
# Teardown: <competitor> (<domain>), <window>, read <date>

## Curve
| month | est. visits | provider | note |
|---|---|---|---|

## Moves (dated, quoted)
| date | move | source (URL) | quote or figure |
|---|---|---|---|

## What lined up with growth
- <inflection month>: <move> — evidence: strong | some | coincidence — <why>

## Plays for us
| play | tactic → skill | channel fit | first bet (metric, method, check) |
|---|---|---|---|

## Not for us
- <play> — <channel> fit <score>: <reason from gtm.py fit>

## Analysis (opinion, labelled)
<what this suggests about their strategy; kept apart from the facts above>

Spend: $<actual> (estimate was $<estimate>).
```
