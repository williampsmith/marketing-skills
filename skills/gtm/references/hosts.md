# Installing the heartbeat

One scheduler entry, daily, that runs `gtm tick` in the product repo. Everything else (what's due,
weekly or quarterly jobs, events) is decided by `gtm.py tick` from `<state>/gtm.json`. Never create
one scheduler entry per job; then the schedule lives where the agent can't see or change it.

For the whole setup (credentials, branch protection, supervised init, first week), see
`docs/remote-setup.md` in the plugin repo. Pick a quiet hour in the team's timezone. Use the same
prompt everywhere:

> Run the gtm skill in tick mode for the repo at <path>. Follow its "Every run" steps, respect its
> autonomy gates, and notify per gtm.json.

## Where the state lives

`<state>` is the directory `gtm.py where` prints. The product repo only receives PRs; the program's
memory lives in the state store. Pick the backend by how long the host lives:

| host | backend | setup |
|---|---|---|
| Persistent: Hermes on a VPS, your own server | `dir` (default) | nothing: state goes to `~/.marketing/<owner>-<repo>/` on that machine. Back the directory up with the rest of the host. |
| Ephemeral: a Claude Code cloud routine, a fresh container per run | `git` | a private state repo (e.g. `<product>-marketing`) that the agent's token can push to |
| Teams that want 0.3's behaviour | `repo` | `.marketing/` in the product repo, committed as before |

With the `git` backend, every run starts with `gtm.py sync pull` and ends with `gtm.py sync push`.
Point the agent at the state repo once with `gtm.py store use <git URL>` (saved in
`~/.marketing/config.json`). On a host that forgets its home directory between runs, set
`MARKETING_STATE=<git URL>` in the routine's environment instead.

`sync pull` only fast-forwards. If the clone has uncommitted changes or the remote diverged, it stops
and the run should alert rather than guess.

## Hermes Agent

Hermes reads Agent Skills folders, so copy or symlink the plugin's `skills/` directory into its
skills directory, keeping the skills side by side. Then:

- The host needs the product repo checked out (with `gh` for PRs), a treg token (`treg` CLI signed
  in, or the token in the agent's environment), and `python3`. The `dir` backend keeps state on the
  host.
- Create the cron job with Hermes's scheduler, using the prompt above, daily. Cron jobs persist in the
  agent's data directory (e.g. `/opt/data/cron/` in the Docker image). If you manage agents
  declaratively, keep the job definition in that config like the rest of the agent's setup.
- Set `notify.channel: "gateway"` in gtm.json. The digest's "Needs you" goes to the agent's chat,
  and your replies ("approve 1, 3") are applied on the next tick.
- Long skills (one-pager, outreach triage) can be split across the agent's subagents. Give each one
  the job recipe and the gates, never the whole program.

## Claude Code

- Cloud: `/schedule` a daily routine with the prompt above on the product repo. Add
  `MARKETING_STATE=<state repo git URL>` and the treg token as environment secrets, and give the
  routine write access to the state repo. The skill's "Every run" steps pull and push it.
- Own server: cron runs Claude Code headless in the product repo once a day. The `dir` backend is
  enough.
- Local: `/loop` works only while a session is open, so use it for a supervised week, not production.

## CI (GitHub Actions) — the jobs that need no model

Run the free, deterministic jobs on CI so a model outage or a bad run can't hide a regression. The
workflow checks out the state repo next to the product and writes there; nothing is committed to
the product repo.

```yaml
name: marketing-heartbeat
on:
  schedule: [{cron: "17 6 * * *"}]
  workflow_dispatch: {}
jobs:
  access:
    runs-on: ubuntu-latest
    env:
      SITE: "https://example.com"
      MARKETING_STATE: ${{ github.workspace }}/state
    steps:
      - uses: actions/checkout@v4
        with: {path: product}
      - uses: actions/checkout@v4
        with: {repository: acme/product-marketing, token: "${{ secrets.STATE_REPO_TOKEN }}", path: state}
      - name: access check
        working-directory: product
        run: |
          mkdir -p "$MARKETING_STATE/access"
          mv "$MARKETING_STATE/access/latest.json" "$MARKETING_STATE/access/previous.json" 2>/dev/null || true
          python3 path/to/skills/ai-search-optimization/scripts/check_ai_access.py "$SITE" / /pricing \
            --json "$MARKETING_STATE/access/latest.json" || echo "problems found"
          python3 path/to/skills/gtm/scripts/gtm.py record access_check
      - name: push state
        working-directory: state
        run: |
          git config user.name marketing-heartbeat
          git config user.email marketing-heartbeat@users.noreply.github.com
          git add -A && git commit -qm "marketing: access check $(date -u +%F)" && git push || echo "no changes"
```

`MARKETING_STATE` here is a directory (the checkout), so `gtm.py` uses it directly and the workflow
does the git push itself. The audit can also run on CI (install the treg CLI and put the token in a
secret), with the agent's tick doing only the judgment: reading the report, the work session, and
the digest. That split is the most robust setup.

## Any other host

Anything that can run an agent with this skill on a daily timer works: cron plus a headless agent
CLI, or a workflow tool. The contract is the same: one daily `gtm tick`, the repo checked out, the
state store reachable, treg available, and `python3`.
