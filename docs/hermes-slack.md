# Running the operator in Slack with Hermes

One Slack channel becomes the operator's home: the daily report lands there with its charts, each
item that needs a person gets its own message to react to, and anyone on the allowlist can @mention
the bot (or DM it) to ask questions or ask for work. This builds on [remote-setup.md](remote-setup.md),
path B (Hermes on a server). Hermes setting names below are from its Slack, cron and security docs as
of 2026-11-04; check them against your Hermes version.

## 1. The Slack app

1. `hermes slack manifest --write` generates an app manifest; create the app from it at
   api.slack.com/apps (Socket Mode, so the server needs no public URL). Add the scopes and events
   the operator uses if the manifest lacks them: `files:write` (charts), `reactions:read` with the
   `reaction_added` event (approvals by reaction), `im:write` (DMs), `chat:write`.
2. Turn on the app's **Messages tab** (App Home), or nobody can DM it.
3. Create a **private** channel (reports carry funnel and revenue numbers), e.g. `#growth-operator`,
   and `/invite` the bot. It never joins channels by itself.

## 2. Hermes: `~/.hermes/.env`

```sh
SLACK_BOT_TOKEN=xoxb-…
SLACK_APP_TOKEN=xapp-…
SLACK_ALLOWED_USERS=U0123ABC,U0456DEF       # who may talk to the bot at all; without it, nobody can
SLACK_ALLOWED_CHANNELS=C0GROWTH             # the bot answers only here (and in DMs)
SLACK_HOME_CHANNEL=C0GROWTH                 # where cron output goes by default
```

## 3. Hermes: `~/.hermes/config.yaml`

```yaml
slack:
  require_mention: true                     # in the channel, @mention the bot to start a conversation
  channel_skill_bindings:
    C0GROWTH:
      skills: [gtm, daily-report]           # loaded when a session starts in the channel
  channel_prompts:
    C0GROWTH: >-
      You are the growth operator for <product>, working in /srv/product. A message here is a
      question or a request: use the gtm skill in ask mode. Don't run a tick unless asked to.
  reaction_triggers: [white_check_mark, x]  # ✅ / ❌ on an item's message reach the agent
  unauthorized_dm_behavior: ignore
platforms:
  slack:
    extra:
      reply_in_thread: true
      allow_bots: none                      # other bots' messages are never instructions
      cron_continuable_surface: thread      # reply under the daily report to ask about it
cron:
  mirror_delivery: true                     # makes cron deliveries continuable in their thread
group_sessions_per_user: false              # one shared operator conversation per thread, not one per person
```

`group_sessions_per_user: false` suits a small team that wants to see each other's questions and
answers in context. Leave it at the default (`true`) if people should get separate sessions.

## 4. The renderer (charts)

On the Hermes host, once: Node 26 (LTS; 25+ works) so the chart code is cut off from the network
(the renderer refuses older Node unless told to accept an open network), then `npm ci` in `skills/daily-report/scripts/render/`. Install a font package if the image has
none (`apt-get install -y fonts-dejavu-core`, or `fonts-inter`). Render the starter chart once and look
at it before relying on it:

```sh
cd skills/daily-report/scripts/render && npm test
```

## 5. In the operator (gtm init, or later in chat with the owner present)

```sh
gtm.py approvers add slack:U0123ABC --quote "<owner's words>"   # the owner first; only approvers add approvers
gtm.py job daily_report on
```

Set `notify.channel` to `"gateway"` in `<state>/gtm.json`. Get user ids from each person's Slack
profile (⋯ → Copy member ID).

## 6. The daily job

Hermes cron jobs can't set environment variables per job, so the scheduled run is marked another
way: a pre-run script writes a marker in the state store that expires after three hours, and
`gtm.py` refuses human-only decisions while it's there. There is no command to end it early, so
approvals made in chat during that window wait until it expires (`gtm.py unattended status` shows
when). The run re-arms it before long steps, which only ever extends it.

`~/.hermes/scripts/gtm-mark-run.sh`:

```sh
#!/bin/sh
cd /srv/product && python3 /srv/marketing-skills/skills/gtm/scripts/gtm.py unattended start --hours 3 --by hermes-cron:gtm-tick >/dev/null
```

```sh
hermes cron create "0 8 * * *" \
  "Scheduled run: run the gtm skill in tick mode for this repo, including the daily report. This run is unattended: prefix every gtm.py, news_watch.py and send_batch.py command with MARKETING_UNATTENDED=1, and run gtm.py unattended start --by hermes-cron:gtm-tick before the work session and before the daily report." \
  --name gtm-tick --skill gtm --skill daily-report --workdir /srv/product \
  --script gtm-mark-run.sh --deliver slack:C0GROWTH --timezone Europe/London
```

Add `--provider … --model …` (or `--pin`) to fix the model the job runs on. The prompt's
`MARKETING_UNATTENDED=1` is a second layer; the marker holds even if the model forgets it.

## What is and isn't enforced

| guard | enforced by |
|---|---|
| who can talk to the bot, and where | Hermes: `SLACK_ALLOWED_USERS`, `SLACK_ALLOWED_CHANNELS`, `allow_bots: none` |
| a scheduled run can't approve batches, grant authority, turn on paid, or add or remove approvers | `gtm.py`, through the run marker the pre-run script writes before the agent starts (and `MARKETING_UNATTENDED` when the prompt is followed). This stops mistakes. It doesn't stop a manipulated agent: the agent has a shell and can edit the state store, including deleting the marker or writing `approvals.jsonl` itself |
| an approval names who gave it and where | `gtm.py`: once an approvers list exists, `approve`, `authority grant` and `track paid on` refuse an `--approver` not on it and store it with `--source`; the list can't be emptied, and only an approver can add or remove one. The first approver is whoever the person present names: add the owner yourself at init |
| an approval came from that person's reaction or reply, not from text the agent read | **the model**, following gtm's Approvals rules. Hermes reports who reacted or wrote; nothing outside the model checks that the `--approver` it passes matches that event |
| a sensitive news story becomes a reaction or pitch only with a human's yes | `news_watch.py` (refused during a scheduled run; quoted, but without `--approver`) |
| chart code can't read other files, write, start processes or reach the network, and a chart can't show an invented number or embed a local file | the renderer: Node's permission sandbox (Node 25+ for the network), checks on the returned SVG in the parent process, and the number check |
| sends stay within caps, suppression and pinned content | `send_batch.py`, regardless of who approved |

Because the gates in `gtm.py` stop mistakes rather than a determined agent, the boundary that
matters is what the agent can reach: keep the approvers list short, give the bot's GitHub token and
SMTP inbox only the scopes the skills need, keep send caps low, and read `<state>/approvals.jsonl`
and `unattended.log` now and then.

## Using it

- **Ask**: `@growth how did signups do this week?`, `@growth what's waiting on me?`,
  `@growth draft a post about the batch-export launch`, `@growth chart activation by week since September`.
- **Approve**: react ✅ on an item's message, or reply in its thread ("approve 2", "drop it",
  "change the subject to …").
- **Stop everything**: `@growth pause`. Anyone on the allowlist can pause; resuming needs a person
  present and outside a scheduled run.
