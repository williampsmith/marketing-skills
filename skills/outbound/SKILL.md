---
name: outbound
description: Find accounts that match the product's ICP and are showing a buying signal now, research each one, find the right person and a verified email through treg, and write short, specific first touches and follow-ups through the writing gates into a batch for a human to approve. Sends only what a human approved, only on a channel a human granted approve-to-send, from a dedicated sending inbox, within daily caps, never to suppressed addresses. Also runs creator pitches (channel `creators`). Use when the gtm operator runs outbound_signals, or the user asks for outbound, prospecting, cold email, account research, a target list, "find companies that need us", or creator outreach. For pitches to editors of pages AI engines cite, see citation-outreach; for emails to existing users, see lifecycle (when installed).
---

# Outbound

Outbound works when the message arrives because something just happened at the account (a hire, a
launch, a funding round, a public complaint about the problem) and says one specific, true thing
about why that matters. Volume without a signal burns the sending domain and the brand. This skill
finds the signal, writes the message, and leaves the decision to send with a human until the human
says otherwise.

`<state>` is the directory printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
every script from the product repo root by absolute path. Copy drafted by this skill passes the
`../writing` gates first: claims from the ledger, specific to the recipient, no AI-tell phrasing.

## Requires

- A confirmed GTM profile and `<state>/product-context.md` with an ICP and an anti-ICP
  (`../product-context`). The `outbound_signals` job is skipped until the profile is confirmed and
  the `outbound` channel is eligible in `gtm.py fit`.
- `<state>/claims.md`. Every value claim in a message is an OK row, with its qualifier.
- For sending at all: a human has granted the channel approve-to-send (below), and `gtm.json`
  has `sender.address` (a postal address) and `sender.opt_out` (one line of opt-out text).

## 1. Signal sweep (the `outbound_signals` job, weekly)

Pick 2-3 signals that mean "this account has the problem now" for this ICP, write them in
`plan.md`, and sweep only those. Examples (endpoint ids checked 2026-11-02; verify with
`catalog_get` and state the price before batching):

| signal | how |
|---|---|
| hiring for the role that owns the problem | `blitzapi.companies.tam-by-jobs` (companies hiring for a title), `apollo.companies.jobs` (one company's postings) |
| just raised | `predictleads.financing.discover` (funding feed) |
| a champion changed jobs | `leadmagic.x.job-change-detector` for known contacts |
| talking about the problem in public | `anyapi.linkedin.search.posts`, `scrapecreators.reddit.search.posts` |

If the treg plugin's `lead-signals` skill is installed, use it for the sweep: it already covers
these feeds and returns scored accounts. Either way:

1. Drop accounts that match the anti-ICP, sit in a consent-only country (`../gtm/references/compliance.md`),
   or appear in `<state>/suppression.csv` (email or domain).
2. `python3 ../gtm/scripts/gtm.py may outbound_signals <domain>`. Exit 3 means skip: the account was
   contacted inside its cooldown (90 days), or failed twice.
3. Keep at most `max_actions` (10) accounts per run, strongest signal first.

## 2. Research pack and contact

Endpoint ids below are examples, checked 2026-11-02; verify each with `catalog_get` and state the
price before batching.

For each account, write `<state>/outbound/accounts/<domain>.md`: what they do (`treg.companies.enrich`,
routed), the signal with its link and date, the likely problem it implies, which claims-ledger row
answers it, and one detail only someone who looked would know.

Find the person who owns the problem, not the most senior title: `apollo.people.search` or the routed
`treg.people.search` by title and company. Find and verify the email: `treg.people.email.find`
(routed; providers such as `blitzapi.people.email.find`), then `treg.people.email.verify`. Only
`valid` addresses go into a batch; catch-all or unknown results are dropped, not guessed. Store
names and emails only in the batch folder, never in plan.md, digests, metrics or PostHog.

## 3. Draft the batch

A batch is one channel and one play: `<state>/sends/<batch>/drafts.jsonl`, batch id
`<date>-<play>`, one JSON line per message:

```json
{"to": "dana@acme-bank.com", "subject": "...", "body": "...", "key": "acme-bank.com",
 "channel": "outbound", "followup_of": null, "signal": "hiring a compliance ops lead (2026-11-01)"}
```

- `to` is one bare address (`dana@acme-bank.com`, no display name, never two addresses);
  `send_batch.py` skips anything else. `key` is the account's domain; it defaults to the address's
  domain when left out.
- First touch: under 90 words, one signal, one problem, one claim row, one easy ask (a reply, not
  a meeting link). No attachments, no tracking pixels, plain text.
- Follow-ups belong to a sequence written up front in `references/sequences.md`: at most two, each
  adding something new. A follow-up has `followup_of` set to the first touch's subject and goes in
  its own later batch.
- Order the file best first: approval covers the first N lines, pinned by content hash, so a draft
  edited, reordered or added after approval is no longer approved.
- `gtm.py record outbound_signals --key <domain>` for each account drafted, and `--cost` with the
  treg spend.

Put the batch in the digest's **Needs you**: batch id, count, the play, and three sample messages
inline. The human replies, for example, "approve batch 2026-11-12-hiring, 12".

## 4. Approve, then send

Scheduled runs are unattended (`MARKETING_UNATTENDED=1` in their environment), and `gtm.py`
refuses approvals and grants there. So when a scheduled run finds an approval reply in the digest
thread, it records it in `plan.md` under "Decisions waiting on a human" as pending, verbatim. The
next session with the human present (they run `/marketing:gtm`, or tell the Hermes agent in chat)
applies it with their words quoted:

```
python3 /abs/path/skills/gtm/scripts/gtm.py approve 2026-11-12-hiring --count 12 \
  --quote "approve batch 2026-11-12-hiring, 12"
```

Then check the channel's authority with `python3 /abs/path/skills/gtm/scripts/gtm.py authority show`:

- `draft` (the default): stop. The human sends from the drafts; list the batch path in the digest.
- `approve_to_send`: a human granted it, in a session where they were present, for example
  `gtm.py authority grant outbound --level approve_to_send --daily-cap 20 --quote "<their words>"`.
  Never grant it yourself. Run `python3 /abs/path/skills/outbound/scripts/send_batch.py <batch>
  --dry-run` from the product repo root, read the plan (would-send count, left for later, skipped
  and why), then run it without `--dry-run`.

What `send_batch.py` does:

- Refuses (exit 3) when the program is paused, the channel is drafts-only or at an unknown level, or
  today's cap is used up. Otherwise it sends as many as the daily cap allows and leaves the rest
  for the next run.
- Checks the kill switch before every message: `gtm.py pause` writes `<state>/PAUSED`, which stops
  a batch mid-send.
- Skips drafts that aren't approved (or changed since), aren't one bare address, are suppressed
  (an email or a domain in `<state>/suppression.csv`; subdomains match), are duplicates within the
  batch, were already sent, or whose key is inside the channel's cooldown (`send:<channel>`,
  `cooldown_days` in the authority, default 30).
