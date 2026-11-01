# Where entities live (checked 2026-11-01)

Pick the rows that fit the product. Priority is a default; reorder it using what the engines
actually cite for the category (`top_cited_domains` in the audit).

| platform | type | why it matters | priority | notes |
|---|---|---|---|---|
| Wikidata | knowledge graph | read by search engines and model builders; structured facts | high if notable | needs an independent reference; disclose COI on the talk page |
| Wikipedia | encyclopedia | heavily weighted in training | only with independent coverage | never self-authored |
| Google Business Profile | local entity | knowledge panel for companies with a location | med | can be connected to treg for reads |
| LinkedIn company page | company db | maker, size, people; ranks for the brand | high | |
| Crunchbase | company db | founding, funding, category; widely scraped | high (startups) | |
| G2 / Capterra / GetApp / Software Advice | software directory | cited heavily on "best X software" | high (B2B) | Capterra, GetApp and Software Advice share one Gartner listing |
| TrustRadius | software directory | enterprise buyers | med | |
| AlternativeTo | software directory | cited on "alternatives to X" | high (consumer/prosumer) | add as an alternative to the incumbents |
| Product Hunt | launch directory | durable product page, often cited | med | launch day is the best moment |
| SaaSHub / Slant | directories | comparison-style pages, often cited | low-med | |
| Mac App Store / Microsoft Store / Setapp | app stores | platform truth: OS, price, rating | high if distributed there | |
| GitHub org / repo | code host | devtools entity, topics and description | high (devtools) | |
| npm / PyPI / crates.io / Homebrew | registries | devtools install truth | high (devtools) | |
| Trustpilot | reviews | cited for "is X legit" | med (B2C) | treg reads it (`trustpilot.business.reviews`) |
| Reddit (official account, subreddit) | community | engines lean heavily on Reddit | med | an official, disclosed account; no astroturf |
| YouTube channel | video | demos get cited in AI Mode and Gemini | med | |
| X / Bluesky / Mastodon | social | brand handle consistency | low | |
| Status page, docs site, changelog | owned | fresh facts engines quote | high | in llms.txt and sameAs where applicable |

## Field limits to plan for

One-liner ≤ 160 chars covers most "tagline" fields (G2 is shorter; check each). Long description
≤ 750 covers most. Keep a 60-character version for app store subtitles and similar fields.
