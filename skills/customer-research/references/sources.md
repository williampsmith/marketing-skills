# Where to sample, through treg

Endpoint ids were checked on 2026-11-02 and are examples. Verify each with `catalog_get` before
calling (parameters, current price, measured reliability), prefer routed `treg.*` ids when they
exist, and use the CLI (`treg --json call …`) for batches so results stay out of the context window.

| source key | job to search | example endpoint (checked 2026-11-02) | ~cost per call | read for |
|---|---|---|---|---|
| `reddit` | "reddit search posts" | `scrapecreators.reddit.search.posts`, `tikhub.x.reddit-app-fetch-dynamic-search` | $0.001-0.002 | questions, complaints, "what do you use for…" |
| `linkedin` | "linkedin search posts by keyword" | `anyapi.linkedin.search.posts`, `harvestapi.linkedin.post.search` | $0.002-0.004 | practitioners and buyers in B2B roles posting about the problem |
| `tiktok` | "tiktok search videos by keyword" | `treg.tiktok.search.videos` (routed) | about $0.001 | consumer and creator demand; check who posts, not just views |
| `youtube` | "youtube search videos" | `treg.youtube.search.videos` (routed) | about $0.001 | tutorials and reviews people watch before choosing |
| `x` (counts toward `linkedin_organic`) | "twitter x search tweets" | `treg.x.search.posts` (routed) | under $0.001 | developer and founder chatter |
| `hackernews` | "search hacker news" | `crawl4ai.hackernews.search.stories` | under $0.001 | developer tools and infrastructure |
| `g2`, `capterra` | not in the catalog on 2026-11-02 | read public pages with `treg.web.extract` (free) when they render | free | review volume and recurring complaints per alternative |
| `press` | news search | `treg.web.search.news` | cents | coverage of the problem and the category |
| `search` | "keyword search volume" | `treg.google.keywords.volume` (routed) | under $0.002 per keyword | whether people search for the problem at all |

`x` has no channel of its own in `channel-fit.json`. `attention.py` maps it to `linkedin_organic`
(founder-led social): record X under the `x` source key and it counts toward that channel. Its results
are also good for customer language.
Trustpilot (`dataforseo.x.business-data-trustpilot-reviews-task-post`, async) is useful for
consumer products' review patterns.

## Judging relevance

A result is relevant when someone in the ICP, in their own voice:

- describes the problem or its cost;
- asks how to solve it or which tool to use;
- compares alternatives, including the workaround;
- reports buying, switching or giving up.

Not relevant: vendor posts and ads, recruiters, listicles written for SEO, unrelated meanings of the
query words, and posts by people clearly outside the ICP (students for an enterprise product, for
example). When unsure, don't count it, and note the borderline cases in the evidence file.

## The `search` source

For `search`, `sampled` is the number of problem queries checked and `relevant` the number with
meaningful monthly volume in the target market (decide the threshold per market and write it in the
evidence file). It feeds `seo_content`'s weight.
