---
name: entity-presence
description: Make a product a clear, consistent entity that AI models and answer engines recognize - one canonical description, accurate profiles on the knowledge graphs, company databases, software directories, app stores and code hosts that models learn from and retrieve for brand questions, linked together with sameAs. Probes what models believe about the brand from training alone vs with web search, finds name collisions and wrong facts, and produces paste-ready copy per platform for a human to apply. Use when AI answers don't know the product, describe it wrongly, confuse it with something else, or when the user asks about knowledge graph, Wikidata, G2/Crunchbase profiles, brand SERP, or "brand" prompts in the audit.
---

# Entity presence

**Why it works.** A model doesn't store a product as a web page. It stores an *entity*: a name tied
to a type ("PDF redaction app"), a maker, platforms, and the categories it belongs to. That picture
is built from every mention in its training data, and it relies most on sources that are
structured, widely copied, and agree with each other: Wikidata, company databases, software
directories, app stores and code hosts. If those sources are missing or contradict each other, the
model's picture is vague or wrong. Then it can't name you for a category, and it may confuse you
with a similarly named thing.

This pays off on two timescales:

- **Now:** brand questions ("is X legit", "X pricing", "what is X") make engines search, and they
  usually land on these profiles, not your homepage.
- **Later:** each new model generation trains on them. Entity work is the only lever here that
  improves what a model knows *before* it searches anything, and those gains carry forward into
  future models.

`<state>` below is the marketing state directory printed by `python3 ../gtm/scripts/gtm.py where`
(field `root`). It lives outside the product repo by default; site changes still go to the product
repo as PRs.

Copy drafted by this skill must pass the `../writing` gates first: every claim from the ledger, something
the current top answers lack, and no AI-tell phrasing.

## Requires

- `<state>/product-context.md` and `<state>/claims.md` (descriptions are claims too).
- treg for probes (~$0.01-0.05 per question per engine) and page reads (free).
- A human for anything behind a login. This skill prepares the exact copy; it never creates
  accounts or posts.

## State

```
<state>/entity.md          the canonical entity card (single source of truth)
<state>/entity/inventory.md   every profile: URL, status, drift from the card, action
<state>/entity/probe-<date>.md  what the models believe, with and without search
```

## The run

### 1. Write the canonical entity card

`<state>/entity.md`, built from `<state>/product-context.md` and the claims ledger and confirmed by the user:

- **Name** exactly as it should appear, plus spellings to avoid. Also the legal entity and maker.
- **Type / category**, in the words buyers and directories use ("PDF redaction software").
- **One-liner**, at most 160 characters. Fits every short field, uses no hype words, and is the same
  everywhere.
- **Short description**, about 300 characters, and **long description**, about 750 (field limits vary;
  keep all three).
- **Facts**: founded, HQ country, platforms, pricing model, license, website, docs, support,
  status page, logo URL (square, at least 512 px), founders or key people (only if they agree to be named).
- **Official profiles** (`sameAs`): filled in during step 3.

Every profile, the site's Organization schema, llms.txt and the homepage use this text. Most entity
problems are inconsistency problems.

### 2. Probe what the models believe (treg)

Run 4-6 brand questions ("What is <name>?", "Who makes <name>?", "Is <name> safe to use?",
"<name> pricing", "What is <name> used for?") in two ways:

- **Trained knowledge only**: Claude via `dataforseo.x.ai-optimization-claude-llm-responses-live`
  (model API), plus any other model-API answer endpoint the catalog offers (`catalog_search "LLM
  answer to a prompt"`). This is what the model learned in training. **Check that the answer has no
  sources.** On 2026-11-01, ChatGPT's `"disableWebSearch": true` on `cloro.ai-search.chatgpt.scrape`
  still searched (18 sources; reported to treg). An answer with sources is a retrieval answer,
  whatever the flag says.
- **With retrieval**: ChatGPT with search on, Perplexity, and Google AI Mode, keeping their cited
  sources. This shows what the engines find today and where they find it.

