---
name: customer-research
description: Find out where the product's buyers actually spend attention, what they call the problem, and what stops them buying, from public conversations - Reddit, LinkedIn, TikTok, YouTube, X, Hacker News, review sites. Measures attention per channel into an evidence file and turns it into the GTM profile's attention weights (which decide channel fit), mines verbatim customer language and objections into product-context.md. Use during gtm's fit_review, when the user asks "where are our buyers", "what do customers say about this problem", "is TikTok/LinkedIn worth it for us", for voice-of-customer or objection research, or before positioning work. The profile and positioning themselves live in ../product-context; fit is computed by ../gtm.
---

# Customer research

Channel fit starts from defaults for the sales motion. This skill replaces the guess about where
buyers are with a count: for the problem the product solves, how much of what each platform shows is
the ICP actually talking about it. It also brings back the words buyers use, which every drafting
skill needs.

`<state>` is the store root printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
scripts from the product repo root, calling the plugin's scripts by absolute path (`scripts/…` is
this skill's folder).

## When it runs

- gtm's `fit_review` job (quarterly), and whenever the GTM profile changes (new ICP, new motion).
- On demand, before positioning or a new channel bet.
- Budget: $1 per run by default. Check `gtm.py budget --need 1` first and state the estimate.

## 1. Attention measurement

1. **Queries.** From `<state>/product-context.md`, write 3-5 problem queries in buyers' words (the
   problem, the job, the workaround they use today), not the product's name or category jargon.
2. **Sample.** For each source in `references/sources.md`, run the queries and read the most recent
   results (aim for 30-40 per source across the queries; at least 15, or the source counts as
   unmeasured). Record `sampled` (results read) and `relevant` (results where the ICP itself
   discusses the problem, compares options, asks for recommendations, or reports a purchase).
   Vendors' own posts, recruiters, unrelated meanings of the words and spam are not relevant. Keep
   2-5 example URLs per source.
3. **Write the evidence file** `<state>/research/attention-<date>.json`:

```json
{"date": "2026-11-12", "icp": "compliance leads at mid-size banks",
 "queries": ["redact documents before sharing with auditors", "..."],
 "sources": {
   "reddit":   {"sampled": 40, "relevant": 9,  "examples": ["https://..."]},
   "linkedin": {"sampled": 40, "relevant": 22, "examples": ["https://..."]},
   "tiktok":   {"sampled": 30, "relevant": 0,  "examples": []}}}
```

   Source keys: `reddit`, `forums`, `stackoverflow`, `hackernews`, `g2`, `capterra`, `linkedin`,
   `tiktok`, `instagram`, `youtube_shorts`, `youtube`, `creators`, `newsletters`, `podcasts`, `press`,
   `search`. Each maps to a channel in `../gtm/references/channel-fit.json`.

4. **Weights.** `python3 scripts/attention.py <state>/research/attention-<date>.json` prints the
   proposed weight per channel (each channel's best relevant share relative to the best channel,
   floored at 0.05) and the channels left unmeasured.
5. **Propose, then apply.** Put the weights, the counts behind them, and the channels whose
   eligibility would change (compare each weight with `gtm.py fit`'s current `matrix` and `fit`) in
   the digest. Apply only after the human agrees: `attention.py <file> --apply`. Applying unconfirms the profile, so the human
   confirms it again with the product-context skill (`gtm.py profile --confirm`, never in a
   scheduled run).

AI search and the product's own site aren't measured here; they keep a weight of 1.0. A channel with
weak evidence keeps its default rather than a weight built on 8 results.

## 2. Customer language

While sampling, copy the phrases buyers use, verbatim, with the source URL:

- how they describe the problem and what it costs them;
- what they call the category and the alternatives (including the workaround and "do nothing");
- what they praise or complain about in alternatives (patterns with counts, not individuals).

Add them to the "Customer language" section of `<state>/product-context.md` with source and date.
Never paraphrase into the verbatim column, and never attribute a quote to a named person.

## 3. Objections

From threads where buyers decide against something, or ask "is X worth it", record the objection in
their words, how often it appeared, and whether the claims ledger can answer it. Objections the
ledger can't answer go to the digest as questions for the human; answered ones go to the
product-context "Objections" section.

## Rules

- Public content only. Don't log in as anyone, join private groups, or message people.
- Report counts, not anecdotes. One viral thread is a sample of one.
- Keep personal data out: store URLs to public posts, not names, handles or profile details.
- Date everything. Attention drifts; the quarterly fit review re-measures it.

## Spend

Search calls are fractions of a cent to a few cents each (`references/sources.md`). A full
attention run with 5 queries across 8 sources is typically $0.20-0.60. Record it with
`gtm.py record fit_review --cost <usd>` (or the job that triggered the run).
