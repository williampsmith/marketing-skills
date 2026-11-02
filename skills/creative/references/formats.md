# Formats by channel

Formats belong to channels, and fit decides channels. Pick the format from the channel the bet is
on; don't pick a channel to suit a format.

| channel (`channel-fit.json`) | formats that fit | length and shape | what makes it work |
|---|---|---|---|
| `short_video` | UGC-style hook, problem-solution clip, 3-step demo | 9:16, 15-45 s; the hook in the first 2 s | a recognisable moment of the problem, then the product resolving it on screen |
| `long_video` | tutorial for a job buyers search for, full demo, comparison walkthrough | 16:9, 3-12 min, chapters | answers one searchable question end to end; real screen recording |
| `linkedin_organic` | document (carousel) post, workflow diagram, founder clip | 6-10 slides, 1080×1350; clips under 90 s with captions | one idea per post, a useful takeaway even without the product |
| `paid_social` | the short-video and static formats above, cut per placement | per platform spec | the hook and the claim survive with the sound off |
| `paid_search` | none (text ads are written in `../paid`) | | |
| `review_communities` | screenshots and short GIFs attached to an honest answer | | shows the exact steps the thread asked about |
| `creators` | the creator's own format, briefed with one claim and the disclosure terms | | the creator's voice, not a script read aloud |

## By sales motion

| motion | lead with | avoid |
|---|---|---|
| consumer_app, ecommerce | UGC hooks, before/after, product-in-hand clips | long explainers before the hook |
| self_serve | 30-60 s demos of the first value moment, tutorial videos | abstract brand pieces |
| sales_assisted | demo videos, LinkedIn documents, customer-problem walkthroughs | trend-chasing UGC |
| enterprise | 2-minute demos, architecture and workflow diagrams, LinkedIn documents for the buying committee, security and compliance explainers | TikTok-style UGC (fit rules it out; say so and offer these) |
| oss_devtool | terminal recordings, README GIFs, tutorials | presenter-led ads |

## Variant discipline

Change one thing per variant (hook, first frame, claim framing, call to action) so a win says which
change won. Keep 3-8 variants per batch; more splits the audience too thin to learn anything.

## Specs to check before generating (verify on the platform; they change)

- 9:16 at 1080×1920 for TikTok, Reels and Shorts; safe zones keep text away from the bottom and
  right edges.
- Captions burned in for short video (most views are muted).
- LinkedIn documents as PDF, readable on a phone at 100%.
