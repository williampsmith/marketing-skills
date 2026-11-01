---
name: one-pager
description: Research, write and ship a single-intent "one-pager" answer article for a product's website, built to be cited by AI answer engines (ChatGPT, Perplexity, Google AI Mode, Claude). Run inside the product repo; it reads the code and docs as ground truth for every product claim, uses treg to find the intent and see what the engines currently answer and cite, writes a dated quick-answer page with matching JSON-LD, and wires it into the site, sitemap, llms.txt and feed. Use when the user asks for a one-pager, answer page, AEO/GEO article, comparison page, "write a page so ChatGPT recommends us for X", or to work the backlog in .marketing/pages.md.
---

# One-pager

One page answers one intent better than anything the engines cite today, and every product claim
on it is backed by the code. That combination is the moat: competitors can copy the format, but
not claims you can prove from your own source.

A one-pager is **not** a product pitch. It is the most useful answer to a question a buyer asks an
assistant, written by the team that knows the problem best. The product shows up where it honestly
fits, in a separate section at the end.

Arguments: an intent or question, a prompt id from the panel, or nothing (pick from the backlog).

## Requires

- treg (CLI or MCP) for research. Without it, use built-in web search and fetch, and say the gap
  analysis was skipped.
- `.marketing/profile.md` (positioning, ICP, competitors). If it's missing, draft it from the repo
  and confirm it with the user, as described in the `ai-visibility-audit` skill.
- Optional but valuable: a recent `.marketing/runs/*/score.json` (gaps, citation targets, fan-out).

## The pipeline

Work through the phases in order. Write intermediate output to `.marketing/pages/<slug>/` so the
user can review it, and so the next run can refresh the page instead of starting over.

```
.marketing/pages/<slug>/
  brief.md        intent, prompts, angle, outline (phase 1-3)
  recon.json      engine answers + cited sources for the target prompts (phase 2)
  evidence.md     external facts with URLs, read and checked (phase 3)
  claims.md       product claims used on the page → evidence in the repo (phase 4)
```

### Phase 0 — Ground truth: the claims ledger

Before any research, build or refresh `.marketing/claims.md` from the repo: what the product
demonstrably does, what it does not do, and the caveats. Each row cites a file or doc. Method and
format: `references/claims-ledger.md`.

Two rules apply throughout:

- **Every product claim on the page maps to a ledger row marked OK.** If there's no row, there's no
  claim. An outdated strategy doc is not evidence; code, tests and shipped docs are.
- **Never claim what isn't shipped, and never use absolutes the evidence can't carry** ("100%",
  "unrecoverable", "guaranteed", "the only", "proof"). In regulated or security categories, this
  is where FTC claim-substantiation risk lives.

### Phase 1 — Choose the intent

Pick the intent in this order of preference:

1. The user's argument.
2. A gap from the latest audit: a prompt where competitors are named and the brand is not, in a
   bucket where the product honestly fits. These are already listed in `.marketing/pages.md`.
3. Mine fresh candidates with treg. Recipes are in `references/research-with-treg.md`: keyword
   ideas, People-Also-Ask, Reddit/forum questions, and ChatGPT fan-out queries.

Score each candidate 1-3 on: **fit** (the product truly solves it), **gap** (engines answer it
poorly or without you), **demand** (volume, forum frequency, fan-out recurrence), and **proof**
(the ledger can back the relevant claims). Ship the highest total. Drop any candidate that scores 1
on fit or proof, however attractive the volume.

Write `brief.md`: the intent as one question, 3-5 paraphrased prompts (how different buyers would
ask), the audience, and the decision the reader is trying to make.

### Phase 2 — Recon: what the engines say now (treg, ~$0.05)

Run the target question and 2 paraphrases on ChatGPT, Perplexity and Google AI Mode (endpoints
and bodies as in the audit panel; `catalog_get` first, state the price). Save to `recon.json`, then
record in `brief.md`:

- **Consensus**: what all the answers agree on. The page must state it too, and state it better.
- **Errors and gaps**: wrong, outdated or missing points. These are the page's reason to exist.
- **Cited sources**: read the 3-5 most-cited pages (`treg.web.extract`, free via TinyFish). Note
  their format, depth and freshness, and what they leave out.
- **Brands named**: who wins now, and why the answers say they do.
- **Fan-out**: ChatGPT's `searchQueries`. Each sub-question it searched becomes an H2 or FAQ entry.

### Phase 3 — Evidence and angle

