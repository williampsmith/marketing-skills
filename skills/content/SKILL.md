---
name: content
description: Research, write and ship pages for a product's website that buyers and AI answer engines (ChatGPT, Perplexity, Google AI Mode, Claude) use and cite - answer pages (the one-pager or AEO/GEO article for one intent), integration pages, use-case pages, sales one-pagers and battlecards, and changelog or launch posts. Runs inside the product repo, reads the code and docs as ground truth for every product claim, uses treg to see what engines and searchers find today, writes a dated page with matching JSON-LD, wires it into the site, sitemap, llms.txt and feed, and records the query it targets in the seo query map. Use when the user asks for a one-pager, answer page, AEO/GEO article, integration page, use-case page, battlecard, launch post, "write a page so ChatGPT recommends us for X", or to work the backlog in <state>/pages.md. Comparison and alternatives pages go through ../comparison-pages; technical SEO and the query map are ../seo.
---

# Content

One page answers one intent better than anything the engines cite today, and every product claim
on it is backed by the code. Competitors can copy the format; they can't copy claims you prove
from your own source.

An answer page is **not** a product pitch. It is the most useful answer to a question a buyer asks,
written by the team that knows the problem best. The product shows up where it honestly fits, in a
separate section at the end.

Arguments: a page type and an intent, a prompt id from the panel, a query from the seo query map,
or nothing (pick from the backlog).

`<state>` is the store root printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
scripts from the product repo root, calling the plugin's scripts by absolute path. Pages go to the
product repo as PRs.

Copy drafted by this skill must pass the `../writing` gates: every claim from the ledger, something
the current top results lack, and no AI-tell phrasing.

## Page types

| type | the reader's question | what makes it different | gtm tactic |
|---|---|---|---|
| **answer page** (one-pager) | "how do I…", "what is…", "best way to…" | the full pipeline below; vendor-neutral body, product in "From the publisher" | `answer_page`, `query_gap_page` |
| **integration page** | "does <product> work with <tool>?", "<product> + <tool>" | only integrations the code ships; setup steps taken from the code or docs; a screenshot or snippet | `integration_page` |
| **use-case page** | "<job> for <role or industry>" | one job, one audience; steps, constraints and a worked example from real behavior | `integration_page`, `query_gap_page` |
| **one-pager / battlecard** (sales) | "why us for this deal?" | for buyers and the sales team, not search: problem, proof, objections with answers, pricing facts; battlecards name the competitor, claims quoted and dated as in `../comparison-pages` | sales-assisted and enterprise motions |
| **changelog / launch post** | "what's new?" | written from the shipped change and its claims rows; tiered by gtm launch mode | launch mode |

Comparison, "vs" and alternatives pages are `../comparison-pages`: they need its dossier and
fairness gate, then come back here for drafting and shipping.

## Requires

- treg (CLI or MCP) for research. Without it, use built-in web search and fetch, and say the gap
  analysis was skipped.
- `<state>/product-context.md` (positioning, ICP, competitors, voice). If missing, run `../product-context`.
- Optional: a recent `<state>/runs/*/score.json` (gaps, citation targets, fan-out) and
  `<state>/seo/queries.csv` (the query map).

## The pipeline

Write intermediate output to `<state>/pages/<slug>/` so the user can review it and the next run can
refresh the page instead of starting over:

```
<state>/pages/<slug>/
  brief.md        type, intent, prompts and queries, angle, information gain, outline
  recon.json      engine answers + cited sources for the target prompts
  evidence.md     external facts with URLs, read and checked
  claims.md       product claims used on the page → ledger rows → evidence in the repo
```

Sales one-pagers and battlecards skip phases 2 and 6 (no recon, no publishing): they ship as a file
under `<state>/sales/` or a PR to wherever the team keeps sales material.

### Phase 0: ground truth

Build or refresh `<state>/claims.md` from the repo: what the product demonstrably does, what it
does not, and the caveats. Each row cites a file or doc (`references/claims-ledger.md`). Every
product claim on a page maps to an OK row; no row, no claim. Never claim what isn't shipped, and
never use absolutes the evidence can't carry ("100%", "guaranteed", "the only").

### Phase 1: choose the intent

In order: the user's argument; a gap from the latest audit (competitors named, the brand not, in a
bucket where the product fits; listed in `<state>/pages.md`); a `gap` row in the seo query map; or
fresh candidates mined with treg (`references/research-with-treg.md`).

Score each candidate 1-3 on **fit** (the product truly solves it), **gap** (engines and search answer
it poorly or without you), **demand** (volume, forum frequency, fan-out recurrence) and **proof** (the
ledger backs the claims). Ship the highest total; drop anything scoring 1 on fit or proof.

Check the query map first: if a page already owns the query, improve that page instead of writing
a second one.

