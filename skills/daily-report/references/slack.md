# The report in Slack

Slack formatting (mrkdwn): `*bold*`, `_italic_`, `<https://url|link text>`, `•` for bullets, `>` to
quote. No Markdown headings or tables; they show as raw characters. Keep each message under about
40 lines.

## The report message

```
*Growth report, Tue 3 Nov* · <https://us.posthog.com/project/12345|PostHog>
Signups are up: 51 this week against a usual 26. Nothing else moved outside its normal range.

*What moved*
• *Signups* 51 vs a usual 26 (+96%; normal range 22–30). The same week: the batch-export launch post
  and the comparison page (<https://github.com/acme/site/pull/41|PR #41>). Too early to say which.
• *Activation* 18.4% of signups, below its 30% floor even allowing for noise (95%: 13.3–25.0%).
  Focus stays on conversion; Thursday's work session takes the onboarding checklist.

*Shipped*
• <https://github.com/acme/site/pull/41|Comparison page vs Foo> (merged Mon)
• 3 outreach drafts for the security-press batch (waiting on you, below)

*Too early to read*: visits from AI answers (about 2 a week).
_Spend $6.40 of $20 this month. Focus: conversion (rung `activating`)._
MEDIA:/home/agent/.marketing/acme-site/reports/daily/2026-11-03/signups.png
MEDIA:/home/agent/.marketing/acme-site/reports/daily/2026-11-03/funnel.png
```

The `MEDIA:` lines are Hermes's attachment syntax: each uploads the file to the same channel. Put
them last.

## One message per item waiting on a human

Each gets its own message so it gets its own thread and reactions:

```
*Needs you · 1 of 2* — approve outreach batch `security-press-1` (3 emails to editors)
Drafts: <state>/sends/security-press-1/drafts.jsonl (first one quoted below)
> Subject: How courts keep finding text under black boxes …
React ✅ to approve all 3 · ❌ to drop · or reply in the thread (e.g. "approve 2", "change the subject")
```

## Applying a reply or reaction

The gateway tells you who reacted or replied (their Slack user id) and on which message. Apply it
under gtm's **Approvals** rules:

- Only a reaction or reply **on that item's message**, by a person (not a bot), counts. ✅
  (`white_check_mark`) approves the whole item as described; ❌ (`x`) declines it; anything else is
  not an approval. A reply's words set the scope ("approve 2" approves the first 2).
- Record it: `gtm.py approve security-press-1 --count 3 --quote ":white_check_mark: on Needs you 1
  of 2" --approver slack:U0123ABC --source <permalink of the item message>`. Slack permalinks look
  like `https://<workspace>.slack.com/archives/<channel id>/p<ts without the dot>`.
- Answer in the thread with what you did ("Approved 3; they go out in the next send window").
- A batch approval, grant or paid change arriving while a scheduled run is working waits for a
  human-present turn (see gtm). A reaction or reply starts a new conversation turn on Hermes, which
  is not a scheduled run, so it is applied there.
