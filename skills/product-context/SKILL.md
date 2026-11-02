---
name: product-context
description: Create and maintain the product's marketing context - the GTM profile (sales motion, deal size, buyers, sales cycle, where buyers spend attention, regulation, markets), positioning, ICP, objections, switching forces, customer language, brand voice, proof points and accepted learnings - in <state>/product-context.md, and write the structured profile into gtm.json so gtm.py can compute channel fit and the funnel. Run during gtm init, when positioning or pricing changes, when fit_review is due, or when the user asks to "set up product context", "update positioning", "who are we selling to", or "what have we learned". Every drafting skill (writing, one-pager, comparison-pages, citation-outreach, entity-presence) reads its output; claims themselves live in the claims ledger, not here.
---

# Product context

One file every other skill reads before it writes a word: who buys, how they buy, why they switch,
how they talk, and what we have learned. Facts about the product itself live in the claims ledger
(`<state>/claims.md`). This file explains how to use those facts.

Two outputs, kept in step:

| output | for | written by |
|---|---|---|
| `<state>/product-context.md` | the agent and humans: prose, tables, sources | this skill, from `references/product-context-template.md` |
| `profile` block in `<state>/gtm.json` | `gtm.py fit`, `focus`, `funnel` | this skill via `gtm.py profile`; confirmed once the human approves |

`<state>` is the store root: `python3 ../gtm/scripts/gtm.py where` → `"root"`. It is never assumed to
be inside the product repo.

## Before you start

1. `python3 ../gtm/scripts/gtm.py where`. If `initialized` is false, run gtm init first.
2. Read `<state>/claims.md`. If it is missing or older than the last release, build or refresh it
   first (`../one-pager/references/claims-ledger.md`). Positioning built on unverified claims is
   wasted work.
3. **Migrating from 0.3:** if `<state>/profile.md` exists, fold its content into the matching
   sections below, then replace the old file's body with one line: `Moved to product-context.md on
   <date>.` Keep the file so old links still resolve.

## Workflow

### 1. Draft from the repo

Read, in this order, and note the source of every statement you take:

- README, docs, and the in-app copy (onboarding screens, empty states, upgrade prompts).
- The website source: homepage, pricing page, comparison pages, FAQ.
- Pricing configuration, plan definitions, license or billing code (deal size, plans, trials).
- Existing marketing notes in the store (`entity.md`, past digests, `plan.md` learnings).

Fill every section of the template you can support. Mark the rest `unknown` with the question you
would ask. Never fill a gap with a plausible guess.

### 2. Ask only what the repo can't tell you

Batch the open questions into one message, at most six. Typical ones:

- Typical deal size or annual contract value (or lifetime value for consumer products).
- Days from first touch to paying, and who signs off (one person, a small team, a committee).
- Who buys versus who uses, by role.
- Markets you sell in, and whether the category is regulated.
- Two or three phrases customers use for the problem, from calls, tickets or reviews.

### 3. Write the profile into gtm.json

Use `gtm.py profile`; never hand-edit the JSON. Field meanings and allowed values are in
`references/gtm-profile.md`.

```
python3 ../gtm/scripts/gtm.py profile --motion sales_assisted --acv 9000 --cycle-days 45 \
  --regulated light --geo US,UK --buying-committee 2-4
```

- `--motion` must be one of the keys in `../gtm/references/funnel-templates.json`.
- Attention: leave it unset (every channel counts as 1.0) and write "unmeasured" in
  product-context.md. Weights come from measured evidence via `../customer-research` when it is
  installed (`--attention short_video=0.1`), never from your impression of where buyers hang out.
- Any change unconfirms the profile. Until it is confirmed, `gtm.py fit` uses the motion's defaults
  alone (deal size, cycle, regulation and attention are ignored) and says so, and any job that declares it requires a
  confirmed profile is skipped.

Then run `python3 ../gtm/scripts/gtm.py fit` and show the human the channels it rules out and why.
If a result looks wrong, the fix is usually a profile field, not an override.

### 4. Confirm with the human

Present the GTM profile table, the positioning block and the fit result together. Ask for
corrections in one round. Apply them; once the human approves in this conversation, run
`gtm.py profile --confirm` (never in a scheduled run) and log the date in the file's changelog.

## Sections and their rules

| section | rule |
|---|---|
| GTM profile | Mirrors the gtm.json `profile`. Each value carries its source (repo file, human, customer-research run). |
| Positioning | One-liner, category, the problem, alternatives including "do nothing", and differentiators. **Every differentiator names its claims-ledger row.** A differentiator without a row is removed. |
| ICP and anti-ICP | Who gets value fastest, and who should not buy (and why). Outreach and ads skills read the anti-ICP to exclude targets. |
| Objections | The objection in the buyer's words, the honest answer, and the proof (ledger row or page). |
| Switching forces | What pushes buyers off the current approach, what pulls them to us, what keeps them stuck, what scares them about switching. |
| Customer language | Verbatim phrases with their source (ticket id, review URL, call note, thread). No paraphrases. |
| Brand voice | 3-5 attributes, each with a do, a don't, and one real line from existing copy that shows it. |
| Proof points | Only items backed by `claims.md` rows or by permission-granted customer quotes. Numbers keep their qualifier. |
| Learnings | Filled only from accepted bets (below). |
| Changelog | Date, what changed, why. |

## Learnings

Learnings are what make month three smarter than month one, so they are guarded:

1. `python3 ../gtm/scripts/gtm.py learnings` lists candidates: closed bets with a strong method, or
   two bets on one tactic that agree.
2. The digest proposes them. Only after the human accepts one, run
   `python3 ../gtm/scripts/gtm.py learnings --accept <bet id>` and add a row:

   | date | learning | evidence (bet ids) | status |
   |---|---|---|---|
   | 2026-12-10 | Comparison pages lifted "vs" prompts on Perplexity within 3 weeks | b-12 (holdout) | active |

3. When a later bet contradicts a row, set its status to `retired (<bet id>, <date>)`. Never delete
   rows; the history is the point.
4. Never write learnings from a scheduled run without acceptance, and never from a single
   before/after result.

## Keeping it current

| trigger | action |
|---|---|
| `fit_review` job (quarterly) | re-read the profile, refresh attention from customer-research, re-run `gtm.py fit`, propose changes |
| pricing, plans or packaging changed (launch mode) | update deal size and positioning; re-confirm the profile |
| new competitor appears in audits | add it under alternatives and to objections if buyers raise it |
| accepted learning | add the row (above) |

Profile changes after confirmation go back to `confirmed: false` until the human re-confirms, so
fit never silently shifts under the operator.

## Don't

- Don't copy claims into this file. Reference the ledger row; the ledger stays the single source.
- Don't invent customer quotes, logos, metrics or personas.
- Don't set attention weights from intuition.
- Don't keep this file in the product repo unless the store uses the `repo` backend.
