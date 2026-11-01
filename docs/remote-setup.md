# Running it on a server: the playbook

How to point this plugin at a product and leave it running unattended. There are two paths:
**Claude Code** (a cloud routine, or a server you run) and **Hermes Agent** (a long-running agent
on your own server). Both end in the same state: one daily `gtm tick` against the product repo,
with work arriving as PRs and drafts, and a digest telling a human what needs them.

This is the high-level runbook. Mechanics for each host are in
[`skills/gtm/references/hosts.md`](../skills/gtm/references/hosts.md).

## 0. Decide before you start

| decision | recommendation |
|---|---|
| Which repo the agent works in | The product repo that holds the website source (or the site repo, if separate). It must be able to read the code to build the claims ledger. |
| Who owns it | One named human who reviews PRs and sends drafts. The digest goes to them. |
| Budget | $20/month of treg balance to start (`gtm init --budget 20`). Steady state is about $8-12. |
| Stage | `prelaunch` if the site is deliberately hidden from search; otherwise `launched`. |
| Where digests go | The agent's chat (Hermes gateway) or a pinned GitHub issue. A file is always committed too. |

## 1. Accounts and credentials (least privilege)

| what | why | scope it to |
|---|---|---|
| **treg** team + balance | all live data (AI answers, search, pages) | a team for this work, prepaid; per-run and monthly caps live in `gtm.json` |
| **GitHub token** for a bot or machine user | clone, commit `.marketing/`, open PRs | **only the product repo**: contents + pull requests write. Fine-grained PAT or GitHub App. |
| **Model access** | the agent itself | Claude Code: an Anthropic account or API key. Hermes: whichever provider it's configured with. |

What the agent must **not** get: deploy credentials for the website, DNS or CDN access, email
or social logins, or analytics admin. Everything public goes through a human. That's what keeps
the autonomy gates real, not a matter of policy.

**Protect the default branch.** Require a PR review to merge, so nothing the agent writes goes
live without a human. If that blocks the agent's own state commits, set `"state_commit": "pr"` in
`.marketing/gtm.json`. State then flows through one rolling PR you merge whenever you like.

## 2. Path A: Claude Code

### A1. Cloud routine (no server to run)

1. Install the plugin in the project: commit a `.claude/settings.json` that enables it, or set
   it up once in an interactive session (`/plugin marketplace add williampsmith/marketing-skills`,
   `/plugin install marketing@marketing-skills`).
2. Run **`/marketing:gtm init` interactively first**, with the owner present: confirm the profile,
   claims ledger, entity card, prompt panel, stage and goal. Commit `.marketing/`.
3. Create a daily routine with `/schedule`. Give it the repo and the prompt from `hosts.md`, and
   put the treg token in its environment as a secret.
4. Watch the first week (section 4).

### A2. Your own server

1. Server: any small Linux VM. Install `git`, `python3` (≥ 3.9), `gh`, the `treg` CLI, and
   Claude Code. Sign each one in with the scoped credentials above.
2. Clone the product repo; install the plugin as in A1.
3. Run `init` interactively over SSH (step A1.2).
4. Add one cron line that runs Claude Code headless in the repo once a day, with the `gtm tick`
   prompt, and logs to a file. Use a non-interactive permission mode that allows only what the
   skills need (git, gh, python3, treg). Don't grant blanket permissions.

## 3. Path B: Hermes Agent

1. **Server**: run Hermes the way you normally do (e.g. its Docker image on a VPS). Inside the
   agent's environment you need `git`, `python3`, `gh` and the `treg` CLI, each signed in with the
   scoped credentials above.
2. **Skills**: clone this repo onto the server and link `skills/*` into the agent's skills
   directory, keeping the folders side by side. Updating is `git pull`.
3. **Product repo**: clone it where the agent can work in it, with the bot's GitHub token.
4. **Messaging**: connect the gateway (Telegram, Slack, …) and set `notify.channel: "gateway"`
   during init. The digest's "Needs you" list arrives in chat, and replies such as "approve 2" are
   applied on the next tick.
5. **Init in chat**: tell the agent to run the `gtm` skill in init mode for the repo. Answer its
   questions (stage, goal, notify channel) and confirm the profile, claims and panel it drafts.
6. **Heartbeat**: ask the agent to schedule one daily job that runs `gtm` in tick mode for that
   repo (prompt in `hosts.md`). One job only; `gtm` decides what's due.
7. **Optional hardening**: run the free access check from CI as well (`hosts.md`), so a model or
   server outage can't hide your site becoming invisible to AI bots.

## 4. The first week

| day | what to check |
|---|---|
| 0 | `init` committed `.marketing/` (profile, claims, entity, panel, gtm.json, plan.md); the heartbeat exists |
| 1 | First tick ran: access check and baseline audit recorded; spend is on the order of $1 |
| 1-2 | First digest arrived with a diagnosis (which rung) and a 30-day plan. Read the plan and push back. |
| 3-7 | First PRs and drafts arrive. Review them hard: this is where you teach the claims ledger and the voice. |
| 7 | `gtm status` shows the budget on track, no alerts, and bets with check dates |

## 5. Operating it

- **Pause**: disable the scheduled job. State is in the repo, so resuming continues where it stopped.
- **Change budget, cadence or panel**: tell the agent; it proposes the change in the digest, and you
  approve. Or edit `.marketing/gtm.json` yourself in a PR.
- **Update the skills**: `git pull` in the clone (Hermes, A2), or update the plugin (A1).
- **Costs**: `gtm.py budget`, or the treg dashboard. Paid jobs stop on their own at the cap.
- **When it alerts** (access regression, lost prompts, budget exhausted, dirty repo), it stops
  that line of work and tells you. Fix the cause, then reply or rerun.
- **Rotate tokens** like any other bot account. The agent never stores secrets in the repo.