- Collect 3-8 external facts that make the page quotable: statistics, standards, regulations,
  incidents and dates. Use primary sources (regulators, standards bodies, court records, vendor
  docs, peer-reviewed work). Find them with `exa.web.answer` / `treg.web.search` and news search
  for anything time-sensitive, then **read each source** and quote it exactly. Log each in
  `evidence.md` with URL, quote and access date. Never cite a fact you only saw in an AI answer.
- **Give it one named idea**: a short, repeatable frame the page introduces (in the spirit of "the
  lethal trifecta" or "redact before you upload"). Named ideas get repeated, and repeated phrases
  get attributed. It must still be accurate and useful to someone who never buys.
- **State the information gain**: one sentence on what this page offers that the cited pages
  don't, such as a test you ran, a decision table, a failure mode nobody explains, or a checklist
  taken from real code behavior. If you can't write that sentence, choose another intent.

### Phase 4 — Draft

Use `references/page-template.md`. The short version:

- **H1** = the question or intent in the reader's words.
- **Quick answer** right under it: 2-5 sentences that stand alone if quoted, specific, with
  **Updated <date>** visible.
- Question-shaped **H2s** from the fan-out and People-Also-Ask, each opening with its own one-line answer.
- At least one **table or checklist** (comparisons, decision criteria, steps). Engines lift these.
- **Vendor-neutral body.** Name competitors fairly when the intent is a comparison, using claims
  checked against *their* current docs (read them; quote their pricing pages, don't guess).
- **FAQ**: 3-5 questions from People-Also-Ask or fan-out, answered in 1-3 sentences.
- **From the publisher** (at most 15-20% of the page, visually separate): where the product fits,
  what it doesn't do, and a single CTA. All claims come from `claims.md`.
- **Sources**: numbered, linked, primary sources.
- 700-1,400 words. Long enough to be the best answer, short enough to read in one screen of scrolling.

Write `claims.md` for the page: every product sentence → ledger row → repo evidence.

### Phase 5 — Review gates (all must pass)

1. **Claims**: every product statement traces to an OK ledger row, with no absolutes the evidence
   can't support. List any you removed.
2. **Facts**: every number and quote in the body has a source you read, with a link.
3. **Quotability**: the quick answer reads as complete when pasted alone into a chat.
4. **Neutrality**: delete the "From the publisher" section and the page should still be the best
   answer to the intent.
5. **Schema = visible**: JSON-LD (Article, plus FAQPage if there's a FAQ) contains only what's on the
   page, and the dates match the visible date.
6. **Plain language**: no hype adjectives or filler, and no "in today's fast-paced world".

If the repo has a reviewer agent (e.g. `.claude/agents/*review*`) or a claims memory, run the
draft past it. For security, legal, medical or financial products, **a human signs off on claims
before publishing**. Say so and stop at a PR.

### Phase 6 — Ship into the site

Find the site in the repo (or ask), and follow its conventions exactly: framework, layout,
components, CSS, URL scheme. Then:

- Create the page at a stable, descriptive URL (`/guides/<slug>`, `/compare/<a>-vs-<b>`), with the
  content in the raw HTML (static or SSR, never client-only).
- `<title>` ≤ 60 characters, meta description = the quick answer shortened, canonical, Open Graph tags,
  and the JSON-LD.
- Publish a `.md` mirror if the site has them.
- Add the page to the sitemap (with a real `lastmod`), llms.txt under `## Answers`, and the JSON feed.
  If those don't exist yet, hand off to `ai-search-optimization` and don't hand-roll a partial version.
- Link to the page from 1-3 relevant existing pages (internal links tell crawlers the page matters).
- Build or serve the site locally and check the page renders, then run
  `../ai-search-optimization/scripts/check_ai_access.py` (sibling skill in this plugin) against the local or preview URL for that path.
- Commit on a branch and open a PR. Deploying is the user's call.

### Phase 7 — Measure

- Add the target prompts to `.marketing/prompt-panel.json` with `"page": "<url>"` (new ids, never
  reuse old ones) so the next audit tracks the page.
- Mark the intent `shipped <date>` in `.marketing/pages.md`.
- Suggest re-running recon on the target prompts 2-3 weeks after deploy. If the page isn't cited by
  then, check indexing first (Bing Webmaster, Search Console) before rewriting.

## Refreshing an existing one-pager

Rerun phase 2 on its prompts and compare with the saved `recon.json`. Update facts and dates only
when something actually changed, and bump `dateModified` only then. A fake refresh teaches
engines to ignore your dates.

## Spend

A typical page costs $0.05-0.30 in treg calls: recon at about $0.01 per answer, keyword and People-Also-Ask
lookups at a few cents, page reads free. State the estimate before phase 2 and report the actual
spend at the end. Rate calls that invite a `review`, and file `feedback` on anything that wasted money.
