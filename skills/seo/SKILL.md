---
name: seo
description: Get a product's pages crawled, indexed and ranking in classic search, which also feeds the retrieval behind AI answers. Owns the demand track's `indexed` and `ranking` rungs together with measurement's Search Console sensor - a weekly technical crawl (status codes, redirects, noindex, canonicals, robots, titles, thin client-only pages, orphans, broken links), the query map that gives every target query exactly one page, keyword and SERP research through treg, striking-distance improvements for pages ranking 8-20, and internal linking. Use when the user asks about SEO, rankings, indexing, "why isn't this page on Google", keyword research, a technical audit, or a query map, and when gtm's seo_crawl job is due. Writing the pages is ../content; AI-bot access, llms.txt and structured data are ../ai-search-optimization; the Search Console numbers come from ../measurement.
---

# SEO

Search engines still decide which pages most AI answers can find: assistants that browse retrieve
from search indexes, and a page that isn't indexed or ranks on page five is rarely cited. This skill
keeps the site crawlable and gives each query buyers search one strong page.

`<state>` is the store root printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
scripts from the product repo root, calling the plugin's scripts by absolute path (`scripts/…` is
this skill's folder). Site changes go to the product repo as PRs.

## What it owns

| rung (demand track) | metric | written by |
|---|---|---|
| `indexed` | `indexed_ratio` (share of sitemap URLs that appeared in search in 90 days; a proxy, since the API has no coverage report) | `../measurement/scripts/search_console.py` |
| `ranking` | `query_top10_share` (share of query-map queries at an average position of 10 or better) | the same script, reading `<state>/seo/queries.csv` |
| (problems) | `seo_problems` (count from the latest crawl) | `scripts/crawl_check.py` |

`gtm.py connect search_console` must be on for the sensor to run; see `../measurement`.

## Files

```
<state>/seo/queries.csv     the query map (format: references/query-map.md)
<state>/seo/crawl.json      the latest crawl's problems
<state>/seo/research/       keyword and SERP pulls, dated
```

## seo_crawl (weekly, free)

```
python3 scripts/crawl_check.py <site_url> [--limit 300]
python3 ../gtm/scripts/gtm.py record seo_crawl
```

It reads the sitemap (following indexes), fetches each page once with a polite delay, writes
`<state>/seo/crawl.json` and the `seo_problems` metric. Then:

- Compare with last week's counts. A new `status`, `noindex`, `robots` or `canonical` problem on a
  page that had traffic is an alert: say so in the digest now.
- Group fixes by cause, not by page (one template bug can noindex fifty pages). Fixes go through work
  sessions as PRs, each with a bet (metric `indexed_ratio` or `query_top10_share`).
- Problems that are deliberate (staging hosts, private paths) go in gtm.json `accepted_problems` with
  a human's yes. What each problem means and how to fix it: `references/technical.md`.

## The query map

One row per query buyers search, with the page that owns it. Two rules make it useful:
**every target query has at most one page**, and **every page targets at least one query**. Two pages
on one query compete with each other; merge them and redirect the weaker one, with approval if it
has traffic or links.

Build it in `init` or on the first run, then keep it current:

1. **Seed** from `<state>/product-context.md` (the problem in buyers' words, category terms,
   competitors, use cases), the audit's prompts and fan-out queries, and the Search Console queries
   the site already gets.
2. **Expand and size** with treg (checked 2026-11-02; verify each with `catalog_get`):
   `treg.google.keywords.ideas` for related queries, `treg.google.keywords.volume` for volume and
   difficulty (routed; serpstat and seranking cost about $0.0005-0.002 per keyword), and
   `treg.google.serp.organic` for who ranks now and the People-Also-Ask questions (about $0.002).
   `serpstat.google.domain.ranked_keywords` shows what a competitor ranks for.
3. **Assign** each query to an existing page, or mark it `gap`. Gaps go to `<state>/pages.md` as
   candidates for `../content` (or `../comparison-pages` for "vs" and "alternatives" queries).
4. `search_console.py` fills `position` and `last_checked` weekly through measurement; update
   `status` when pages ship.

## Improving rankings

| tactic (gtm `next`) | when | what |
|---|---|---|
| `technical_fix` | the crawl found a problem on a page that matters | fix the cause in the template or config, as a PR |
| `striking_distance` | a query-map page has an average position of 8-20 in Search Console | read the current top 3, close the gap (answer the query in the first two sentences, add the missing sub-questions, a table, fresher facts), add 2-3 internal links from related pages, keep the URL |
| `query_gap_page` | a `gap` query with real demand and a fit the product can prove | brief it to `../content` |
| `integration_page` | an integration the product ships has search demand | brief it to `../content` |

Internal linking: every new or improved page gets links from at least three relevant existing pages,
with descriptive anchor text, and appears in the sitemap with a real `lastmod`.

Open a bet before each change (`gtm.py bet open`): rankings move over weeks, so check dates of 4-8
weeks; prefer a staggered rollout when the same change applies to many pages.

## Limits

- Never delete, noindex, or redirect a page that gets traffic or has backlinks without the owner's
  approval. Check Search Console clicks and `treg.web.backlinks.summary` first.
- Programmatic pages only when each page carries real, unique data a searcher needs (an integration's
  actual setup, a location's actual details). Templated pages that differ only by a keyword get the
  whole site judged as thin.
- Don't buy links or trade them. Earned links come from `../citation-outreach`.
- Don't chase volume outside the product's fit: a ranking that never converts is not progress.

## Spend

The crawl is free. Keyword and SERP research for a query map costs about $0.10-1.00 depending on
size; state the estimate first and record it with `gtm.py record`.
