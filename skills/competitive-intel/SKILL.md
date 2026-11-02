---
name: competitive-intel
description: Know what competitors say, charge and do, from their own public pages and public data, with every claim quoted and dated. Three modes - profile (positioning, pricing, packaging and claims for one competitor), watch (the shared page watcher that flags when a competitor's pricing, docs or claims change, also used by comparison-pages, citation-outreach and entity-presence), and teardown (a dated history of a competitor's growth moves - traffic trend, ads, rankings, content cadence, launches, hiring, reviews - turned into plays for this product). Use when the user asks to profile or watch a competitor, "what is X doing", "how did X grow", for a competitive teardown, or when gtm's watch job is due. Comparison pages themselves are ../comparison-pages; the product's own positioning is ../product-context.
---

# Competitive intel

Competitor facts age fast and wrong ones are expensive: a stale price on a comparison page is a
false-advertising risk, and a plan built on a rumour wastes a quarter. So this skill keeps one rule
above the rest: **every statement about a competitor is a quote from a source you read, with its
URL and the date you read it.** Opinions about what it means go in a separate section, labelled.

`<state>` is the store root printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
scripts from the product repo root, calling the plugin's scripts by absolute path (`scripts/…` is
this skill's folder).

## State

```
<state>/competitors/<slug>.md            profile / dossier: sourced facts (shared with ../comparison-pages)
<state>/competitors/<slug>/teardown.md   teardown history and plays
<state>/watch.json                       pages being watched, by purpose
<state>/watch/<id>/, watch/report.md     snapshots and the latest change report
```

Competitors come from `<state>/product-context.md` (alternatives) and from the brands the audit
names instead of you (`named_instead` in the latest `<state>/runs/*/score.json`).

## Profile mode

For one competitor, read their own pages through `treg.web.extract` (header
`X-Treg-Route-Prefer: tinyfish`, free) and record in `<state>/competitors/<slug>.md`:

| section | from | notes |
|---|---|---|
| Positioning | homepage, about page, meta description | their one-liner and category words, quoted |
| Pricing and packaging | pricing page | plans, prices, limits, trial terms; currency and region as shown |
| Claims | product, security and comparison pages | each claim quoted; mark ones that conflict with your claims ledger |
| Who they target | case studies, industries pages, job posts | quote, don't infer |
| Where they show up | ads (below), the AI answers in your audit runs | which prompts name them, which pages cite them |

Every row: the quote, the URL, the date read. Add each source page to the watch list (below) with
`--used-by` naming the pages or dossiers that rely on it. A profile is a snapshot; teardown is the
history.

## Watch mode

The watcher is shared: `../comparison-pages`, `../citation-outreach` and `../entity-presence` use
the same script and file.

```
python3 scripts/watch_pages.py                                   # all watched pages (gtm's `watch` job)
python3 scripts/watch_pages.py --only competitor                 # one purpose group
python3 scripts/watch_pages.py --add https://x.com/pricing --purpose competitor --used-by <page or dossier>
```

| purpose | what a change means | who acts |
|---|---|---|
| `competitor` | their pricing, docs or claims changed | `comparison_refresh` in gtm re-checks the pages listed in `used_by` |
| `target` | a page you pitched started or stopped mentioning you | `../citation-outreach` updates the target's status |
| `profile` | a directory or review profile no longer carries the canonical description | `../entity-presence` |

Changes land in `<state>/watch/report.md`; gtm turns a "Changed" entry into a `comparison_refresh`
job on the next tick. The watcher is free (treg's routed extractor, falling back to a plain fetch).
Record the job with `gtm.py record watch`.

## Teardown mode

A teardown explains how a competitor grew, in date order, from public evidence, and ends in plays
this product can run. Method, sources and the output format: `references/teardown.md`.

1. **Scope.** One competitor, a window (default the last 24 months), and a spend cap (default $2;
   check with `gtm.py budget --need <usd>` first and state the estimate).
2. **Curve.** Monthly traffic estimates for their domain, so you can see when growth happened.
3. **Moves.** For the months around each inflection: ads they ran, keywords they started ranking for,
   content they published, launches, pricing changes, hiring, review volume, press.
4. **Lined up, not proven.** A move that coincides with growth is a candidate, not a cause. Mark each
   play with the evidence strength (several signals agree, one signal, coincidence only).
5. **Plays.** For each candidate worth trying, name the gtm tactic and skill that would run it here
   (`../gtm/references/channel-fit.json`), and whether its channel is eligible for this product
   (`gtm.py fit`). A play on an ineligible channel is noted and not proposed.
6. Write `<state>/competitors/<slug>/teardown.md` and propose the top 3 plays as backlog items in
   the digest. They become bets only through a work session.

## Fairness and limits

- Quote and date every competitor fact. Paraphrase only in your analysis section, which is labelled
  as analysis.
- Traffic, keyword and ad-spend numbers from third-party tools are estimates. Say so next to every
  number, with the provider.
- Never sign up, buy, or contact a competitor's staff while posing as a customer. Read public pages
  only. Never collect personal data about their employees beyond what a job post states.
- Reviews: report patterns with counts, never quote an individual reviewer by name.

## Spend

Profiles and the watcher are free or nearly free. A teardown typically costs $0.50-2.00 (traffic
history and ranked keywords are the expensive calls). Record the spend with `gtm.py record` and
report it in the digest.
