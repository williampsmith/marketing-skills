# Guardrails

What the operator may do alone, what waits for a human, and how it stops. Every skill in the plugin
follows these tiers. Legal rules for sending and personal data are in `compliance.md`.

## Action tiers

| tier | actions | default |
|---|---|---|
| **1 · autonomous** | read, measure, research, score, draft, stage, open PRs, write the state store, queue events for PostHog | allowed |
| **2 · gated** | publish, send, spend, change ad or email settings, contact a person, merge, delete | a human approves each one, in the digest or on a review page |
| **2 · bounded** | a tier-2 action the human authorised in `gtm.json → authority` | allowed within its caps: per-run and daily volume, spend, an allowlist of accounts, lists or segments |

Some gated actions have a fixed form:

- Site changes, pages, robots.txt, structured data, tracking code: **a PR**. A human merges.
- Outreach, posts, profile edits, emails: **a draft** in the state store or a review page.
- Panel, floors, budget, cadence, profile, fit overrides: **a proposal** in the digest, applied after
  a human says yes. Never raise the budget yourself.
- Anything outside the state store and the agent's own branches: **never deleted or overwritten**
  unattended.

## Sending authority

Authority to send is earned per channel, in three steps.

1. **Draft.** Every channel starts here. The agent writes the message; a human sends it.
2. **Approve-to-send.** The human approves a batch (in the digest, "approve 1, 3", or on the review
   page) and the agent sends exactly those messages, unchanged. Follow-ups go out only inside a
   sequence the human approved, and stop on any reply.
3. **Bounded.** Opt-in per channel. The agent sends without per-message approval, within daily caps,
   to contacts matching an approved segment, using approved templates. It can be switched on only
   after 30 days of approve-to-send in that channel with a reply rate at or above the floor and no
   complaints, spam reports or unsubscribe spikes.

All sending uses a dedicated shared inbox on a separate sending domain (e.g. `hello@try<product>.com`),
authenticated with SPF, DKIM and DMARC, so a mistake can't damage the main domain's deliverability.
Every reply goes to a human.

### Approve-to-send, as implemented (0.6)

Channels: `outbound`, `citation_outreach`, `creators`, `lifecycle_email`. Every one starts at
`draft`.

| step | command | who |
|---|---|---|
| grant | `gtm.py authority grant <channel> --level approve_to_send --daily-cap 20 [--cooldown-days 30] --quote "<the human's words>"` | a human, in a session where they are present |
| check | `gtm.py authority show` | anyone |
| draft | write `<state>/sends/<batch>/drafts.jsonl`, one channel per batch, best first, `to` one bare address | the agent |
| approve | `gtm.py approve <id> --count 12 --quote "<their reply verbatim>"`: pins the first 12 drafts by content hash; a batch is approved once and never topped up | applied in a human-present session |
| send | `../outbound/scripts/send_batch.py <batch> --dry-run`, then without `--dry-run` | the agent |

**Unattended runs can't approve or grant.** Scheduled runs set `MARKETING_UNATTENDED=1`, and
`gtm.py approve` and `authority grant` refuse while it is set. A scheduled run that finds an
approval or grant in the digest thread records it in `plan.md` as pending, verbatim; the next
session with the human present (they run `/marketing:gtm`, or tell the Hermes agent in chat)
applies it with `--quote`. The quote is stored with the approval or grant.

**Approvals are pinned by content.** Each approved draft's recipient, subject, body and routing are
hashed at approval. A draft edited, reordered or added afterwards is no longer approved.

What `send_batch.py` enforces:

- **Capacity.** Exit 3 when the program is paused, the channel is `draft` or at an unknown level, or
  today's cap is used up. Otherwise it sends as many as the cap allows and leaves the rest for the
  next run.
- **Kill switch, per message.** `gtm.py pause` writes `<state>/PAUSED` without waiting for any lock,
  and the batch stops before its next message.
- **Recipients.** `to` must be exactly one bare address. Skipped: anything suppressed (an email or
  a domain in `<state>/suppression.csv`; subdomains match), duplicates within the batch, anything
  already sent, and any key (the account's domain) inside the channel's cooldown. The cooldown key
  is `send:<channel>`, so each channel has its own.
- **Follow-ups.** `followup_of` skips the cooldown only when the same address got an earlier
  message, it has had fewer than 2 follow-ups, and it isn't in `<state>/replied.csv`.
- **Every message** gets the sender's postal address and opt-out line (`gtm.json → sender`), a
  `Date` and a `List-Unsubscribe` header, and comes from `SMTP_FROM` on the dedicated sending domain.
- **Failures.** An "attempt" is logged before each send and "sent" after. A permanent rejection
  (5xx) is logged as a bounce and added to suppression. Any other failure stops the run, and the
  unfinished attempt is held for a human rather than resent.
- **Where it runs.** It refuses on the `repo` backend, so contacts never land in the product repo.
  On the `git` backend it pulls before sending and pushes right after.
- **Personal data.** `<state>/sends.jsonl` logs counts without addresses, and cooldown keys are
  domains. The batch folder keeps addresses; nothing else does.

The `bounded` step is not implemented yet (it arrives in 0.8).

These stay at approve-to-send permanently, whatever the channel's step: press and editors, named
enterprise accounts, existing customers in a dispute, and anyone who has replied before.

## Always escalate

Stop that line of work and notify now, don't wait for the digest, when you see:

- A crisis or a negative mention that needs a response, or a complaint about the agent's messages.
- A revenue, signup or spend anomaly. Report it; don't self-correct.
- An access regression (a bot can no longer read a key page).
- A claim that's ambiguous, or anything legal, medical or financial that needs claim sign-off.
- Something that would delete data or contact a large audience at once.
- A dirty tree, a failed `git pull` or `gtm.py sync pull`, or an exhausted budget.

## Kill switch

`gtm.py pause --reason "<why>"` stops the program at once: it writes `<state>/PAUSED` without
waiting for the lock, so it lands even mid-send. `tick` then returns no jobs and an alert, and
`gtm.py may` refuses every action, so check `may` before anything that sends or contacts someone.
`gtm.py resume` turns it back on. The human can also pause by replying "pause" to a digest; apply it
first thing on the next run.

## Repetition and failure

- **Cooldowns.** A job with `cooldown_days` and a `dedupe_key` (outreach by target domain, for
  example) must not touch the same key twice inside the window. Check with `gtm.py may JOB KEY`
  (exit 3 means no) before acting, and record the action with `gtm.py record JOB --key KEY`.
  `record` never refuses (spend and history are kept) but warns when a key was inside its window.
- **Failures.** Record a failed attempt with `gtm.py record JOB --failed --key KEY`. After two
  failures on one key, `tick` raises an `ESCALATE` alert and `may` refuses that key until a human
  has looked. A later successful `record --key` clears the count.

## Spend

- Before any paid job: `gtm.py budget --need <usd>`. Exit 2 means skip it and say so in the digest.
- Pass a ceiling into every script (`--max-usd`): the smaller of the job's estimate × 1.5 and the
  remaining budget.
- Ad spend, once the paid track is on, has its own caps in `authority` and never draws on the treg
  budget.
