# <state>/plan.md template

`plan.md` is the program's narrative: what we're trying to do, where we're focused and why, what's
next. It is not the record of experiments. Bets are opened and closed with `gtm.py bet open` and
`gtm.py bet close`; the ledger in `<state>/experiments.jsonl` is the source of truth, and the table
below mirrors `gtm.py bet list --status open`. Learnings live in `<state>/product-context.md`, added
only after a human accepts them (`gtm.py learnings --accept <bet id>`).

```markdown
# GTM plan — <product>

**Goal**: <one measurable line, with a date>
**Stage**: launched | prelaunch (launch target: <date>)
**Focus**: <track> on rung `<rung>`, since <date>. Why: <reason from `gtm.py focus`>
**Secondary**: <track> (<standing priority | next weakest stage>)
**Not pursuing**: <channels `gtm.py fit` ruled out, with the reason, until the next fit review>
**Budget**: $<cap>/month (spent this month: see digest)

## Active bets (mirror of `gtm.py bet list --status open`)
| id | track · tactic | hypothesis | metric: baseline → expected | method | checks on |
|---|---|---|---|---|---|
| 2026-11-12-access | discoverability · access_fix | Letting search bots in makes the site citable | ai:citation 0 → 0.1 | before_after | 2026-12-03 |
| 2026-11-12-vs-acme | discoverability · comparison_page | A sourced comparison wins "vs Acme" prompts | ai:mention:comparison 0.1 → 0.3 (control ai:mention:category) | holdout | 2026-12-10 |

## Backlog (ranked)
1. <action> — track/rung — impact · confidence · effort — source (audit run, probe, funnel stage, target)
2. …

## Decisions waiting on a human
- <proposal, e.g. raise budget to $40 to sample key prompts 3×; enable the paid track> — proposed <date>

## Learnings
See `product-context.md` → Learnings. Proposed learnings appear in the digest until accepted or rejected.

## Log
- <date> tick: audit, watch. Named 12% → 15%. Opened bet 2026-11-12-vs-acme.
```

Rules:

- Open the bet in the ledger before acting. A bet without a metric, a baseline, an expected value
  and a check date isn't a bet, and `gtm.py bet open` refuses it.
- Prefer the strongest method the traffic allows: `ab`, then `holdout` (change half the prompts,
  pages or accounts and compare with the untouched half), then `staggered`, then `before_after`,
  which is reported as directional.
- Close every bet with `gtm.py bet close`; it reads the metric from the store and judges
  `won`, `lost` or `inconclusive`. Inconclusive bets usually mean the metric is too coarse or the
  sample too small; fix the measurement before retrying the tactic.
- Keep the narrative short. The digest and the ledger carry the numbers.
