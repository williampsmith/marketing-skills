---
name: cro
description: Raise the share of visitors who take the first step (signup, trial, demo request, add to cart) on the product's marketing pages and forms. Finds which page, step and traffic source leaks from PostHog funnels and recordings, reviews the page against a fixed checklist (message match, one primary action, proof from the claims ledger, objections, form friction, speed, mobile), and ships each change as a PR behind a feature flag with a bet opened first. Use when gtm's focus is the conversion track's first_step rung, when the page_cro tactic is chosen, or when the user asks for CRO, landing page or pricing page improvements, "why aren't visitors signing up", form drop-off, or popups. For what happens after signup see activation; for test design and sizing see experiments; for the copy itself see writing.
---

# cro

This skill works the `first_step` rung of the conversion track: visit → the motion's first step
(`signup` for self-serve, `trial_or_demo` for sales-assisted, `meeting` for enterprise; see
`../gtm/references/funnel-templates.json`). The fix is almost always one of three things: the
page doesn't answer what the visitor came for, the action is unclear or costly, or the visitor
doesn't believe it. Find which one with data before changing anything.

`<state>` is the store root printed by `gtm.py where`. Run scripts from the **product repo root**
by absolute path. Changes ship as PRs in the product repo; copy passes `../writing`; every product
claim on the page is an OK row in `<state>/claims.md`.

## 1. Find the leak

From PostHog (`../measurement` connected it):

1. The funnel from the landing page to the first step, broken down by `$initial_referring_domain`
   or UTM source and by device. A rate that is fine overall can hide one source converting at a
   third of the rest (often paid or AI referrers landing on the wrong page).
2. The top entry pages by sessions that reach the first step, against sessions that leave.
3. For the worst page, 10-20 session recordings of visitors who left: where they stopped
   scrolling, what they clicked that did nothing, form fields where they quit.
4. The form itself: field-level drop-off if the form events exist (if not, a tracking PR first,
   through `../measurement`).

Write the finding in `plan.md` as one sentence: "<page> converts <x>% for <source>, <y>% elsewhere;
recordings show <behaviour>."

## 2. Review the page

Use `references/page-review.md`. In short:

| check | passes when |
|---|---|
| message match | the headline answers what the source promised (the ad, the AI answer, the search query) |
| one primary action | one button label and colour for the first step above the fold; secondary links are quieter |
| proof | numbers, logos and quotes come from claims.md or permission-granted customers, with qualifiers |
| objections | the top 3 objections in product-context.md are answered on the page, near the action |
| friction | only the fields the first step truly needs; no account creation before value where avoidable |
| speed and mobile | LCP under ~2.5 s on mobile, tap targets usable, no layout shift under the button |
| trust | pricing or "free" terms stated plainly; no surprise on the next screen |

## 3. Change it, measured

1. Pick one change that targets the finding. Several unrelated edits at once can't be judged.
2. Size it: `python3 ../experiments/scripts/stats.py days --baseline <rate> --mde <lift> --daily
   <visitors>`. If `run_it` is true, it's an A/B test behind a PostHog flag. If not, ship to half
   the pages of a set (holdout), in waves (staggered), or as a before/after bet that is reported
   as directional. `../experiments` has the details.
3. Open the bet first (`gtm.py bet open … --track conversion --channel on_site --tactic page_cro`),
   with the first-step metric as `--metric`.
4. Open the PR: variant behind the flag, control unchanged, the same events fired in both. Link the
   bet id in the PR description.
5. Close on the check date through `../experiments`.

## Popups and overlays

Only with a frequency cap (once per visitor per few weeks), a visible close control, no cover on
mobile before the visitor has read anything, and an offer that is worth the interruption. Treat a
popup as its own bet with a guardrail on bounce rate.

## Never

- Fake scarcity or urgency (invented countdowns, "only 3 left" that isn't true).
- Confirmshaming ("No thanks, I don't like saving money").
- Pre-checked consent boxes, hidden opt-outs, or terms changed below the button.
- Proof that isn't in the claims ledger, or reviews and logos without permission.
- Changes to price or plans: those go to the human (`../activation`, `../experiments`).
