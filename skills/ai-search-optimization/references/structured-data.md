# Structured data for AI citation

The rule: **mark up only what is visible on the page.** A schema claim with no visible support is
a policy violation for Google and a hallucination you planted for every other engine.

## Sitewide (in the base layout)

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://DOMAIN/#org",
      "name": "Company",
      "url": "https://DOMAIN/",
      "logo": "https://DOMAIN/logo.png",
      "description": "The same one sentence as llms.txt and the homepage.",
      "sameAs": ["https://github.com/…", "https://www.linkedin.com/company/…", "https://x.com/…"]
    },
    {
      "@type": "WebSite",
      "@id": "https://DOMAIN/#website",
      "url": "https://DOMAIN/",
      "name": "Product",
      "publisher": {"@id": "https://DOMAIN/#org"}
    }
  ]
}
```

`sameAs` connects the entity across the web: add every official profile (GitHub, LinkedIn,
Crunchbase, Wikidata, G2, Product Hunt, app store listings). Engines resolve "who is this" by
matching these up.

## Product page

`SoftwareApplication` with `operatingSystem`, `applicationCategory`, and `offers` (price,
priceCurrency, and a free trial if visible). Use `aggregateRating` **only** if the reviews appear
on the page and are real and first-party compliant.

## One-pager / article

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "@id": "https://DOMAIN/guides/x#article",
  "headline": "≤110 chars, matches the H1",
  "description": "the quick answer, shortened",
  "datePublished": "2026-10-31",
  "dateModified": "2026-10-31",
  "author": {"@type": "Person", "name": "Real Name", "url": "https://DOMAIN/about#name"},
  "publisher": {"@id": "https://DOMAIN/#org"},
  "mainEntityOfPage": "https://DOMAIN/guides/x",
  "about": [{"@type": "Thing", "name": "PDF redaction"}],
  "citation": ["https://primary-source-1", "https://primary-source-2"]
}
```

Add `FAQPage` when the page has a visible FAQ, with each `Question`/`acceptedAnswer` copied word
for word. Use a `BreadcrumbList` when the page sits in a hierarchy. A named, real author with an
about page is a strong trust signal; prefer it to "Team".

## Pitfalls

- A `dateModified` that changes on every deploy is noise, and engines learn to ignore it. Change
  it only when the content changes.
- Several disconnected JSON-LD blocks describing the same thing in different ways: use one `@graph`
  with `@id` references.
- Rich results: FAQ rich results are limited to well-known authoritative sites and HowTo rich
  results are gone. The markup still helps machines; just don't promise SERP features.
- Validate: validator.schema.org (syntax and types) and search.google.com/test/rich-results.
