# Tracks, rungs and focus

`gtm.py tracks` shows every track's rungs with the numbers behind them; `gtm.py focus` shows which
track gets the work and why. This file explains the rules both follow. The definitions live in
`scripts/gtm.py` (`DEFAULT_TRACK_RUNGS`) and `funnel-templates.json`; per-product overrides go in
`<state>/gtm.json`.

## Tracks

A track is a part of the funnel with a ladder of pass/fail rungs. A rung is met when its metric,
recorded with `gtm.py metric add` (by the skills or the measurement setup), passes its threshold
and is recent enough. A track works on its first unmet rung.

| track | rungs | metric behind each rung (default threshold) |
|---|---|---|
| measurement | instrumented → attributed → funnel_visible | `tracking_ok` ≥ 1 (3 days); `source_capture_rate` ≥ 0.8 (14 days); every funnel stage has a count from the last 7 days |
| discoverability | reachable → known → associated → preferred | the access check; brand mention ≥ 0.8; category, problem and jobs mention ≥ 0.3; comparison mention ≥ 0.5 with average rank ≤ 2 (`ladder` in gtm.json) |
| demand | indexed → ranking → visited → pipeline | `indexed_ratio` ≥ 0.9; `query_top10_share` ≥ 0.3; first funnel stage ≥ a floor you set; `leads_28d` ≥ a floor you set |
| conversion | first_step → activating → paying | conversion between the template's stages, each ≥ its floor |
| retention | retained → expanding → referring | `churn_rate_monthly` ≤ 0.05; `nrr` ≥ 1.0; `referral_share` ≥ 0.1 |
| paid (off by default) | tracked → profitable → scaling | `paid_conversions_tracked` ≥ 1; `cac_payback_months` ≤ 12; `paid_scaling_ok` ≥ 1 |

A rung whose threshold is product-specific (`visited`, `pipeline`) reports "set a floor" until you
set it, e.g. `"tracks": {"demand": {"rungs": {"visited": {"value": 2000}}}}`. Override any default the
same way. Turn a track on or off with `"tracks": {"paid": {"enabled": true}}`.

## The funnel template

The GTM profile's `motion` picks a template from `funnel-templates.json`: its stages, the floor
conversion rate between each pair, and which stages the conversion rungs point at. Self-serve
measures signups and activation; enterprise measures engaged target accounts, meetings and
opportunities. Each stage's count is a 28-day total recorded as `stage:<id>`.

Floors are benchmark defaults. After 30 days of the product's own data, `strategy_review` proposes
replacing them with the product's baseline (`"floors": {"activated": 0.25}` in gtm.json).
`floors.min_sample` (default 100) is the smallest denominator a conversion rate is judged on.

## Choosing the focus

`gtm.py focus` applies these rules in order:

1. **Alerts preempt.** Access regressions, lost prompts, escalations, a paused program, and a failed
   discoverability `reachable` or `known` rung (except `reachable` in prelaunch) are handled on the
   tick they appear, whatever the focus.
2. **Prelaunch** works on discoverability, with measurement as the secondary track.
3. **Measurement gates the funnel.** Once launched, while measurement is below `funnel_visible`, it
   is the focus: nothing downstream can be judged.
4. **Bottleneck.** Each stage with enough data scores `rate / floor`. The lowest-scoring stage's
   track is the focus. If the first stage has fewer entrants than `min_sample`, reach is the
   bottleneck: the focus is discoverability or demand, whichever has made less progress
   (discoverability on a tie).
5. **Fit.** A track whose eligible channels' fit sums below 0.5 can't be the focus; the next stage
   is tried. Measurement and conversion always qualify (they work on the product's own site).
6. **Hold.** A focus holds for 30 days, until its track is complete, or until another stage falls
   below half its floor. The stage changing (prelaunch to launched) also re-decides.

## Shares and the standing priority

Work sessions follow shares: the focus gets at least 60%, the secondary 25%, exploration the rest.
`gtm.py next` turns the shares into slots by giving each slot to the category furthest behind its
share, using the counts recorded with `record work_session --mix`.

Discoverability is the default secondary while its `preferred` rung is unmet and AI search is an
eligible channel, because buyers in every motion now shortlist with AI assistants. Once `preferred`
is met, it drops to sensors and regressions, and the secondary becomes the next-weakest stage's
track. When discoverability is itself the focus, the secondary is the next-weakest stage's track.

## Tactics

Within a track, `gtm.py next` ranks tactics (`channel-fit.json`): those that work the current rung
first, then by Thompson sampling. Each tactic starts from its channel's fit as a prior worth three
bets; every closed bet on that tactic moves it (won +1, lost 0, inconclusive half each). The sample
keeps trying plausible tactics while favouring what has worked for this product.
