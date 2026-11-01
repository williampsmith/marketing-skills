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
| Files are processed on your device and never uploaded | src/server.ts binds to localhost only; no network calls in src/export/ | except the license check, which sends no file data |
| Checks every export and refuses to save one that fails | checkExport() in src/export/verify.ts; test/export-verify.test.ts | covers only the areas the user marked |

## Never claim (not shipped / not true)
| claim | why |
|---|---|
| Automatic detection of personal data | only on a feature branch, not shipped |
| "100% secure" | no independent audit |

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
