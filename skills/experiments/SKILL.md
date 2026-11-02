---
name: experiments
description: Design, run and close experiments so every conversion and growth change produces a result the operator can trust. Picks the method from the traffic the change will see (A/B test, holdout, staggered rollout, or a before/after read that is only directional), sizes and times it with stats.py, fixes the primary metric before the start, wires PostHog feature flags and experiments, checks sample ratio and guardrail metrics, and closes the gtm bet from the real counts. Use when a work session opens a bet on the conversion or activation track, when the user asks for an A/B test, split test, price test, "is this change working", "how long should this test run", or sample size; and when a bet's check date arrives. cro and activation decide what to change; measurement owns the events; gtm owns the bet ledger.
---

# experiments

Every change the operator ships is a bet (`gtm.py bet open`). This skill makes the bet answerable:
the right method for the traffic, one metric chosen before the start, and a close that reads real
counts instead of an impression. A test that can't reach an answer in reasonable time is not run as
an A/B test at all.

`<state>` is the store root printed by `gtm.py where`. Run every script from the **product repo
root**, calling the plugin's scripts by absolute path (`scripts/stats.py` is this skill's folder,
`../gtm/scripts/gtm.py` the state engine). Method details and worked examples:
`references/methods.md`.

## 1. Pick the method from the traffic

Start from the rate the change should move and the visitors it will see per day (from PostHog,
`../measurement`):

```
python3 scripts/stats.py days --baseline 0.03 --mde 0.20 --daily 400
```

`--mde` is the relative lift worth detecting (0.20 = +20%). Read `run_it`:

| situation | method (`--method` on the bet) |
|---|---|
| `run_it: true` (under 8 weeks) and users can be split by a flag | `ab`: A/B test behind a PostHog feature flag |
| too slow, but the unit can be split (pages, prompt topics, accounts, regions) | `holdout`: change half, keep half as the control |
| many similar units, can't split users | `staggered`: roll out in waves, compare waves still waiting |
| none of the above | `before_after`: directional only, said so in every report |

Never run an underpowered A/B test hoping for luck. A bigger change, a higher-traffic page, or a
holdout gives a usable answer sooner. For AI visibility, the holdout is half the prompt topics:
pages for one half, the other half untouched (`--control-metric ai:mention:<bucket>`).

## 2. Fix the metric before the start

Open the bet before any code ships (gtm work_session step 3):

```
gtm.py bet open --id 2026-11-20-pricing-cta --track conversion --channel on_site --tactic page_cro \
  --hypothesis "One plan-picker CTA lifts visit→signup" --metric stage:signup --baseline 0.031 \
  --expected 0.037 --method ab --check 2026-12-18
```

- One primary metric, written in the bet. It is the only one that decides won or lost.
- Name 1-2 guardrail metrics in the hypothesis (e.g. activation rate, refunds, page errors). A
  win that breaks a guardrail is reported as a loss to investigate, never shipped silently.
- The check date comes from `stats.py days`, not from when the result looks good.

## 3. Wire the flag (A/B only)

- A human creates the feature flag and the experiment in the PostHog UI, with the primary metric
  set to the bet's event. If the agent is asked to use PostHog's API for this, verify the endpoint
  and the key's scope first; the measurement key is read-only by design.
- The agent writes the code path behind the flag in a PR: the variant reads the flag, the control
  is the current behaviour, both fire the same events. A human merges.
- Copy in the variant passes `../writing`. Changes to price or plans need the human's yes before
  the PR (see `../activation`).

## 4. While it runs

- **No peeking.** Don't stop early on a good or bad day. The one exception is a guardrail breach
  (errors, a refund spike): stop, revert, and close the bet `lost` with `--decision "stopped: <why>"`.
- **Sample ratio check** after the first few days: arms should be close to the planned split.
  A 50/50 test at 4,000 vs 4,600 is a broken assignment, not a result. Fix the flag and restart
  the clock (a new bet id).
- Nothing else changes on the tested page while the test runs. Note any launches in plan.md.

## 5. Close it

On the check date (`bet_close` in the gtm tick):

1. Read the counts per arm from the PostHog experiment: visitors (exposed) and conversions on the
   primary metric.
2. Explain the numbers: `python3 scripts/stats.py test --a 4000:124 --b 4000:150` (rates, lift,
   p-value, 95% interval).
3. Close: `gtm.py bet close <id> --a 4000:124 --b 4000:150 --source "PostHog experiment <name>"`.
   gtm.py judges p < 0.05 as won or lost and fewer than 100 per arm as inconclusive.
4. Holdout bets close from the metrics store (`gtm.py bet close <id>` once both the metric and the
   control are measured after the check date). `stats.py holdout` shows the arithmetic.
5. Ship the winner (remove the flag in a PR) or revert the loser. Inconclusive means keep the
   control unless the variant is simpler.

Learnings come only through `gtm.py learnings`: a strong-method result the human accepts.

## Don't

- Don't test several changes on one page at once unless it is a planned multi-variant test sized
  for it.
- Don't report a before/after result as proof. Say "directional".
- Don't change price, plans, billing or anyone's data inside a test without the human's approval.
