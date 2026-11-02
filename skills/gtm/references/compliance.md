# Compliance

The rules that apply whenever the operator contacts people, publishes endorsements or keeps
personal data. This is a working summary, not legal advice: where a line says "confirm with
counsel", do that before the channel goes past the draft step. Facts checked 2026-11-01.

## Email and messages

| rule | where | what it requires of us |
|---|---|---|
| **CAN-SPAM** | US commercial email | no deceptive headers or subject lines; identify the sender; a valid postal address; a working opt-out honoured within 10 business days; no charge or extra steps to opt out. Applies to B2B email too. |
| **CASL** | messages to or from Canada | consent before sending, express or implied (implied covers, for example, an existing business relationship or a published business address with no "no solicitation" notice, if the message relates to their role). Identify the sender and include an unsubscribe. Confirm the implied-consent basis with counsel before cold outreach to Canada. |
| **GDPR / UK GDPR, ePrivacy / PECR** | people in the EU or UK | a lawful basis for processing (usually legitimate interest for B2B, documented); a privacy notice at first contact; honour objections at once. Rules for email to individuals at corporate addresses differ by country: the UK (PECR) allows B2B email to corporate subscribers with an opt-out; sole traders and some partnerships count as individuals and need consent. |
| **Germany and some other EU states** | cold email to businesses | Germany (UWG §7) treats unsolicited advertising email as unacceptable without prior consent, B2B included. Treat Germany as consent-only. Austria and a few others are similarly strict; confirm with counsel per country before including it in a segment. |
| **CCPA / CPRA** | California residents | disclose collection at or before the point of collection; honour opt-outs of sale or sharing; B2B contact data has been covered since 2023. |

Common to every channel:

- Check the suppression list before every send: unsubscribes, bounces, complaints, "do not contact",
  and existing customers in a dispute. A suppressed address stays suppressed.
- Every message says who sent it and why the recipient is getting it.
- One person, one sequence. Cooldowns (`gtm.py may`) stop the operator contacting the same domain
  or person again inside the window.

## Endorsements, reviews and AI disclosure

- **FTC Endorsement Guides** (16 CFR Part 255): disclose any material connection (payment, free
  product, employment, affiliate commission) clearly and close to the claim. Applies to creators,
  affiliates and employees posting about the product.
- **FTC rule on fake reviews and testimonials** (in force from October 2024): no fake or AI-written
  reviews presented as real customers, no buying positive or suppressing negative reviews, no
  undisclosed insider reviews, no fake social-proof indicators. Civil penalties apply per violation.
- **AI presenters and synthetic media**: disclose them. Platforms require labels for realistic AI
  content (TikTok, YouTube and Meta each have one; confirm current rules before publishing). Never
  use a real person's likeness or voice without written permission. In the EU, the AI Act's
  transparency duties for deepfakes apply from August 2026; confirm with counsel for EU campaigns.
- Testimonials and case studies need the customer's written permission and must reflect typical
  results or say they don't.

## Platform automation

Read each platform's terms before automating anything there. As of 2026-11-01:

- LinkedIn, X, Reddit and most forums prohibit automated posting, scraping outside their APIs, and
  undisclosed promotional accounts. The operator drafts; a human posts from their own account.
- Review sites (G2, Capterra, Trustpilot, app stores) prohibit incentivised reviews unless the
  platform's own program allows them, and review gating (asking only happy customers).
- Ad platforms require accurate claims and disclosures, and restrict regulated categories (finance,
  health, legal). The `regulated` profile field tightens what the operator drafts.

## Personal data

- Collect the minimum: name, work email, role, company, the source where you found them, and why
  they were contacted.
- Contacts live only in the state store. Never in the product repo, never in PostHog event
  properties, never in commit messages, logs or the digest. Logs and the digest use IDs or hashes.
- Retention: delete a contact 180 days after the last contact unless they replied and asked to stay
  in touch. Delete at once on request.
- Record where each contact's data came from (the treg endpoint or page), so an access or deletion
  request can be answered.
- Enrichment providers must be ones the team is allowed to use for this purpose; check the
  provider's terms for marketing use.
