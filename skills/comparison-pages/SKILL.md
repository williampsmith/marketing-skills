---
name: comparison-pages
description: Build and maintain honest "X vs Y", "alternatives to X" and "switching from X" pages that AI answer engines cite on high-intent comparison questions. Builds a sourced dossier per competitor through treg (their own pricing and docs pages, the ads they run, review-complaint patterns, what the engines say about them), enforces a fairness gate where every claim about a competitor is quoted from their current page with a date, ships the page through the one-pager pipeline, and watches competitor pages so comparisons are refreshed when competitors change. Use when the audit shows losses on comparison/alternatives prompts, or the user asks for comparison pages, competitor pages, "vs" pages, alternatives pages, or competitive positioning content.
---

# Comparison pages

**Why it works.** "X vs Y" and "alternatives to X" come from people who are already in the market,
often already using X and unhappy with it. These questions convert best, and they're where a
challenger can win. The pages engines find for them today are usually the incumbent's own page
(biased) or affiliate roundups (biased toward commission). A specific, fair, current comparison from
someone who knows the problem well is often the best source available. It gets cited, and when the
reader's needs fit, it names you.

The catch is that comparison pages break in two ways. They're **unfair**: one-sided pages get
discounted by readers and engines, and false comparative claims are a legal risk (false
advertising). Or they're **stale**: the competitor changes pricing or ships the missing feature, and
your page is now wrong. This skill exists for those two failure modes. The writing itself is the
`one-pager` pipeline.

`<state>` below is the marketing state directory printed by `python3 ../gtm/scripts/gtm.py where`
(field `root`). It lives outside the product repo by default; site changes still go to the product
repo as PRs.

Copy drafted by this skill must pass the `../writing` gates first: every claim from the ledger, something
the current top answers lack, and no AI-tell phrasing.

## Requires

- `<state>/product-context.md`, `<state>/claims.md` (your side of every comparison)
- The `one-pager` skill (drafting, review gates, shipping) and a recent audit run if available
- treg for competitor research (mostly free page reads; a few cents for ads and reviews)

## State

```
<state>/competitors/<slug>.md   dossier: sourced facts with URL + date + quote
<state>/watch.json              competitor source pages, each mapped to the pages that cite it
<state>/pages/<slug>/           as in one-pager, plus grid.md (the sourced comparison grid)
```

## The run

### 1. Pick the matchup

From the audit: `comparison` and `alternatives` prompts you lose, and `named_instead` across all
gaps (the brands the engines actually put next to you). Check demand with
`treg.google.keywords.volume` on "<X> vs <you>", "<X> alternative(s)", "<X> vs <Y>". State the cost
first; it's well under a cent per keyword with SE Ranking.

Choose the page type:

| type | when | shape |
|---|---|---|
| `<X> vs <You>` | engines already compare you, or there's search demand | balanced grid, "choose X if / choose us if" |
| `Alternatives to <X> for <constraint>` | X dominates and buyers are looking to leave | criteria first, then 4-7 options **including ones that aren't you** |
| `Switching from <X>` | you win on a clear constraint and migration is the fear | steps, what carries over, what doesn't |
| `<X> vs <Y>` (neither is you) | you can be the neutral expert on a category question | the strongest credibility play; you appear only in the publisher section |

### 2. Build or refresh the dossier

`<state>/competitors/<slug>.md`. Every line has a source URL, an access date, and a quote. See
`references/dossier-template.md`.

- **Their own pages**: pricing, features, security and privacy, docs, changelog, system requirements
  (`treg.web.extract`, free; `treg.web.map` with `q` to find the right pages on their site). Their
  own docs are the only acceptable source for "X does / doesn't do Y". If their docs are silent, the
  answer is "not documented", never "no".
- **What they pay to say**: `catalog_search "google ads transparency"` (e.g.
  `scrapecreators.x.v1-google-company-ads`, ~$0.002) shows the claims they defend with money,
  which is their positioning.
- **What users complain about**: Trustpilot (`trustpilot.business.reviews`), app store reviews,
  Reddit search. Report patterns with counts ("23 of 140 recent reviews mention X"), never quotes
  that identify an individual. G2 and Capterra aren't in the treg catalog yet (requested); read
  public pages through `treg.web.extract` if needed.
- **What the engines say about them**: the audit's answers, or a quick recon run. Note what
  engines get wrong about them too, and don't repeat those errors.

Add every source page to the watch list, mapped to the pages that will rely on it:

```bash
python3 <skill>/scripts/watch_pages.py --add https://competitor.com/pricing --purpose competitor --used-by site/compare/x-vs-us.html
```

### 3. Build the grid (the fairness gate)

`grid.md` comes before any prose. One row per criterion the *buyer* cares about (from forum
language and the fan-out queries), not per feature you happen to win. Each cell has a value and a
source:

| criterion | You | X | source (X) |
|---|---|---|---|
| Works offline | Yes (claims: local-only) | Desktop app: yes; web: no | x.com/docs/offline, 2026-11-01 |

The rules:

- **Your cells** come from OK rows in the claims ledger, with their qualifiers.
- **Their cells** quote their current page with a date. "Not documented" is a valid value; "no"
  without a source isn't.
- **Include the rows where they win.** A grid you win on every row reads as an ad, and readers and
  engines discount it. Choose criteria by buyer importance, then let the results fall where they fall.
- Prices and plans carry "as of <date>".
- Use competitor names nominatively. Don't use their logos or anything that implies affiliation, and
  don't disparage. Describe, cite, and let the reader decide.

### 4. Write and ship through `one-pager`

Run the `one-pager` pipeline from phase 2, with the grid as the core asset:

- The quick answer states who each option is for. "X if you need A and B; <You> if you need C,"
  with no "best".
- Include a "choose <X> if" section that's actually useful to people who should choose X.
- For alternatives pages, list options in order of fit for the stated constraint, with your product
  in its honest position.
- Put the as-of date at the top and in `dateModified`.
- Extra review gate: **every competitor statement has a source in the dossier** dated within the
  last 90 days. Re-read the source if it's older.

### 5. Keep it true

The scheduled run (or `gtm weekly`) runs:

```bash
python3 <skill>/scripts/watch_pages.py --only competitor
```

For each `CHANGED` competitor page, read the diff in `<state>/watch/report.md`. If a fact in the
grid moved (price, plan, feature, platform), update the dossier and grid, revise the affected pages
listed in `used_by`, bump `dateModified`, and open a PR. Cosmetic changes need nothing.
Re-verify every comparison page at least quarterly even if no change was detected, because watchers
miss pages behind scripts or logins.

### 6. Measure

Tag the panel's comparison and alternatives prompts with `"page": "<url>"`. Wins show up as those
prompts flipping to named, and as a better rank among the brands named (`avg_rank_when_named`).

## Spend

Dossier: mostly free reads plus about $0.01-0.05 for ads and reviews. Keyword volume is under a cent.
Recon is ~$0.03. The watcher is free (treg extractor via TinyFish). Report actual spend and rate
calls that invite a `review`.
