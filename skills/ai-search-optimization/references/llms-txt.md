# llms.txt, llms-full.txt, markdown mirrors, JSON feed

## /llms.txt (spec: llmstxt.org)

```markdown
# Product Name

> One sentence: what it is, who it is for, and the main value. Written so an AI can quote it
> unchanged, and identical to the homepage and Organization schema description.

Two or three short paragraphs or bullets of facts an agent needs: platforms, pricing model,
what it does NOT do, where support is. No marketing adjectives.

## Product
- [Product overview](https://DOMAIN/): What it does and for whom.
- [Pricing](https://DOMAIN/pricing): Plans, trial length, licensing.
- [Security](https://DOMAIN/security): How data is handled; what leaves the device.

## Answers
- [How to redact a PDF so text can't be recovered](https://DOMAIN/guides/redact-pdf-permanently): Quick answer + method.
- [Acrobat vs dedicated redaction apps](https://DOMAIN/compare/acrobat): When each fits.

## Docs
- [Quickstart](https://DOMAIN/docs/quickstart.md): Install to first result.

## Optional
- [Changelog](https://DOMAIN/changelog): Release history.
- [Feed](https://DOMAIN/feed.json): Every article and answer page, as JSON Feed.
```

Rules:

- Exactly one H1 (the name), then a `>` blockquote summary, then optional plain text, then H2
  sections of link lists. `## Optional` marks what an agent can skip when context is short.
- Full absolute URLs. Each link description is one sentence saying what the page *answers*.
- Order by importance. Keep it under about 100 links, curated rather than dumped from the sitemap.
- Point to `.md` mirrors where they exist; agents read them cheaply.
- Serve it as `text/plain` or `text/markdown` with 200, and don't let a SPA fallback return
  `index.html` for it (the checker flags this).

## Keep it generated, not hand-maintained

Each one-pager is added to it automatically. The best setup is a small build step that writes
llms.txt (and llms-full.txt and feed.json) from the same content source as the pages, such as
frontmatter `title`, `description`, `url`, `updated`, `section`. On a static site with no build,
the `one-pager` skill appends its entry under `## Answers`. Either way, list the pages in one
place only.

## /llms-full.txt

The key pages' content as Markdown, concatenated with `# Title` + `Source: URL` headers. Build it.
Include product, pricing, security and every answer page. Leave out legal and boilerplate.

## Markdown mirrors

For each docs page and one-pager, publish `same-path.md` (or `index.md` in the directory) with
the same content as clean Markdown, and link it in `<head>`:
`<link rel="alternate" type="text/markdown" href="/guides/x.md">`.

## /feed.json (jsonfeed.org v1.1)

```json
{
  "version": "https://jsonfeed.org/version/1.1",
  "title": "Product — answers and articles",
  "home_page_url": "https://DOMAIN/",
  "feed_url": "https://DOMAIN/feed.json",
  "items": [{
    "id": "https://DOMAIN/guides/x",
    "url": "https://DOMAIN/guides/x",
    "title": "…",
    "summary": "the quick answer",
    "content_text": "full text",
    "date_published": "2026-10-31T00:00:00Z",
    "date_modified": "2026-10-31T00:00:00Z",
    "tags": ["category"]
  }]
}
```

Add `<link rel="alternate" type="application/feed+json" href="/feed.json">` to the site `<head>`.
