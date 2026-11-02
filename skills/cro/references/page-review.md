# Page review checklist

Run this on one page at a time, with the leak from SKILL.md step 1 in mind. Note each failing
item with the evidence (a recording, a funnel number, a screenshot) in `plan.md`. Fix the item
closest to the leak first.

## Above the fold (first screen on a phone)

- [ ] The headline says what the product does for this visitor, in their words
      (product-context.md customer language). Not a slogan.
- [ ] It matches the promise of the source that sent them: the ad text, the AI answer, the query.
      Check the top 3 sources separately.
- [ ] One primary action, labelled with what happens next ("Start free trial", "Book a 20-minute
      demo"), not "Submit" or "Learn more".
- [ ] What it costs, or that it's free, is visible or one tap away.

## Belief

- [ ] Proof near the action: a specific result, a recognisable customer, a review count. Every
      item maps to a claims.md row or a permission-granted quote.
- [ ] The top objections from product-context.md are answered on the page (security, switching
      effort, price, "does it work with X").
- [ ] Nothing contradicts the product: screenshots are current, limits are stated.

## The action

- [ ] The form asks only what the first step needs. Every extra field has a reason someone can
      name.
- [ ] Errors say what's wrong and keep what was typed.
- [ ] After submitting, the next screen says what happens and when.
- [ ] Sales-assisted and enterprise: a calendar link or a clear response time beats "we'll be in
      touch".

## Mechanics

- [ ] Mobile LCP under ~2.5 s (PageSpeed Insights or the site's own monitoring).
- [ ] No layout shift moves the button as the page loads.
- [ ] Tap targets at least ~44 px; the button is reachable with one thumb.
- [ ] The first-step event fires once per completion (check in PostHog's live events).

## Common findings and the change they suggest

| finding | change to test |
|---|---|
| AI or search visitors land on the homepage but asked a specific question | a landing page that answers that question first (`../content`), linked from where they arrive |
| visitors open pricing, then leave | state the free tier or trial terms beside the button; answer the top pricing objection |
| form drop-off at one field | remove or defer the field |
| recordings show rage clicks on non-links | make that element a link to what visitors expect |
| mobile converts at half of desktop | fix speed and the first screen on mobile before any copy test |
