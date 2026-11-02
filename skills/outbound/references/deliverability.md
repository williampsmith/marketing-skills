# Deliverability and the sending setup

A human sets this up once, before any channel is granted approve-to-send. The agent checks it and
reports gaps; it never changes DNS or mailbox settings itself.

## The sending domain

- A separate domain for outbound (e.g. `try<product>.com` or `<product>mail.com`), never the main
  domain, so a mistake can't hurt the main domain's reputation or its transactional mail.
- A shared inbox on that domain (`hello@…`) that a human reads every working day. Replies go there.
- The domain's site redirects to the main site, so recipients who look it up land somewhere real.

## Authentication checklist

| record | what to check |
|---|---|
| SPF | one TXT record listing only the sending provider; ends in `-all` or `~all` |
| DKIM | the provider's selector published; signatures pass on a test message |
| DMARC | `_dmarc` TXT present; start at `p=none` with reports, move to `quarantine` once clean |
| MX | the domain receives mail (replies and bounces must arrive) |
| PTR/HELO | handled by the provider; confirm in their setup page |

Check with a test message to a mailbox you control and read the authentication results header.

## Warmup and caps

- Warm a new inbox for 2-4 weeks before any outbound: small daily volume of real conversations,
  rising slowly. Follow the provider's guidance; confirm the current recommendations with them.
- Start the channel's `daily_cap` low (20 per inbox) and raise it only after two weeks with bounces
  under 2% and no complaints.
- Plain-text messages, one link at most, no tracking pixels, no attachments.

## Environment for `send_batch.py`

`SMTP_HOST`, `SMTP_PORT` (465 for SSL, otherwise STARTTLS), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
(an address on the sending domain). They live in the host's environment or secret store, never in
the state store or a repo.

## Watch

- Bounce rate per batch (stop and alert above 3%).
- Spam complaints (any complaint pauses the channel until a human looks).
- Replies saying the message reached spam: check authentication again before the next batch.
