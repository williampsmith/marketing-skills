# Experiment methods

How each method in `../SKILL.md` works, when it breaks, and how it closes in `gtm.py`.

## Sizing

`stats.py size --baseline B --mde M` gives visitors per arm for a two-sided test at 95% confidence
and 80% power. `stats.py days … --daily D --arms 2` divides by the traffic. Rules of thumb:

| baseline rate | relative lift | per arm |
|---|---|---|
| 5% | +20% | ~8,200 |
| 5% | +50% | ~1,500 |
| 2% | +20% | ~21,000 |
| 30% (activation) | +10% | ~3,800 |

Low baselines and small lifts need far more traffic than most early products have. When
`run_it` is false, change the plan, not the threshold.

## A/B (`--method ab`)

- Assignment by a PostHog feature flag on a stable user id (or the anonymous id for logged-out
  pages). Exposure is the first time the flagged code runs, not the page view before it.
- Primary metric: the bet's `--metric`, counted per exposed user. Guardrails: errors, the next
  funnel stage, refunds or cancellations where relevant.
- Sample ratio mismatch: with a 50/50 split, arms more than about 2-3% apart after a few thousand
  users usually mean a bug (caching, bots, a redirect in one arm). Don't analyse it; fix and restart.
- Close: `gtm.py bet close <id> --a N:X --b N:X --source "PostHog experiment <name>"`.

## Holdout (`--method holdout`)

For changes that can't be split per user: AI visibility (pages for half the prompt topics), SEO
(half of a page set), outreach (half the target list), regions.

- Pick the halves before the change, at random or by alternating a sorted list. Never hand-pick
  the treated half.
- The bet needs `--control-metric` and `--control-baseline` (measured now). gtm.py subtracts the
  control's change from the treated change.
- Close: `gtm.py bet close <id>` once both metrics have values dated on or after the check date.

## Staggered rollout (`--method staggered`)

Ship to one wave of units, wait, compare with the waves not yet changed, then ship the next wave.
Same bet shape as a holdout: the control metric is the not-yet-changed waves. The last wave has no
control, so judge on the earlier waves.

## Before/after (`--method before_after`)

The metric before versus after, with no control. Seasonality, launches and campaigns all move
it, so gtm.py marks every result "directional: no control" and it never becomes a learning on its
own. Use it only when nothing else fits, and say so.

## Reading a result

- p < 0.05 with the predicted sign: won. Ship it.
- p < 0.05, wrong sign: lost. Revert, and write down what you believed that wasn't true.
- p ≥ 0.05: inconclusive. Not a loss. Keep the simpler version and move on; don't extend the test
  to chase significance.
- The 95% interval (`stats.py test`) says how big the effect might really be. A "win" whose
  interval runs from +0.1% to +4% is a small, uncertain win.
