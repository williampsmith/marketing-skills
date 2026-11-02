# Skill backlog

The growth-operator spec ([`design/growth-operator.md`](design/growth-operator.md)) is fully
implemented as of 0.8: the state store, tracks, fit, focus and bets (0.4); measurement (0.5);
customer research, competitive intel, SEO, content, outbound, creative and social (0.6); CRO,
activation and experiments (0.7); lifecycle, paid, and bounded sending and spend authority (0.8).

## Next
- `docs-for-agents`: for devtools. llms-full.txt, Markdown mirrors, OpenAPI, an MCP stub, and an
  AGENTS.md integration guide. Measured by whether agents can complete a "use <product> to do X" task.
- Reply handling: read the sending inbox (IMAP) so replies, bounces and complaints reach
  `gtm.py outcome` and `suppression.csv` without a human relaying them.
- CRM stages: pull qualified, meeting and won counts from the CRM, so sales-led funnels don't depend
  on hand-recorded stage metrics.
