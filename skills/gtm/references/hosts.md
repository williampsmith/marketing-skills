# Installing the heartbeat

One scheduler entry, daily, that runs `gtm tick` in the product repo. Everything else (what's due,
weekly or quarterly jobs, events) is decided by `gtm.py tick` from `.marketing/gtm.json`. Never
create one scheduler entry per job; then the schedule lives where the agent can't see or change it.

For the whole setup (credentials, branch protection, supervised init, first week), see
`docs/remote-setup.md` in the plugin repo. Pick a quiet hour in the team's timezone. Use the same prompt everywhere:

> Run the gtm skill in tick mode for the repo at <path>. Follow its "Every run" steps, respect its
> autonomy gates, and notify per gtm.json.

## Hermes Agent

Hermes reads Agent Skills folders, so copy or symlink the plugin's `skills/` directory into its
skills directory, keeping the skills side by side. Then:

- The host needs the product repo checked out (with push access for state commits and `gh` for
  PRs), a treg token (`treg` CLI signed in, or the token in the agent's environment), and `python3`.
- Create the cron job with Hermes's scheduler, using the prompt above, daily. Cron jobs persist in the
  agent's data directory (e.g. `/opt/data/cron/` in the Docker image). If you manage agents
  declaratively, keep the job definition in that config like the rest of the agent's setup.
- Set `notify.channel: "gateway"` in gtm.json. The digest's "Needs you" goes to the agent's chat,
  and your replies ("approve 1, 3") are applied on the next tick.
- Long skills (one-pager, outreach triage) can be split across the agent's subagents. Give each one
  the job recipe and the gates, never the whole program.

## Claude Code

- Cloud: `/schedule` a daily routine with the prompt above on the product repo. The routine needs the
  treg token as an environment secret and repo write access.
- Local: `/loop` works only while a session is open, so use it for a supervised week, not production.

## CI (GitHub Actions) — the jobs that need no model

Run the free, deterministic jobs on CI so a model outage or a bad run can't hide a regression.

```yaml
name: marketing-heartbeat
on:
  schedule: [{cron: "17 6 * * *"}]
  workflow_dispatch: {}
jobs:
  access:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          mkdir -p .marketing/access
          mv .marketing/access/latest.json .marketing/access/previous.json 2>/dev/null || true
          python3 path/to/skills/ai-search-optimization/scripts/check_ai_access.py "$SITE" / /pricing --json .marketing/access/latest.json || echo "problems found"
          python3 path/to/skills/gtm/scripts/gtm.py record access_check
        env: {SITE: "https://example.com"}
      # commit .marketing/ back (bot user), or upload as an artifact for the agent's tick to read
```

The audit can also run on CI (install the treg CLI and put the token in a secret), with the
agent's tick doing only the judgment: reading the report, the work session, and the digest.
That split is the most robust setup.

## Any other host

Anything that can run an agent with this skill on a daily timer works: cron plus a headless agent
CLI, or a workflow tool. The contract is the same: one daily `gtm tick`, the repo checked out, treg
available, and `python3`.
