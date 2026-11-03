# News sources

Checked 2026-11-02. Endpoint ids and prices change: verify with `treg catalog_get <id>` before
relying on them, and update this table when they move.

| source key | what it finds | endpoint | price per call | good for |
|---|---|---|---|---|
| `news` | recent articles from news sites | `treg.web.search.news` (routed over 5 providers, cheapest first; TinyFish is free) | $0 to about $0.008 | the default; broad coverage |
| `google_news` | Google News results with outlet and timestamp | `treg.google.serp.news` (routed over 6) | about $0.00015 to $0.002 | a second view; dates are reliable |
| `hackernews` | stories and their points and comments | `crawl4ai.hackernews.search.stories` | about $0.00015 | developer and security audiences; shows what technical buyers argue about |
| `x` | posts by keyword, with engagement | `treg.x.search.posts` (routed over 3) | about $0.00075 | fast reactions; noisy, so keep queries exact (quote phrases) |
| `courtlistener` | federal court filings (RECAP documents) with full-text search | CourtListener REST v4 `/search/?type=rd`, `Authorization: Token …` | free with an account | court-record signals before or without press coverage |

Every treg call carries `X-Treg-Route-Max-Cost` (the script sets it per source) and the sweep stops
before `--max-usd`. A routed call reports what it was charged; the sweep sums those.

## What the script keeps

- Title, URL, outlet, publication date, a 500-character snippet, the query that found it, and an
  engagement count where the source has one (Hacker News points plus comments; X likes, reposts,
  replies and quotes).
- **No author names or handles.** X posts are stored as `https://x.com/i/status/<id>`. Journalists'
  names come from the article byline when a pitch is drafted, and live in `<state>/outreach/` like
  other contacts.

## CourtListener notes

- Coverage: federal courts only, and only filings someone bought through PACER with the RECAP
  extension, so high-profile cases are over-represented. State courts are mostly missing.
- Useful queries look for the cleanup, not the leak: `"notice of errata" redacted`,
  `"inadvertently filed" unredacted`, `"corrected redacted version"`, `"motion to seal" unredacted`.
- The API's date filter (`filed_after`) and ordering (`entry_date_filed desc`) are as documented for
  v4 on 2026-11-02; the script also drops anything older than `max_age_days` itself.
- Never scan filings for redaction failures yourself. Finding a live leak in someone else's
  document isn't marketing work, and using it would be wrong. Work from what's already public.

## Trends (optional, by hand)

`treg.google.keywords.trends` (about $0.0012) shows whether a topic is rising. Use it in a work
session to choose between two candidates, not in the sweep.
