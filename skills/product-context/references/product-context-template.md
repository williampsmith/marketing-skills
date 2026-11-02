# <state>/product-context.md template

Copy this into `<state>/product-context.md`. Replace every `<…>`. Mark anything you cannot source
as `unknown — <question to ask>`.

```markdown
# Product context — <product>

Last confirmed by <name> on <date> · claims ledger verified <date> against <commit>

## GTM profile
| field | value | source |
|---|---|---|
| motion | <self_serve · sales_assisted · enterprise · consumer_app · ecommerce · oss_devtool> | <file or person> |
| acv_usd | <number, or LTV for consumer> | |
| buyer | <role, seniority, team> | |
| user | <role> | |
| buying_committee | <1 · 2-4 · 5+> | |
| cycle_days | <days from first touch to paid> | |
| attention | unmeasured (customer-research not run yet) | |
| regulated | <none · light · heavy> (<which rules>) | |
| geo | <markets> | |
| stage | <prelaunch · launched> (gtm.json `stage`) | |

## Positioning
- **One-liner:** <what it is, for whom, in one sentence>
- **Category:** <the shelf buyers look on>
- **Problem:** <what goes wrong without it, in the buyer's terms>
- **Alternatives:** <competitor A>, <competitor B>, <the manual workaround>, do nothing
- **Differentiators:**
  | differentiator | claims-ledger row | qualifier |
  |---|---|---|
  | <…> | <row text or id> | <required qualifier> |

## ICP
<who gets value fastest: company type, size, trigger events>

## Anti-ICP
<who should not buy, and why; outreach and ads exclude them>

## Objections
| objection (buyer's words) | honest answer | proof |
|---|---|---|

## Switching forces
- **Push** (away from today's approach): <…>
- **Pull** (toward us): <…>
- **Habit** (what keeps them stuck): <…>
- **Anxiety** (what scares them about switching): <…>

## Customer language
| phrase (verbatim) | context | source |
|---|---|---|

## Brand voice
| attribute | do | don't | a real line |
|---|---|---|---|

## Proof points
- <proof> — <claims-ledger row or permission-granted quote with source>

## Learnings
| date | learning | evidence (bet ids) | status |
|---|---|---|---|

## Changelog
- <date> — <what changed and why>
```