A throwaway panel works with the audit's `run_panel.py`. See `references/probe-panel.json`.
State the cost before running (about $0.15 for 6 questions × 5 engine variants).

Record in `probe-<date>.md`:

| finding | meaning |
|---|---|
| Trained knowledge: "I'm not aware of…" | not yet an entity in training data; profiles and mentions are the fix, payoff in the next model |
| Trained knowledge describes something else with your name | **name collision**: disambiguate everywhere ("Acme, the PDF redaction app") and on the site |
| Retrieval right, trained knowledge wrong or empty | fine for now; keep the profiles consistent so the next model learns it |
| Retrieval wrong | a source the engine cites is wrong: fix that profile, or send it to `citation-outreach` as a correction |
| Retrieval cites only your site | no third-party corroboration: profiles and reviews come first |

Also check the search results directly: routed `treg.google.serp.organic` for the brand name shows
the knowledge panel (if any) and which profiles rank. Those rankings are what the engines retrieve.

### 3. Inventory the profiles

Check each platform in `references/platforms.md` that fits the product: search
`site:<platform> "<name>"` through `treg.web.search` (free via TinyFish), then read the profile
(`treg.web.extract`, free). For each one record: exists? claimed? description matches the card?
category correct? links to the site? last updated? review count?

Rank the fixes:

1. Wrong facts on any profile an engine cites (seen in the probe or the audit's sources).
2. Missing profiles on the platforms engines cite for your category (look at `top_cited_domains`
   in the audit, e.g. g2.com, alternativeto.net, apps.apple.com).
3. Stale or inconsistent descriptions.
4. Everything else that fits.

### 4. Prepare the fixes (paste-ready)

For each profile write the exact field values: name, one-liner, description, category,
website, logo, and links. Respect each platform's field limits and category taxonomy. Put them in
`inventory.md` as a checklist for the human who owns the logins.

- **Wikidata**: create or extend an item only if the product meets Wikidata's notability bar (at
  least one serious, independent public reference). Prepare the statements (instance of, developer,
  official website, platform, inception, logo) as a QuickStatements batch with a reference for each,
  for a human to review and run. Disclose the affiliation on the item's talk page.
- **Wikipedia**: never write or edit your own article. If independent coverage exists, the most that's
  acceptable is a disclosed request on a talk page.
- **Directories and stores**: the claimed listing uses the card's text. Pick the category the
  buyer browses, not the most flattering one.
- **GitHub / package registries**: org description, website field and topics match the card.
- **Reviews**: ask real customers for reviews on the one or two review platforms the engines cite.
  Ask everyone, or a random sample, never only happy customers (gated or selective review requests
  can breach the FTC's 2024 fake-review rule). No incentives unless the platform allows them and they
  are disclosed. Draft the ask email and suggest a good moment in the product to ask.

### 5. Wire the site to the entity

Hand off to `ai-search-optimization` or do it directly:

- Organization schema `sameAs` lists every official profile from the inventory. `name`,
  `description` and `logo` come from the card.
- An **About** page with the card's facts in plain text: what it is, who makes it, since when,
  where, and how to contact them.
- If there's a name collision, put a one-line disambiguation on the homepage and About page, and a
  "not to be confused with" note in llms.txt.

### 6. Watch and measure

- Add every official profile to the watch list with the one-liner as the expected text:
  `python3 ../competitive-intel/scripts/watch_pages.py --add <url> --purpose profile --expect "<a distinctive phrase from the one-liner>"`.
  Profiles drift: directories rewrite descriptions and marketplaces change categories.
- Re-run the probe quarterly, and whenever a major model version ships. Trained-knowledge results
  only move when new models are trained, so they're slow and shouldn't be expected weekly.
- The audit's `brand` bucket is the weekly metric for this skill.

## Spend

Probe: ~$0.15. Inventory: mostly free reads, plus a few cents for search results. Review requests: $0.
Report actual spend and rate calls that invite a `review`.
