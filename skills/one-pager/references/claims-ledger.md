# The claims ledger

`.marketing/claims.md` is the single list of what marketing may say about the product. Every
skill in this plugin reads it. It is built from the repo, because code is the ground truth and
roadmaps, decks and old strategy docs are not.

## Building it

1. Read the product's own description: README, CLAUDE.md or AGENTS.md, docs, site copy, and the app's
   in-app help.
2. For each capability those describe, find the code that implements it and any test that pins
   it. A capability that exists only in a spec, roadmap or branch is **not shipped**.
3. Look for caveats in the code: silent fallbacks, feature flags, platform gates, "best effort"
   paths, swallowed exceptions, TODOs on the claimed path.
4. Check memory files and docs for earlier claim decisions (e.g. a claims memory or a marketing
   doc) and carry them forward. Point out where they conflict with the code.
5. Ask the user about anything you can't verify from the repo (certifications, audits, customer
   counts, pricing).

## Format

```markdown
# Claims ledger — <product> — verified <date> against <commit>

## OK to claim
| claim (as it may appear in copy) | evidence | notes / required qualifier |
|---|---|---|
| Runs entirely on the device; documents are not uploaded | python/server.py binds 127.0.0.1 only; no outbound calls in export path | except license check (no document data) |
| Verifies every export with two independent parsers and refuses to save on failure | verify_export() in pdf_redactor.py; tests/test_export_self_check.py | covers boxed areas only |

## Never claim (not shipped / not true)
| claim | why |
|---|---|
| Automatic PII detection | not in the shipping code path |
| "100% unrecoverable" | no independent audit; OCR find is best-effort |

## Caveats every page must respect
- …

## Open questions for a human
- …
```

## Rules of use

- Copy a claim's wording and its qualifier together. Dropping the qualifier makes it a new claim.
- Comparative claims ("faster than X", "unlike X") need evidence about X too: their current docs or
  a test you can describe. Without that, describe your own behavior and let the reader compare.
- Re-verify the ledger when the default branch moves past a release. Record the commit you checked.
- When a page needs a claim that isn't in the ledger, add it with evidence or drop it. Never
  write the claim first and look for evidence afterward.
