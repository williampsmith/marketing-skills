---
name: creative
description: Produce marketing creative for a bet - short-form video and UGC-style hooks, product demo clips, LinkedIn document and diagram posts, static images, voiceovers - in the formats that fit the product's channels. Starts from a brief (channel, format, audience, one claim from the claims ledger), researches what works in that channel through treg (trending short-form, top LinkedIn posts, competitors' ad libraries), writes scripts and variants through the writing gates, generates through treg's image, video and voice models with the cost recorded, and builds a review page for a human. Nothing is published from this skill. Use when a work session picks a creative tactic (ugc_hooks, demo_clip, document_post, tutorial_video), or the user asks for ads, UGC, hooks, a demo video, social graphics or creative for a launch. Posting organic copy is ../social; paid placement is ../paid.
---

# Creative

Creative serves a channel, and `gtm.py fit` decides which channels fit. So the same request comes
out differently by product: a consumer app gets UGC hooks for TikTok and Reels, an enterprise product
gets a two-minute demo, a LinkedIn document post or a diagram of the workflow. When the user asks for
a format on a channel `gtm.py fit` rules out, say so with the reason and offer the formats that fit
(`references/formats.md`).

`<state>` is the directory printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
scripts from the product repo root by absolute path. Scripts and captions pass the `../writing` gates.

## 1. Brief

Every batch starts from a bet (`gtm.py bet list --status open`) or a launch. Write
`<state>/creative/<batch>/brief.md`, where the batch is `<date>-<slug>`:

| field | from |
|---|---|
| channel and format | the tactic `gtm.py next` offered; the channel must be eligible in `gtm.py fit` |
| audience | the ICP and customer language in `<state>/product-context.md` |
| the one claim | one OK row of `<state>/claims.md`, quoted with its qualifier |
| proof shown | what the viewer sees that makes the claim believable (the product doing it) |
| metric | what the bet measures (hook rate, click-through, cost per first step) |
| budget | the generation spend for the batch; check `gtm.py budget --need <usd>` first |

## 2. Research the channel

Look at what is working now in that channel for this audience, and write 5-10 patterns (hook,
structure, length, visual) in the brief with links. Examples (checked 2026-11-02; verify with
`catalog_get` and state prices before batching):

| channel | look at | endpoints |
|---|---|---|
| short video (consumer) | top recent videos for the problem's keywords and hashtags | `treg.tiktok.search.videos` (routed), `tikhub.tiktok.hashtag.videos` |
| LinkedIn (B2B) | posts on the problem by people in the ICP, and what got discussion | `anyapi.linkedin.search.posts`, `harvestapi.linkedin.post.search` |
| competitors' ads | what they run and keep running (long-running ads are the ones that work) | `treg.meta-ads.library.advertiser` (routed), `adyntel.linkedin.search.ads.company`, `harvestapi.linkedin.ads.search` |

Copy patterns, never assets: no competitor footage, music you don't have rights to, or someone's
likeness.

## 3. Scripts and variants

Write 3-8 variants that change one thing each (the hook, the first visual, the claim's framing), so
the results say something. Each variant gets an id, a script, and its claim row. Run them through
`../writing` (claims gate, no AI-tell phrasing). On-screen text and captions count as copy.

## 4. Generate

Use treg's generation models through the CLI, and record the spend:

| asset | examples (checked 2026-11-02) |
|---|---|
| image | `replicate.image-gen.flux-schnell`, `minimax.image-gen.from_text` |
| video | `replicate.video-gen.seedance-1-lite`, `replicate.video-gen.veo-3.1-fast` |
| voice | `fishaudio.tts.s2-1-pro` (check the price per call; voice is the costly part) |

If the treg plugin's `make-ugc` skill is installed, use it for UGC-style batches: it covers hook
research, presenter generation and captions. Prefer real screen recordings of the product for demo
clips; generated footage of a product UI is a claim the product has to live up to.

`gtm.py record creative --cost <usd> --note "creative <batch>"` once the batch is generated.

## 5. Review page

Write `<state>/creative/<batch>/manifest.json`, one entry per asset:

```json
[{"id": "hook-03", "file": "hook-03.mp4", "channel": "short_video", "format": "ugc_hook",
  "claim_row": "Checks every export and refuses to save one that fails", "script": "...",
  "ai_generated": true, "disclosure": "AI-generated presenter", "cost_usd": 0.86}]
```

Then `python3 scripts/review_page.py <state>/creative/<batch>`. It writes `review.html` next to the
assets and refuses if any asset has no claim row, or is AI-generated without a disclosure. Put the
page path and the asset count in the digest's **Needs you**; the human replies
"approve creative <batch>: hook-01, hook-03" and posts or uploads what they approved.

## 6. Measure

After a human publishes, record per asset what the bet measures, from the channel's own analytics
or PostHog: `gtm.py metric add creative:<batch>:<id>:hook_rate 0.31 --source "tiktok analytics"`
(and click-through, cost per first step). Close the bet on its check date. Winning patterns go into
the brief template for the next batch; a pattern becomes a learning only through
`gtm.py learnings`.

## Guardrails

- **Disclosure.** AI-generated presenters, voices and synthetic testimonials are labelled as such,
  in the asset and in the post, and use each platform's AI label where one exists. Paid or gifted
  creator content carries the creator's disclosure (FTC; `../gtm/references/compliance.md`).
- **Likeness.** No real person's face, voice or name without their written permission on file.
- **Claims.** One claim per asset, from the ledger, with its qualifier. No invented results,
  reviews, customers or numbers.
- **Regulated products** (`profile.regulated` is heavy): a human reviews every asset before it's
  used anywhere, including internally.
- **Nothing publishes from here.** Posting is a human's job, or `../paid` within its caps.
