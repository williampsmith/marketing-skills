# Channel fit

`gtm.py fit` scores every channel from 0 to 1 for this product. Channels below 0.25 (gtm.json
`fit.min`) are ineligible: no improvement work and no tactics. A track can't become the focus when
the fit of its eligible channels sums below 0.5 (see `tracks.md`).
The numbers live in `channel-fit.json`; this file explains them.

```
fit = matrix[motion][channel] × attention × economics × cycle × compliance
```

| factor | source | effect |
|---|---|---|
| matrix | `channel-fit.json`, by the profile's `motion` | the default for this kind of business |
| attention | `profile.attention[channel]` in gtm.json, measured by customer research | 1.0 until measured; low when the buyers aren't on that channel |
| economics | `min(1, acv × 0.8 margin × 18 months / 12 / cost per customer)` | rules out paid channels the deal size can't pay back; organic channels cost effort, not media, so their factor is 1 |
| cycle | channels marked `fast_feedback`, when `cycle_days` > 90 | `max(0.4, 90 / cycle_days)`: fast channels lose value when results land months later |
| compliance | `compliance` in `channel-fit.json`, by `profile.regulated` | e.g. creators × 0.4 for a heavily regulated product |

Unknown deal size leaves economics at 1 and the digest says so; confirm the profile early.

## Learning from the product

The matrix value is a prior worth three bets (`prior_weight_bets`). Each closed bet in a channel
moves its fit toward the result: won counts 1, lost 0, inconclusive 0.5. After three or four bets the
product's own evidence outweighs the default. A bet closed with `--cost-per-customer` replaces the
channel's cost floor with the measured median.

## Overrides

`"fit": {"overrides": {"short_video": "include", "pr": "exclude", "linkedin_organic": 0.7}}` in
gtm.json. A number replaces the computed fit; `include` and `exclude` force eligibility. Propose
overrides in the digest with a reason; apply them after the human agrees. The digest lists the
channels not being pursued once a month so a human can disagree.

## The default matrix (checked 2026-11-01)

| channel | self_serve | sales_assisted | enterprise | consumer_app | ecommerce | oss_devtool |
|---|---|---|---|---|---|---|
| AI search and comparison pages | 0.8 | 0.9 | 0.9 | 0.6 | 0.6 | 0.9 |
| SEO content | 0.8 | 0.7 | 0.5 | 0.5 | 0.8 | 0.8 |
| Review sites and communities | 0.6 | 0.8 | 0.7 | 0.4 | 0.6 | 0.8 |
| Outbound to named accounts | 0.1 | 0.7 | 0.9 | 0 | 0 | 0.3 |
| LinkedIn organic | 0.4 | 0.7 | 0.8 | 0.1 | 0.1 | 0.4 |
| Short-form video and UGC | 0.5 | 0.2 | 0.05 | 0.9 | 0.9 | 0.2 |
| Long-form video | 0.6 | 0.6 | 0.5 | 0.5 | 0.5 | 0.7 |
| Creators and influencers | 0.5 | 0.3 | 0.1 | 0.8 | 0.8 | 0.5 |
| PR and press | 0.4 | 0.5 | 0.6 | 0.5 | 0.4 | 0.4 |
| Partnerships and marketplaces | 0.6 | 0.7 | 0.7 | 0.3 | 0.4 | 0.8 |
| Paid search | 0.6 | 0.6 | 0.3 | 0.4 | 0.8 | 0.3 |
| Paid social | 0.5 | 0.4 | 0.3 | 0.8 | 0.8 | 0.2 |
| Lifecycle email | 0.9 | 0.7 | 0.5 | 0.8 | 0.9 | 0.6 |
| Referral program | 0.6 | 0.4 | 0.2 | 0.7 | 0.7 | 0.4 |
| The product's own site and app | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

Default cost per customer: outbound $1,500, PR $1,000, paid search $400, paid social $300,
creators $200, everything else 0 (effort only).

What the values rest on (mostly vendor-reported surveys; directional):

- **AI search is high in every B2B motion.** G2's 2026 survey of software buyers reports that half
  start vendor research in an AI chatbot rather than a search engine, and that most changed their
  shortlist because of what it surfaced. Forrester's 2026 buyer survey reports generative AI use in
  nearly every recent business purchase.
- **Peers outrank social for trust.** A 2026 survey of US decision makers found most had used social
  media to research a purchase, but far fewer trusted it than trusted peer opinions. So review sites
  and communities score above social feeds for B2B, and short-form video counts for awareness.
- **Cost per customer by channel has no reliable benchmark.** Published figures disagree several-fold,
  so the floors are conservative and measured costs replace them.

## Tactics

Each channel lists the tactics it is worked through, with the skill that does the work and the
tracks it moves. `gtm.py next` offers a tactic only on its tracks and only for eligible channels.
Add a tactic by adding it to `channel-fit.json` with a `skill`, a `label` and `tracks`.
