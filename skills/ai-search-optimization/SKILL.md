---
name: ai-search-optimization
description: Make a product's website crawlable, readable and citable by AI search and answer engines (ChatGPT/OAI-SearchBot, Claude-SearchBot, PerplexityBot, Google AI Overviews, Copilot) - robots.txt and CDN bot access, llms.txt and markdown mirrors, intent-matched pages with quick answers, JSON-LD, sitemap and IndexNow, and AI-referral analytics. Use when the user wants to optimize a site for AI search, AEO/GEO, LLM discoverability, "get recommended by ChatGPT", set up llms.txt, or fix AI bots being blocked. Implements the changes in the site's source, verifies them live, and flags what needs human review.
---

# AI search optimization

Make the site **reachable, readable and citable** by AI answer engines, in that order. If a bot can't
reach the site, the other steps don't matter. If it can reach but can't read (client-rendered text),
the content work doesn't matter.

Source: `references/source-playbook.md`, the original playbook (the changes that took one
site from zero to most of its traffic coming from ChatGPT), expanded with what is known as of late 2026.

Implement the steps in order. Report what you changed, and flag anything that needs a human
decision: existing robots rules, CDN settings, analytics, domain-specific copy.

## Before you touch anything

1. **Find the site.** In a product repo it may be a subdirectory (`site/`, `web/`, `apps/www`,
   `docs/`) or another repo. Identify the framework (static HTML, Next.js, Astro, Hugo, Docusaurus,
   Webflow export, WordPress) and how it deploys. A hosted CMS edits out of repo, so write the exact
   changes for a human instead.
2. **Baseline.** Run the checker against production:
   ```bash
   python3 <skill>/scripts/check_ai_access.py https://DOMAIN / /pricing /docs   # key pages
   ```
   It reports robots.txt per bot, what the server returns to each bot's user agent (403s, CDN
   challenges), llms.txt, sitemap, and per page: words in raw HTML, JSON-LD types, modified date,
   noindex.
3. **Measure.** If `.marketing/runs/` has no recent run, offer the `ai-visibility-audit` skill first.
   Without a before measurement you can't tell whether any of this worked.
4. **Check intent.** A `Disallow: /` or `noindex` may be deliberate (a pre-launch, staging or trial
   host). **Ask before opening a site that blocks everything.** Never change it silently.

## Step 1 — Access: robots.txt and the CDN (highest leverage)

Name each AI bot explicitly. Don't rely only on `*`. Bots fall into three roles; the full table,
with user agents and docs, is in `references/bots.md`.

