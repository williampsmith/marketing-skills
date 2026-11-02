# Running it on a server: the playbook

How to point this plugin at a product and leave it running unattended. There are two paths:
**Claude Code** (a cloud routine, or a server you run) and **Hermes Agent** (a long-running agent
on your own server). Both end in the same state: one daily run of the `gtm` skill in tick mode against the product repo,
with work arriving as PRs and drafts, and a digest telling a human what needs them.

This is the high-level runbook. Mechanics for each host are in
[`skills/gtm/references/hosts.md`](../skills/gtm/references/hosts.md).

## 0. Decide before you start

| decision | recommendation |
|---|---|
| Which repo the agent works in | The product repo that holds the website source (or the site repo, if separate). It must be able to read the code to build the claims ledger. |
| Where the state lives | Outside the product repo. A persistent host (Hermes VPS, your own server) uses the default `dir` store on that machine. An ephemeral host (Claude Code cloud routine) needs a private state repo, e.g. `<product>-marketing`. |
| Who owns it | One named human who reviews PRs and sends drafts. The digest goes to them. |
| Budget | $20/month of treg balance to start (`gtm.py init --budget 20`). Steady state is about $8-12. |
| Stage | `prelaunch` if the site is deliberately hidden from search; otherwise `launched`. |
| Where digests go | The agent's chat (Hermes gateway) or a pinned GitHub issue. A copy is always written to the state store. |

## 1. Accounts and credentials (least privilege)

| what | why | scope it to |
|---|---|---|
| **treg** team + balance | all live data (AI answers, search, pages) | a team for this work, prepaid; per-run and monthly caps live in `gtm.json` |
| **GitHub token** for a bot or machine user | clone the product repo, push branches, open PRs; push the state repo if you use one | **only those repos**: contents + pull requests write. Fine-grained PAT or GitHub App. |
| **Model access** | the agent itself | Claude Code: an Anthropic account or API key. Hermes: whichever provider it's configured with. |

What the agent must **not** get: deploy credentials for the website, DNS or CDN access, email
or social logins, or analytics admin. Everything public goes through a human. That's what keeps
the autonomy gates real, not a matter of policy.

**Protect the default branch** of the product repo. Require a PR review to merge, so nothing the
agent writes goes live without a human. The agent never needs to push to it: pages and site changes
go through PRs, and its own bookkeeping goes to the state store.

## 2. Path A: Claude Code

### A1. Cloud routine (no server to run)

1. Create a private state repo (e.g. `acme/product-marketing`, empty is fine) and give the bot token
   write access to it.
2. Install the plugin in the project: commit a `.claude/settings.json` that enables it, or set
   it up once in an interactive session (`/plugin marketplace add williampsmith/marketing-skills`,
   `/plugin install marketing@marketing-skills`).
3. Run **`/marketing:gtm init` interactively first**, with the owner present. Point it at the state
   repo (`gtm.py store use <git URL>`, then `gtm.py sync pull`), and confirm the product context and
   GTM profile, claims ledger, entity card, prompt panel, stage and goal. The run ends with
   `gtm.py sync push`.
4. Create a daily routine with `/schedule`. Give it the repo and the prompt from `hosts.md`, and put
   `MARKETING_STATE=<state repo git URL>` and the treg token in its environment as secrets.
5. Watch the first week (section 4).

### A2. Your own server

1. Server: any small Linux VM. Install `git`, `python3` (≥ 3.9), `gh`, the `treg` CLI, and
   Claude Code. Sign each one in with the scoped credentials above.
2. Clone the product repo; install the plugin as in A1. The default `dir` store
   (`~/.marketing/<owner>-<repo>/`) keeps state on the server; include it in the server's backups.
3. Run `init` interactively over SSH (step A1.3, without the state repo).
4. Add one cron line that runs Claude Code headless in the repo once a day, with the gtm tick-mode
   prompt, and logs to a file. Use a non-interactive permission mode that allows only what the
   skills need (git, gh, python3, treg). Don't grant blanket permissions.

## 3. Path B: Hermes Agent

1. **Server**: run Hermes the way you normally do (e.g. its Docker image on a VPS). Inside the
   agent's environment you need `git`, `python3`, `gh` and the `treg` CLI, each signed in with the
   scoped credentials above. Keep `~/.marketing` on a persistent volume, since that's where the
   default state store lives.
2. **Skills**: clone this repo onto the server and link `skills/*` into the agent's skills
   directory, keeping the folders side by side. Updating is `git pull`.
3. **Product repo**: clone it where the agent can work in it, with the bot's GitHub token.
4. **Messaging**: connect the gateway (Telegram, Slack, …) and set `notify.channel: "gateway"`
   during init. The digest's "Needs you" list arrives in chat, and replies such as "approve 2" are
   applied on the next tick.
5. **Init in chat**: tell the agent to run the `gtm` skill in init mode for the repo. Answer its
   questions (stage, sales motion, deal size, goal, notify channel) and confirm the product context,
   claims and panel it drafts.
6. **Heartbeat**: ask the agent to schedule one daily job that runs `gtm` in tick mode for that
   repo (prompt in `hosts.md`). One job only; `gtm` decides what's due.
7. **Optional hardening**: run the free access check from CI as well (`hosts.md`), so a model or
   server outage can't hide your site becoming invisible to AI bots.

## 4. The first week

| day | what to check |
|---|---|
| 0 | `gtm.py where` shows the store outside the repo; `init` wrote gtm.json, product-context.md, claims, entity card, panel and plan.md there; the heartbeat exists |
| 1 | First tick ran its work session; the baseline audit and access check from init are recorded; spend is on the order of $1 |
| 1-2 | First digest arrived with the focus and why, and a 30-day plan. Read the plan and push back. |
| 3-7 | First PRs and drafts arrive, each tied to a bet. Review them hard: this is where you teach the claims ledger and the voice. |
| 7 | `gtm.py status` shows the budget on track, no alerts, and open bets with check dates |

## 5. Operating it

- **Pause**: reply "pause" to a digest, or run `gtm.py pause --reason "…"`. Every job stops until
  `gtm.py resume`. Disabling the scheduled job also works; state is in the store, so resuming
  continues where it stopped.
- **Change budget, cadence, floors or panel**: tell the agent; it proposes the change in the digest,
  and you approve. Or edit `<state>/gtm.json` yourself.
- **Update the skills**: `git pull` in the clone (Hermes, A2), or update the plugin (A1).
- **Costs**: `gtm.py budget`, or the treg dashboard. Paid jobs stop on their own at the cap.
- **When it alerts** (access regression, lost prompts, budget exhausted, dirty repo, a failed
  `sync pull`, an action that failed twice), it stops that line of work and tells you. Fix the
  cause, then reply or rerun.
- **Rotate tokens** like any other bot account. The agent never stores secrets in either repo.

## 6. Upgrading a 0.3 install

0.3 kept its state in `.marketing/` inside the product repo and committed it there. That still works
(the `repo` backend), but the default is now to keep it outside:

1. On the agent's host, in the product repo: `gtm.py migrate --to <dir or git URL>`. It copies
   `.marketing/` into the new store, upgrades `gtm.json` (the old `state_commit` setting is removed)
   and remembers the store for this repo.
2. Open a PR in the product repo that deletes `.marketing/`. Whether to rewrite history to remove it
   entirely is the team's call.
3. Check `gtm.py where` and run one `gtm.py status` before the next scheduled tick.
