---
name: activation
description: Get new signups to the product's first value moment faster and turn active users into paying ones, by changing the product itself in its repo. Defines the activation event with the team, finds where people drop between the first step and activation (and between activation and paid) in PostHog, and ships changes to signup, onboarding, empty states, checklists, contextual prompts and upgrade moments as PRs behind feature flags, each with a bet. Use when gtm's focus is the conversion track's activating or paying rung, when the signup_flow, onboarding_change or paywall_change tactic is chosen, or when the user asks about activation, onboarding, time to value, trial conversion, upgrade prompts or paywalls. For marketing pages before signup see cro; for test design see experiments; for pricing decisions the human decides.
---

# activation

This skill works two rungs of the conversion track: `activating` (first step → `activated`) and
`paying` (activated → paid, or the motion's equivalents in
`../gtm/references/funnel-templates.json`). It works where the operator has an advantage: inside
the product repo, where signup, onboarding and the upgrade path are code.

`<state>` is the store root printed by `gtm.py where`. Run scripts from the **product repo root**
by absolute path. Every change is a PR a human merges, behind a feature flag, with a bet opened
first. In-product copy passes `../writing`.

## 1. Define activation (once, with the team)

Activation is the first moment a new user gets the value they signed up for, measured as one
event: for a redaction tool, "first redacted export"; for an analytics tool, "first dashboard with
real data". Pick it with the human:

1. List 3-5 candidate events from the product's code and PostHog.
2. For each, compare 30-day retention of users who did it in their first week versus those who
   didn't. The best candidate separates the two groups most and happens early.
3. Name it in `gtm.json` `measurement.stage_events.activated` (through `../measurement`) and in
   product-context.md. Changing it later resets the stage's history, so get agreement first.

## 2. Find the drop-off

From PostHog:

- The funnel from the first step to activation, step by step through the onboarding screens, by
  signup source and plan.
- Time to activation for those who make it: the median and the slowest quarter.
- Recordings of 10-20 users who signed up and never activated.
- For `paying`: where activated users meet the upgrade prompt or the paywall, and what they do
  next.

## 3. Change the product

Typical changes, smallest first (`references/onboarding.md` has patterns):

| leak | change |
|---|---|
| signup asks too much | defer fields until they're needed; social or SSO sign-in if the audience uses it |
| users land on an empty screen | a sample project, a template, or one clear first action |
| onboarding is a tour | replace it with doing the first task, guided |
| users stall mid-setup | a short checklist that ends at the activation event; save progress |
| upgrade prompt comes on day 7 regardless | show it when a user hits a limit while getting value |
| paywall blocks before value | let users see the result first, then ask |

For each change: open the bet (`--track conversion --channel on_site --tactic signup_flow |
onboarding_change | paywall_change`, `--metric stage:activated` or `stage:paid`), size it with
`../experiments/scripts/stats.py days`, ship the PR behind a flag, close through
`../experiments`.

If `../lifecycle` is installed, emails that bring stalled signups back belong there; coordinate so
one bet doesn't hide the other's effect.

## Ask the human first

- Price, plans, trial length, or what a plan includes.
- Anything that deletes, hides or migrates a user's data.
- Removing a feature from a plan or adding a new limit.
- Changes to billing, cancellation or consent flows.

The agent may draft a proposal with the evidence and the expected effect. It doesn't open the PR
until the human says yes.

## Never

- Dark patterns: hidden cancellation, auto-enrolment in paid plans, fake countdowns on trials.
- Counting a bet as won on activation if paid conversion or retention dropped (guardrail metrics).
- Shipping onboarding changes without the activation event firing in both arms.