- Follow-ups (`followup_of` set) skip the cooldown only when the same address got an earlier
  message, it has had fewer than 2 follow-ups, and it isn't in `<state>/replied.csv`.
- Adds the postal address, the opt-out line, `Date` and `List-Unsubscribe`. Logs an "attempt"
  before each send and "sent" after. A permanent rejection (5xx) is logged as a bounce and added to
  suppression automatically. Any other failure stops the run, and the unfinished attempt is held
  for a human instead of being resent.
- Refuses on the `repo` backend (contacts must never land in the product repo). On the `git`
  backend it pulls before sending and pushes right after, so an ephemeral host can't forget what
  it sent.
- Logs sends without addresses (`sends.jsonl`); keys are domains.

### Bounded sending

When `gtm.py authority show` reports `bounded_eligible: true` for the channel, say so in the digest
with the numbers; never grant it yourself. Once a human grants it
(`gtm.py authority grant outbound --level bounded --template <id> --segment <id> --quote "<their words>"`):

- Templates and segments are the approved ones, by id. A template is a message with fixed claims and
  structure (personalisation only in marked slots); a segment is an ICP slice written in plan.md.
- Every draft line carries `"template"` and `"segment"`; `send_batch.py` skips any that don't match
  the allowlist, and sends the rest without `gtm.py approve`, still inside the daily cap,
  suppression and cooldowns.
- After replies come in, record them: `gtm.py outcome outbound --replies N --complaints N`. One
  complaint drops the channel back to approve-to-send.

## 5. Replies and stopping

- Every reply goes to a human. The agent never answers a reply on its own. Add every address that
  replied to `<state>/replied.csv` (one per line) the same day; `send_batch.py` then stops its
  follow-ups.
- "Stop", "unsubscribe" or any complaint: add the address (and the domain if they ask) to
  `<state>/suppression.csv` the same day, with the reason and date. Never remove a line.
- A bounce: `send_batch.py` adds it to suppression; add bounces reported later by hand. More than 3% bounces or any spam complaint in a batch:
  `gtm.py pause --reason "outbound deliverability"` and alert.
- Measure per play: replies, positive replies and meetings per 100 sent, recorded with
  `gtm.py metric add outbound:<play>:reply_rate …`. Pipeline counts feed `leads_28d`.

## Creators

Creator pitches (channel `creators`) use the same machinery: a shortlist of creators whose audience
matches the ICP (from `../customer-research` attention evidence), a research pack per creator, a
short pitch with the disclosure terms stated up front, a batch, approval, then send. Any paid or
gifted deal needs the creator to disclose it (FTC); put that in the pitch.

## Don't

- Don't buy lists, scrape personal emails, or email anyone whose address isn't verified.
- Don't send from the product's main domain. Setup and warmup: `references/deliverability.md`.
- Don't send to a consent-only country, a suppressed address, or an account inside its cooldown.
- Don't mention a customer, number or result that isn't in the claims ledger.
