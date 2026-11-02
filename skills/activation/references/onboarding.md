# Onboarding and upgrade patterns

Patterns that usually shorten the path to the first value moment. Each one is a hypothesis for a
bet, not a rule; test it against this product's activation event.

## Before the first value moment

- **Ask later.** Name, company size, role and phone can wait until the user has seen value. Ask
  only what the first task needs.
- **Start with something.** A sample file, a template, demo data, or an import from a tool the user
  already has beats a blank screen. Label sample content clearly and make it easy to remove.
- **Do, don't tour.** A tooltip tour explains; a guided first task teaches. End the guidance at the
  activation event, then get out of the way.
- **One next step.** Every empty state names one action and why it matters.
- **Save progress.** A user who leaves mid-setup returns to where they left, not to the start.

## Checklists

- 3-5 items, ending at the activation event. Each item is a real action in the product.
- Show progress; hide the checklist once it's done or dismissed.
- Track each item as an event, so the drop-off between items is visible in the funnel.

## Contextual prompts

- Prompt at the moment the feature helps ("You redacted 20 pages; save this as a template?").
- One prompt at a time, dismissible, not shown again once dismissed.

## Upgrade moments

- Tie the prompt to value: the user hit a limit while doing something useful, or asked for a
  feature in a higher plan.
- Say what they get and what it costs, on the prompt itself.
- Let them finish what they were doing first when possible. A paywall in the middle of a task
  feels like a trap.
- Trials: remind before the end with what they'll lose, not with a countdown alone.

## Measuring

- Primary metric: the conversion into the next stage, `rate:<rungs.activating>` or
  `rate:<rungs.paying>` from the motion's template (e.g. `rate:activated`), for the cohort that saw
  the change.
- Guardrails: retention after 30 days, support tickets, refunds or cancellations.
- Cohorts by signup week, so a change isn't credited for a busy week.
