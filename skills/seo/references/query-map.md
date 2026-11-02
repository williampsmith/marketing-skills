# The query map: `<state>/seo/queries.csv`

A CSV with a header row. `search_console.py` (measurement) reads the `query` column to compute
`query_top10_share`; the other columns are for the agent and the human.

| column | values | meaning |
|---|---|---|
| `query` | lower-case text, as searched | one query per row; unique |
| `intent` | `how`, `what`, `best`, `vs`, `alternatives`, `integration`, `use-case`, `pricing`, `brand` | what the searcher wants to do |
| `page` | a site path (`/guides/redact-pdf`) or empty | the one page that owns the query |
| `status` | `live`, `planned`, `gap`, `merged` | live: the page exists; planned: in `pages.md`; gap: no page yet; merged: folded into another row's page |
| `position` | number or empty | average Search Console position, last 28 days |
| `last_checked` | YYYY-MM-DD | when `position` was last updated |

Example:

```csv
query,intent,page,status,position,last_checked
redact pdf permanently,how,/guides/redact-pdf,live,7.4,2026-11-09
pdf redaction tool for law firms,use-case,,gap,,
acme vs adobe acrobat redaction,vs,/compare/acme-vs-acrobat,planned,,
```

## Rules

- **One page per query.** Before assigning a query, search the file for the same or a near-identical
  query (plurals, word order). Near-duplicates share one row's page.
- **Merging.** When two pages own queries a searcher would treat as the same, keep the stronger page
  (more clicks, more links), move the other's unique content into it, 301 the weaker URL to it, and
  set the weaker rows to `merged`. A page with traffic or backlinks needs the owner's approval first.
- **Brand queries** stay out of the map. When the map exists, every row counts toward
  `query_top10_share`, and brand queries rank easily, which would flatter the number. Brand answers
  are watched by the AI-visibility audit instead.
- **Pruning.** Remove queries with no demand and no fit at each `strategy_review`; the map measures
  what the business needs, not everything searchable.
- Keep it under a few hundred rows. A smaller map of queries that convert beats a large one of
  vanity terms.
