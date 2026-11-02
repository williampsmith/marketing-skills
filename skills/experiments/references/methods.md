# Experiment methods

How each method in `../SKILL.md` works, when it breaks, and how it closes in `gtm.py`.

## Sizing

`stats.py size --baseline B --mde M` gives visitors per arm for a two-sided test at 95% confidence
and 80% power. `stats.py days … --daily D --arms 2` divides by the traffic and rounds up to whole
weeks. With more than two arms it splits alpha across the comparisons with control (Bonferroni), so
each arm needs more visitors. It refuses a lift the rate can't reach (baseline × (1 + mde) ≥ 1).
Rules of thumb:

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
- Primary metric: the bet's `--metric` (a `rate:<stage>` for conversion), counted per exposed
  user. Guardrails: errors, the next funnel stage, refunds or cancellations where relevant.
- Check date: the expected launch date plus `stats.py days`. The bet stays open until exposures
  reach the planned `per_arm`.
- Sample ratio mismatch: test the split with `stats.py srm --a N --b N [--split 0.5]`, a chi-square
  test that flags `mismatch` at p < 0.001. Small gaps are normal noise (1,020 vs 980 has p ≈ 0.37);
  4,000 vs 4,600 is a bug (caching, bots, a redirect in one arm). On a mismatch, don't analyse it:
  fix the cause, close the bet with `--force --void "SRM: <cause>"` and open a new one.
- Close: `gtm.py bet close <id> --a N:X --b N:X --min-n <per_arm> --source "PostHog experiment <name>"`.
  The result compares the arms (variant minus control). Small counts or fewer than `--min-n` per
  arm read as inconclusive.
- Stopped on a guardrail breach: `gtm.py bet close <id> --force --void "<reason>"`. A void bet has
  no result and isn't counted in fit or learnings.

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

- The comparison is variant against control in the same window, never against the baseline the
  bet was opened with.
- p < 0.05 with the predicted sign: won. Ship it.
- p < 0.05, wrong sign: lost. Revert, and write down what you believed that wasn't true.
- p ≥ 0.05: inconclusive. Not a loss. Keep the simpler version and move on; don't extend the test
  to chase significance.
- The 95% interval (`stats.py test`) says how big the effect might really be. A "win" whose
  interval runs from +0.1% to +4% is a small, uncertain win.
