# Answer page template (also the base for integration and use-case pages)

Adapt the markup to the site's framework and components. The structure and order are what matter.

```markdown
---
title: <the intent as a question, ≤ 60 chars for <title>>
slug: <descriptive-kebab-slug>
description: <quick answer compressed to ≤ 155 chars>
published: 2026-10-31
updated: 2026-10-31
author: <real person>          # with an about page; avoid "Team"
intent: <one-line intent>
prompts: [<panel prompt ids this page targets>]
named_idea: <the frame>
---

# <Question in the reader's words>

**Quick answer** · Updated <Month D, YYYY>
<2–5 sentences. Direct answer first, then the key condition or number. Must stand alone if quoted.
No product name unless the question is about the product.>

<One short paragraph introducing the named idea: what it is and why it matters.>

## <Sub-question 1 from fan-out / PAA>
<One-line answer first.> Then the explanation, with sources inline [1].

## <Sub-question 2>
…

## <Decision table or checklist>
| situation | do this | why |
|---|---|---|

## Common mistakes
- <failure mode> — <consequence> — <fix>

## FAQ
**<PAA question>?** <1–3 sentences.>
**<…>?** <…>

---

## From the publisher
<Who we are, in one line. Where <product> fits this problem, using claims from the ledger with
their qualifiers. What it does not do. One CTA.>

## Sources
1. <Publisher — Title — URL — accessed date>
```

## Page types

| type | H1 pattern | must include |
|---|---|---|
| How-to / safest way | "How to <job> without <risk>" | steps, failure modes, verification step |
| Explainer | "What is <concept>?" / "Why <thing> fails" | definition, example, named idea |
| Comparison | "<A> vs <B> for <audience>" | fair table checked against both sides' current docs, "choose A if / choose B if" |
| Alternatives | "Alternatives to <X> for <constraint>" | criteria first, then options *including* ones that aren't you |
| Problem/incident | "<Thing that went wrong>: what happened and how to avoid it" | dated facts, primary sources, prevention checklist |

## Style

- Lead every section with its answer. Engines quote first sentences.
- Concrete beats clever: numbers, versions, dates, named standards.
- Use short paragraphs (≤ 4 lines). Put anything list-shaped in a list or table.
- Write the publisher section as an honest note, not an ad. It should still read well to someone
  who decides not to buy.
- Never write "best" about yourself. In a comparison, say who each option is for.
