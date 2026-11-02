# Technical problems: what `crawl_check.py` reports and how to fix it

Each problem in `<state>/seo/crawl.json` has a `kind`. Fix the cause (usually a template, a config
or a build step), not one page at a time.

| kind | what it means | usual fix |
|---|---|---|
| `status` | the sitemap lists a URL that doesn't return 200 | remove it from the sitemap, restore the page, or redirect it (with approval if it had traffic) |
| `redirect` | the sitemap lists a URL that redirects | list the final URL in the sitemap instead |
| `redirect_chain` | more than one hop to the final page | point the first URL straight at the final one |
| `offsite` | a sitemap URL ends on another host | a misconfigured redirect or a stale sitemap entry; fix or remove |
| `robots` | robots.txt disallows the page for Googlebot | allow it, unless it's private on purpose (then drop it from the sitemap and add it to `accepted_problems`) |
| `noindex` | a robots meta tag or `X-Robots-Tag` header says noindex | remove it if the page should rank; staging-only noindex leaking to production is the classic cause |
| `canonical` | the page's canonical points elsewhere | self-canonical for pages that should rank; keep it pointing elsewhere only for true duplicates |
| `title` | missing, or over 60 characters | a specific title per page from the template; the query it targets first |
| `duplicate_title`, `duplicate_description` | several pages share one | template defaults leaking through; give each page its own |
| `description` | no meta description | write one from the page's quick answer |
| `thin_html` | under 150 words in the server-rendered HTML | content rendered only in the browser: render it on the server or statically (crawlers and most AI fetchers don't run JavaScript reliably) |
| `orphan` | no crawled page links to it | link it from related pages and the relevant hub or nav |
| `broken_link` | an internal link returns 404 or 410 | fix the link, or redirect the old URL if it had traffic |

## Checks the crawl doesn't do

- **Indexing in Search Console**: the API has no coverage report, so `indexed_ratio` is a proxy
  (pages that appeared in search). For a page that should rank but never appears, ask a human to
  inspect the URL in Search Console and request indexing.
- **Speed and Core Web Vitals**: use the team's existing tooling; flag only clear regressions.
- **Structured data and AI-bot access**: `../ai-search-optimization` (`check_ai_access.py`).
- **Hreflang and international setups**: check by hand when the site has more than one locale.

## Before any change that removes a page from search

Deleting, noindexing, redirecting or canonicalising away a page needs the owner's approval when the
page has clicks in the last 90 days (Search Console) or referring domains
(`treg.web.backlinks.summary`, checked 2026-11-02; verify with `catalog_get`). Put the evidence in
the PR description.
