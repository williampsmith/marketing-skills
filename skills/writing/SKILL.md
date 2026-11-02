---
name: writing
description: The shared writing standard for every piece of marketing copy the plugin produces - pages, comparison pages, outreach pitches, profile copy, posts, emails, ad and video scripts, announcements. Two modes - write (apply the gates while drafting) and guard (check existing copy with scripts/claims_guard.py against the claims ledger, AI-tell lists, numbers and competitor comparisons). Use whenever another skill drafts copy, or when the user asks to "check this copy", "is this claim OK", "edit this page", "make this sound less like AI", or "review the site copy for claims". Facts come from the claims ledger and positioning from product-context; this skill decides whether the words are allowed and good.
---

# Writing

Every sentence the plugin publishes passes the same gates, whichever skill drafted it. Two inputs
make that possible:

- `<state>/claims.md`: what the product demonstrably does, with qualifiers (method:
  `../one-pager/references/claims-ledger.md`).
- `<state>/product-context.md`: buyer, voice, customer language, competitors (`../product-context`).

`<state>` is `python3 ../gtm/scripts/gtm.py where` → `"root"`.

## Modes

| mode | when | output |
|---|---|---|
| `write` | another skill is drafting, or the user asks for new copy | a draft that passes the gates, plus a short claims list (sentence → ledger row) |
| `guard` | copy exists: a page, a PR diff, a pitch, a site section | the guard report, then an edited version with every failure fixed or removed |

## The gates

Apply them in order. A failed gate is fixed before moving on; it is never waived silently.

### 1. Claims

- Every product claim maps to an **OK** row in `claims.md`, and carries that row's qualifier. A
  claim with its qualifier dropped is a different claim.
- No row, no claim. Rewrite the sentence around what the ledger supports, or ask the human for
  evidence and add the row with it (never the other way round).
- Comparisons with a named competitor need evidence about the competitor too: their current docs
  or pricing page, dated. Without it, describe your own behaviour and let the reader compare.
- Regulated categories (`profile.regulated` is `light` or `heavy`): claims about security,
  compliance, health, money or legal effect go to a human before publishing, even with a row.

### 2. Information gain (new pages only)

Before writing a new page, read what currently ranks or gets cited for its question and write one
sentence: what will this page have that none of them do? Original data, a real example from the
product, a working tool, a clearer answer, a constraint they skip. If you can't write the sentence,
don't write the page; put the question in the digest instead.

### 3. Numbers and quotes

Never invent a statistic, quote, customer, review, price, benchmark or date. Every number traces
to the ledger, a cited external source (URL, date read), or the product's own measured data with
its source. Round only in the cautious direction.

### 4. Voice and language

Use the voice attributes and the verbatim customer language in product-context.md. Name things the
way buyers do. Answer first, then explain. Short paragraphs. Specific nouns over adjectives.

### 5. AI tells

Apply `references/ai-tells.md`: banned phrases out, capped phrases within their caps, and the
patterns no script catches (reflex contrasts, triplets, fake suspense, hedge stacks).

### 6. Disclosure

- AI-generated people, voices or testimonials are labelled as such, and platform AI-content labels
  are switched on where the platform has them.
- Paid, gifted or affiliate relationships are disclosed in the content itself (FTC endorsement
  rules), not only in a profile bio.
- Testimonials and logos only with permission, and only typical results, or the result labelled as
  not typical.

## Guard mode: the script

```bash
python3 scripts/claims_guard.py <file|-> [--json] [--competitor "Name"]...
```

It splits the copy into sentences and flags those with numbers, risky terms (superlatives and
absolutes such as "fastest", "only", "100%", "secure", "free"), a competitor named next to a
comparative word, or a banned phrase. Each claim-like sentence is matched against the ledger's OK
rows: `covered` (with the row and its qualifier) or `unsupported`. Capped phrases used too often
are listed as `overused`. Exit 1 means at least one unsupported or banned sentence.

Competitor names come from `--competitor` and the "Alternatives" line of product-context.md.

**What it can't do.** It catches candidates; it doesn't prove anything. It can't judge meaning,
misses claims phrased without numbers or risky words, and word overlap can match a row that says
something else. Read every flagged sentence, and read the rest of the copy for claims the script
missed.

## Guard mode: the procedure

1. Run the script on the copy (for a PR, on each changed page).
2. For each `unsupported`: rewrite to a ledger row, add the qualifier, or cut. For `covered`:
   confirm the row really says this and the qualifier is present.
3. For `banned` and `overused`: rewrite with the swaps in ai-tells.md.
4. Read the copy end to end for the gates the script can't check (information gain, voice,
   disclosure, unsupported claims without trigger words).
5. Re-run the script. It must exit 0 before the copy goes into a PR or a draft for sending.
6. In the PR description or draft note, list each claim and its ledger row.

## Hand-off to other skills

Drafting skills call this one at the end of their drafting step and include the guard result in
what they hand the human: one-pager and comparison pages in the PR, citation-outreach and other
outreach in the draft file, entity-presence in the profile copy, launch announcements in
`<state>/launches/`.
