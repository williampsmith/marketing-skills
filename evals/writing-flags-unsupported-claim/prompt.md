---
name: writing-flags-unsupported-claim
description: The writing skill checks draft copy against an inline claims ledger and calls out the unsupported superlative.
tags: [smoke]
runs: 1
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---
Please check this landing-page paragraph against our claims ledger before it goes live, and tell me what has to change.

Claims ledger (OK to claim):

| claim | evidence | qualifier |
|---|---|---|
| Files are processed on your device and never uploaded | src/server.ts binds to localhost only | except the license check, which sends no file data |
| Checks every export and refuses to save one that fails | checkExport() in src/export/verify.ts | covers only the areas the user marked |

Draft paragraph:

> Acme Redact is the fastest redaction tool on the market. Your files are processed on your device and never uploaded, and every export is checked before it is saved.
