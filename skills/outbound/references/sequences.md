# Sequences

A sequence is written before the first batch goes out and approved with it. Follow-ups outside an
approved sequence are new messages and need their own approval.

## Shape

| step | when | job |
|---|---|---|
| first touch | day 0 | the signal, the problem it implies, one claim row, a reply-sized ask |
| follow-up 1 | day 4-6, only if no reply | one new thing: a relevant page, a short answer to the likely objection, or a specific example |
| follow-up 2 | day 10-14, only if no reply | a clean close ("I'll leave it here; if X becomes a priority, this is the page") |

Stop at the first reply of any kind, an out-of-office that names a return date (resume after it, in
a new batch), a bounce, or an unsubscribe. Never more than three messages to one person; never a
second sequence to the same account inside its cooldown.

## Writing each step

- Subject: 2-6 words, specific, lower-case is fine. No "quick question", no fake "Re:".
- Open with them, not you: the signal, in their terms.
- One claim row, quoted with its qualifier. No numbers that aren't in the ledger.
- The ask is easy to answer by replying: "worth a look?", "who owns this now?".
- Plain text, no images, no tracked links. One link at most, to a page that answers the question.
- Read it aloud. If it would embarrass the product in a screenshot, rewrite it.

## Example play: hiring signal (self-serve compliance tool)

```
subject: your compliance ops hire
Saw the posting for a compliance operations lead. Teams hiring for that role are usually
redacting by hand while they build the process. <Product> checks every export and refuses to save
one that fails (claims row 2, for the areas the user marked). Worth a look before the new lead
starts?
```

Follow-up 1 adds the one-page answer to "how do we know redaction worked?". Follow-up 2 closes.

## Measuring a play

Per play, after its batches: sent, replies, positive replies, meetings, per 100 sent. Open a bet on
the play (`gtm.py bet open --channel outbound --tactic signal_sequence …`) with the reply rate as
the metric, so plays compete on evidence. Retire a play that stays under half the floor after
200 sends.