### Phase 2: recon (treg, ~$0.05)

Run the target question and 2 paraphrases on ChatGPT, Perplexity and Google AI Mode (`catalog_get`
first; state the price). Save to `recon.json`, then note in `brief.md`: the consensus (the page must
state it, better), errors and gaps (the page's reason to exist), the 3-5 most-cited pages (read them
with `treg.web.extract`, free), brands named and why, and ChatGPT's fan-out queries (each becomes an
H2 or FAQ entry).

### Phase 3: evidence, angle and the information-gain gate

- Collect 3-8 external facts from primary sources (regulators, standards, vendor docs, court records,
  peer-reviewed work). **Read each source** and quote it exactly in `evidence.md` with URL and access
  date. Never cite a fact you only saw in an AI answer.
- Give the page **one named idea**: a short, accurate, repeatable frame useful to someone who never buys.
- **Information-gain gate**: write one sentence on what this page has that the current top results
  and cited pages don't (a test you ran, a decision table, a failure mode nobody explains, a
  checklist from real code behavior). If you can't, choose another intent. This sentence goes first
  in `brief.md`.

### Phase 4: draft

Use `references/page-template.md`. In short: H1 in the reader's words; a 2-5 sentence quick answer
that stands alone, with **Updated <date>** visible; question-shaped H2s from fan-out and
People-Also-Ask, each opening with a one-line answer; at least one table or checklist; a
vendor-neutral body (competitors named fairly, from *their* current docs); a 3-5 question FAQ; "From
the publisher" (at most 15-20% of the page, visually separate, claims from `claims.md`, one CTA);
numbered primary sources. 700-1,400 words for answer pages; integration and use-case pages can be
shorter if complete.

### Phase 5: review gates (all must pass)

1. **Claims**: every product statement traces to an OK ledger row; list any you removed.
2. **Facts**: every number and quote has a source you read, linked.
3. **Information gain**: the brief's sentence is true of the finished page.
4. **Quotability**: the quick answer reads as complete when pasted alone into a chat.
5. **Neutrality** (answer and use-case pages): with "From the publisher" deleted, the page is still
   the best answer.
6. **Schema = visible**: JSON-LD (Article, plus FAQPage if there's a FAQ) contains only what's on the
   page; dates match.
7. **Writing**: `../writing` passes, including `claims_guard.py` on the draft.

For security, legal, medical or financial products, **a human signs off on claims before
publishing**. Say so and stop at a PR.

### Phase 6: ship into the site

Follow the site's conventions exactly (framework, layout, components, URL scheme):

- A stable URL (`/guides/<slug>`, `/integrations/<tool>`, `/use-cases/<slug>`); content in the raw
  HTML (static or SSR, never client-only).
- `<title>` ≤ 60 characters, meta description from the quick answer, canonical, Open Graph, JSON-LD.
- A `.md` mirror if the site has them; the sitemap (real `lastmod`), llms.txt under `## Answers`,
  and the JSON feed. Missing feeds are `../ai-search-optimization`'s job; don't hand-roll a partial one.
- Links from 1-3 relevant existing pages.
- Render locally, run `../ai-search-optimization/scripts/check_ai_access.py` on the preview URL, then
  a branch and a PR. Deploying is the user's call.

### Phase 7: measure

- Add the target prompts to `<state>/prompt-panel.json` with `"page": "<url>"` (new ids only).
- Record the page in the seo query map: one row per target query in `<state>/seo/queries.csv`
  (`query,intent,page,status,position,last_checked`, status `live`). One page per query: if another
  row already points that query at a different page, merge the pages instead (`../seo`).
- Mark the intent `shipped <date>` in `<state>/pages.md`. If a work session opened a bet for this
  page, its metric and check date are already set; otherwise suggest recon again 2-3 weeks after
  deploy. If the page isn't cited or ranking by then, check indexing first.

## Refreshing a page

Rerun phase 2 on its prompts and compare with the saved `recon.json`. Update facts and dates only
when something changed, and bump `dateModified` only then. A fake refresh teaches engines to ignore
your dates.

A **news refresh** (from `../news`, decision `refresh`) adds one recent, real example to a page
that already explains its mechanism: two to four sentences, dated, quoting the primary source (the
filing, the regulator, the original report) with its URL in `evidence.md`. It describes what
happened and how, never the exposed content itself, and names private people only if the primary
source does and the page needs it (usually it doesn't). That is a real change, so `dateModified`
moves.

## Spend

A page costs $0.05-0.30 in treg calls: recon at about $0.01 per answer, keyword and
People-Also-Ask lookups at a few cents, page reads free. State the estimate before phase 2 and the
actual spend at the end. Rate calls that invite a `review`, and file `feedback` on anything that
wasted money.
