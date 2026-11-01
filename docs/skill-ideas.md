# Skill backlog

Built: `ai-visibility-audit`, `ai-search-optimization`, `one-pager`, `citation-outreach`,
`entity-presence`, `comparison-pages`.

## Next: `gtm`, the single entry point
Agreed design (2026-11-01):

- **Plan file** `.marketing/plan.md`: stage, main goal metric, monthly treg budget and spend so far,
  active bets tied to panel prompt ids, cadence with the last-run date of each job, and an
  experiment log. Every run reads it first and writes it last.
- **Ladder diagnosis**: work on the lowest rung not yet met. 0 Reachable (access check) → 1 Known
  (brand prompts correct; `entity-presence`) → 2 Associated (category/problem; `one-pager`,
  `citation-outreach`) → 3 Preferred (comparison/alternatives; `comparison-pages`) → 4 Converting
  (AI referrals → sign-ups; `ai-referral-dashboard`).
- **Modes**: `init` (no `.marketing/`; includes a pre-launch variant), `tick` (what's due?),
  `weekly`, `launch <PR>`, `status` (read-only). No argument = detect.
- **Heartbeat scheduling**: one scheduler entry (Hermes cron, `/schedule`, CI) calls `gtm tick`
  daily. `gtm` decides what's due from the dates in the plan file, so the schedule is data the
  agent can change, not a set of cron entries.
- **Autonomy gates**: measuring, research and drafting run unattended; pages and site changes go to a PR;
  outreach is drafted and never sent; spend has per-run and monthly caps.
- **Digest**: always committed to `.marketing/digests/<date>.md`, plus a short push to wherever
  the human will see it (gateway message, PR or issue comment).
- Starting budget: $20/month.

## After gtm
- `ai-referral-dashboard`: GA4, Search Console, PostHog and CDN bot logs through treg-connected
  accounts, set next to panel visibility per landing page. Rung 4 of the ladder.
- `claims-guard`: the one-pager's claims gate as a standalone linter and hook for any copy.
- `docs-for-agents`: for devtools. llms-full.txt, Markdown mirrors, OpenAPI, an MCP stub, and an
  AGENTS.md integration guide. Measured by whether agents can complete a "use <product> to do X" task.
- `launch-kit`: a merged feature becomes an updated claims ledger, a page if it answers an intent,
  feed updates, posts, and new panel prompts.

## Later (other marketing tracks)
- Short-form video via the treg `make-ugc` skill, wired to the profile.
- `lead-signals` integration: route people complaining about the problem to sales.
- Paid search and ads-library competitive monitoring.