| role | bots | what blocking does |
|---|---|---|
| **search** (builds the answer engine's index) | OAI-SearchBot, Claude-SearchBot, PerplexityBot, Googlebot, Bingbot, Applebot | you disappear from that engine's citations |
| **user** (fetches live when a person asks) | ChatGPT-User, Claude-User, Perplexity-User, DuckAssistBot, MistralAI-User | the assistant can't open your page mid-conversation |
| **training** | GPTBot, ClaudeBot, CCBot, Meta-ExternalAgent; tokens Google-Extended, Applebot-Extended | future models know less about you |

**Always allow search and user bots.** Training is a business decision: **recommend allowing it for
a product marketing site.** A model that learned your product in training can name it without a
search, and that is how `brand` prompts get answered. Blocking training mainly protects content
that is itself the product (publishers, paid docs). Present the choice to the user; don't decide it.

Google-Extended and Applebot-Extended are robots tokens only. Blocking them does **not** remove
the site from Google Search, AI Overviews, AI Mode or Apple search.

Template (merge with the existing rules, keep real private paths, remove the comment for the choice not taken):

```
# AI search + user-triggered fetchers
User-agent: OAI-SearchBot
User-agent: ChatGPT-User
User-agent: Claude-SearchBot
User-agent: Claude-User
User-agent: PerplexityBot
User-agent: Perplexity-User
User-agent: DuckAssistBot
User-agent: MistralAI-User
Allow: /
Disallow: /admin/
Disallow: /api/

# Training crawlers — allowed (recommended for product sites). To block instead, set Disallow: /
User-agent: GPTBot
User-agent: ClaudeBot
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: CCBot
User-agent: Meta-ExternalAgent
Allow: /
Disallow: /admin/
Disallow: /api/

# Everyone else, including Googlebot and Bingbot
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: https://DOMAIN/sitemap.xml
```

A bot follows only the most specific group that names it and ignores `*`. So every named group
must repeat the private-path disallows.

**Then check the CDN, which is the silent killer.** Cloudflare has blocked known AI crawlers by
default on many zones since mid-2025 (Security → Bots / AI Crawl Control, plus "managed
robots.txt", which can rewrite your file). Vercel, Netlify, Akamai and WAF rules can also block
or challenge bots whatever robots.txt says. In the checker output, a `200` page for browsers next
to a `403`/challenge for a bot points to the CDN. Spoofed user agents test only user-agent rules;
confirm in the CDN dashboard and logs that real, verified bot traffic gets through. Most changes
here are in a dashboard, so write them up for the human owner.

OpenAI says robots.txt changes reach its systems in about 24 hours. Some user-triggered fetchers
may not honor robots.txt; don't rely on robots.txt for anything secret.

## Step 2 — Machine-readable entry points

- **`/llms.txt`**: a curated Markdown index. Major engines haven't confirmed using it for
  citations, but agents and coding assistants do read it, and it is cheap. Format, rules and a
  generator approach: `references/llms-txt.md`.
- **`/llms-full.txt`** (optional): the key pages' full content concatenated as Markdown.
- **Markdown mirrors**: serve `page.md` next to `page.html` (or answer `Accept: text/markdown`)
  for docs and one-pagers. Agents read these with far fewer tokens and less extraction error.
- **Public JSON feed** (`/feed.json`, JSON Feed 1.1): title, URL, date published and modified,
  summary, and content for every article and one-pager. Link it from llms.txt and the HTML `<head>`.
- **Sitemap** with accurate `<lastmod>`, generated from content dates, not the build time. List it
  in robots.txt.
- **IndexNow** (Bing, Yandex, Seznam, Naver): ping on publish so Bing indexes new pages in
  minutes. ChatGPT search and Copilot draw on Bing, so this shortens the time to show up there.
  Also verify the site in Bing Webmaster Tools and Google Search Console.

## Step 3 — Content that can be quoted

On each key page, especially pages aimed at a specific question:

- A dated **Quick answer** near the top: 2-5 sentences that answer the page's main question by
  themselves, specific enough to quote (numbers, names, conditions). Show "Updated <date>" and put
  the same date in the schema.
- **One page per intent.** A focused page answering one question gets cited; a long page covering
  many topics gets skimmed. Creating these is the `one-pager` skill's job. This step finds the
  gaps and lists them in `.marketing/pages.md`.
- **Main content in the initial HTML** (server-rendered or static). The checker's `words` column
  flags client-rendered pages (fewer than 150 words in the raw HTML).
- Question-shaped H2s, tables for comparisons, short paragraphs, and outbound citations to primary
  sources. The 2023 GEO study (Aggarwal et al.) reported that adding citations, quotations and
  statistics measurably raised a page's visibility in generative answers. Keyword stuffing did not.
- **Entity clarity**: the same one-sentence description of the product on the homepage, llms.txt,
  Organization schema and every external profile, so engines settle on one description.

## Step 4 — Structured data

JSON-LD that matches what's visible on the page, and nothing beyond it. Patterns and pitfalls:
`references/structured-data.md`. The minimum is `Organization` + `WebSite` sitewide,
`SoftwareApplication`/`Product` on the product page, and `Article` (+ `FAQPage` when there is a
visible FAQ) on one-pagers. Google now shows FAQ rich results only for a few authoritative sites
and has retired HowTo rich results. Add the markup anyway for machine readability, but promise
no rich results. Validate with the Schema Markup Validator and Google's Rich Results Test.

## Step 5 — Track AI referrals

AI traffic often shows up as Direct. Recipes for GA4, PostHog, server logs, and treg-connected
analytics are in `references/ai-referral-tracking.md`. The key points:

- ChatGPT adds `utm_source=chatgpt.com` to many outbound links. Perplexity, Claude, Gemini and
  Copilot mostly send a referrer.
- Count **ChatGPT-User / Claude-User / Perplexity-User hits in the server or CDN logs**. Each one
  means a person asked an assistant something and it opened your page. It is the best early signal,
  and it shows up before clicks do.
- Watch Direct traffic to deep pages such as one-pagers, which nobody types by hand.

## Step 6 — Verify and hand off

Rerun the checker against production after deploying. Expect zero problems except ones the user
chose to keep. Then:

- [ ] robots.txt names the search and user bots and allows them; the training choice is recorded
- [ ] the CDN serves real bots (dashboard and logs checked, or the human owner asked to check)
- [ ] `/llms.txt` returns 200 Markdown with full URLs; feed and sitemap are linked and current
- [ ] key pages: quick answer + date + matching JSON-LD, with content in the raw HTML
- [ ] AI referrals are visible, or at least separable, in analytics
- [ ] IndexNow / Bing Webmaster / Search Console are set up
- [ ] a follow-up `ai-visibility-audit` is scheduled 1-2 weeks out (results take days to weeks;
      the source playbook saw a jump after about a week)

Report: the changes with file paths, what is still in human hands (CDN, analytics, domains), and
the gap intents handed to `one-pager`.

## Using treg here

- `treg.web.extract` (free via TinyFish) reads competitor and cited pages to see how pages that
  get cited are structured.
- Check how engines see a page: `cloro.ai-search.chatgpt.scrape` with a prompt naming the brand
  and `include.searchQueries`. If the answer comes from third-party pages rather than yours,
  your pages aren't being read or don't answer the question.
- Search Console and GA4 can be connected to treg by the team (`treg connections`). With them
  connected, step 5's verification can query real data instead of asking a human.
- Always `catalog_get` for the price first; rate calls that invite a `review`.
