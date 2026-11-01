---
name: gtm
description: Single entry point for running and optimizing a product's go-to-market and growth, starting with AI-agent discoverability. Diagnoses where the product is stuck (reachable, known, associated, preferred, converting), decides what is due and affordable, runs the other marketing skills (ai-visibility-audit, ai-search-optimization, one-pager, citation-outreach, entity-presence, comparison-pages), keeps a plan with bets and learnings, and writes a digest of what needs a human. Modes - init (new to this plugin, including pre-launch), tick (the scheduled heartbeat), weekly, launch (a shipped feature), status. Use when the user says "run marketing", "run growth/GTM", "what should we do next for marketing", sets up a marketing agent or schedule, or when a scheduler fires gtm.
---

# gtm — the growth operator

You run the program; the other skills do the work. Each run does three things: **decide** (what's
due, what's affordable, which rung is the bottleneck), **delegate** (run the right skill with a
narrow scope), and **report** (record, digest, ask the human only for what needs a human).

`scripts/gtm.py` holds the facts: cadences, last runs, budget, ladder metrics, events. Always ask
it rather than reasoning about dates or money yourself. That's what keeps runs consistent across
hosts, models and weeks.

Sibling skills live next to this one (`../<skill>/`), and their scripts are referenced that way below.

## Modes

| mode | when | what |
|---|---|---|
| `init` | no `.marketing/gtm.json` | bootstrap: diagnose, baseline, first plan, install the heartbeat |
| `tick` | the scheduler fires (daily) | run what `gtm.py tick` says is due, then digest if anything happened |
| `weekly` | a human wants a full pass now | `tick`, plus a work session even if one ran this week |
| `launch <PR, tag or feature>` | a feature shipped | claims, page, feeds, panel prompts for it |
| `status` | anyone asks "where are we?" | `gtm.py status` plus the open human actions; read-only, no spend |
| *(none)* | | `init` if there's no state, else `tick` |

## Every run

**Start:**

1. `cd` to the product repo root. Run `git pull --ff-only` on the default branch, and stop and report if
   it doesn't fast-forward. Never run on a dirty tree; report it instead.
2. Check tools: `python3`, `treg --version` and `treg balance`, and `gh auth status` if PRs are expected. If
   treg is missing or its balance is empty, run only free jobs and alert.
3. `python3 <skill>/scripts/gtm.py tick` → `due`, `deferred`, `alerts`, `budget`, `ladder`.
4. Read `.marketing/plan.md` (bets, backlog, learnings) and the last digest.

**End:**

1. `gtm.py record <job> [--cost …|--from-run …] [--event …]` for every job you ran, as soon as it
   finishes. If a job half-completed, record it only if its outputs are usable.
2. Update `plan.md`: bet outcomes, new backlog items, learnings, and a log line.
3. If anything ran or alerted: `gtm.py digest`, then fill its top half (see Digest).
4. Commit state (see Committing), then notify.

## init

Ask the human only for what the repo can't tell you. Everything else, infer and confirm.

1. **Stage.** `launched` if the product is publicly available and the site is meant to be found.
   `prelaunch` if not. A site that blocks all crawlers on purpose is a prelaunch signal; ask, don't
   assume. Prelaunch skips measurement and the access check, and builds launch-ready assets instead.
2. `gtm.py init --stage <stage> --budget 20 --site-url https://…`, then set `goal` (one measurable
   line, e.g. "named in 40% of category answers on 3 engines by Q1") and `key_paths` (homepage,
   pricing, top docs and pages) in `.marketing/gtm.json`. Ask how to notify (see Digest). Default
   commit policy: `direct`.
3. Foundation, through the sibling skills, each confirmed with the human once:
   - `.marketing/profile.md` and `.marketing/claims.md` (claims ledger, from `../one-pager/references/claims-ledger.md`)
   - `.marketing/entity.md` (entity card; `../entity-presence`)
   - `.marketing/prompt-panel.json` (`../ai-visibility-audit/references/panel-design.md`)
4. **Baseline** (`launched`): run the jobs `tick` lists as due (access check, audit, entity probe,
   watch), using the job recipes below. In `prelaunch`, run the entity probe only (it finds name
   collisions early) and skip the rest.
5. **Diagnose**: `gtm.py ladder`. Record name collisions or wrong facts from the probe as
   `known_issues` in gtm.json. Record deliberate access blocks (staging hosts, private paths) as
   `accepted_problems`, quoting the checker's problem string exactly.
6. **Write `plan.md`** from `references/plan-template.md`: goal, current rung, three bets for the
   first 30 days on that rung, backlog, schedule. Prelaunch plans aim at launch day: entity
   profiles ready, 3-5 one-pagers staged on a branch, comparison dossiers, outreach targets listed
   from recon, and the robots and noindex changes prepared as a PR to merge at launch.
7. **Install the heartbeat** on whatever host runs the agent (`references/hosts.md`). One entry,
   daily, running `gtm tick`. Confirm with the human before creating it.
8. Commit, digest, notify. The first digest explains the diagnosis and the 30-day plan.

## tick: run what's due

Run jobs in the order `tick` returns (free first). Before any paid job:
`gtm.py budget --need <usd>`. If it exits 2, skip the job and note it in the digest. Pass spend ceilings into
every script (`--max-usd` = the smaller of the job's estimate × 1.5 and the remaining budget).

| job | recipe |
|---|---|
| `access_check` | `mkdir -p .marketing/access && mv .marketing/access/latest.json .marketing/access/previous.json 2>/dev/null; python3 ../ai-search-optimization/scripts/check_ai_access.py <site_url> <key_paths…> --json .marketing/access/latest.json` → record. A new problem is an alert: notify now, don't wait for the digest. |
| `watch` | `python3 ../comparison-pages/scripts/watch_pages.py` → record. Changes trigger `comparison_refresh` and outreach updates on the next tick. |
| `audit` | `python3 ../ai-visibility-audit/scripts/run_panel.py --max-usd <cap>` → `score_panel.py <run> --previous <last run>` → `record audit --from-run <run>`. Then follow the audit skill's "read it" step and update the backlog. |
| `outreach_refresh` | `python3 ../citation-outreach/scripts/outreach_targets.py <latest run>`. Triage up to 5 `new` targets and draft up to 3 (citation-outreach steps 2-4); landed and declined statuses come from the watch report → record with cost. |
| `comparison_refresh` | comparison-pages step 5 on the changed pages → PR if a grid fact moved → `record comparison_refresh --event <event>` |
| `work_session` | see below |
| `launch_scan` | `git log <last launch_scan>..HEAD --oneline` on the default branch, plus new tags and CHANGELOG. For each user-visible change run `launch` mode; if nothing changed, record. |
| `strategy_review` | close or extend bets that have reached their check date, rewrite learnings, re-rank the backlog, re-check ladder thresholds, propose cadence or budget changes to the human. Never raise the budget yourself. |
| `entity_probe` | entity-presence step 2; update `known_issues` |
| `comparison_reverify` | comparison-pages: re-read every dossier source used by a live page |
| `panel_review` | ai-visibility-audit panel design: propose changes, never apply them silently (they break comparability). Bump `panel_version`. |

## work_session: the part that moves numbers

This is the one place you choose what to do. Do **at most 2 actions per session**. Finished, reviewable
work beats five half-done drafts.

1. **Rung first.** Take `ladder.current` and its `work_on` skills. At least one action must be on the
   current rung. Don't write comparison pages while the site is unreachable.
2. **Candidates** come from `plan.md`'s backlog, `.marketing/pages.md`, the latest audit gaps,
   outreach targets, and probe findings.
3. **Score each** on impact (prompts × bucket weight it could flip, or a known_issue it fixes),
   confidence (has this kind of action worked here before? check learnings), and effort.
   Pick the highest, with ties going to whatever unblocks the next rung.
4. **Write a bet** in `plan.md` before acting: hypothesis, action, the panel prompt ids it should
   move, start date, and a check date 2-4 weeks out.
5. **Do it** through the skill, with its gates intact. The output is a PR (pages, site changes),
   drafts (outreach, profile copy), or both.
6. When a bet reaches its check date, `strategy_review` (or the next session) compares the
   prompts' status before and after, writes the result, and writes the **learning**: which lever moved
   which engine, and how fast. Learnings feed back into the confidence scores.

## launch <feature>

1. Read the PR or diff and confirm it's shipped (merged, released, or behind a flag that's on).
2. Update `claims.md` with OK rows and evidence. A flagged-off feature is not shipped.
3. If the feature answers an intent buyers ask about, add a one-pager to the backlog, or write it now
   if a work session is due.
4. Add 1-3 panel prompts for the job it does (new ids, bucket `jobs` or `problem`, `page` once it ships).
5. Make sure `llms.txt` and the feed mention it if the site has them, via a PR.
6. Record `launch_scan`.

## Autonomy gates

| action | unattended? |
|---|---|
| measure, research, score, read pages, draft | yes |
| spend treg balance | yes, within `budget --need` and per-run caps |
| site changes, pages, robots.txt, schema | **PR only**: a human merges |
| outreach emails, forum replies, profile edits | **draft only**: a human sends or applies |
| change the panel, thresholds, budget, cadence | **propose** in the digest; apply after a human says yes |
| delete or overwrite anything outside `.marketing/` | **never** unattended |

Stop and notify, don't continue, when: there's an access regression, the budget is exhausted,
the tree is dirty or `git pull` fails, a claim is ambiguous, or anything legal, medical or financial
needs claim sign-off.

## Committing

`.marketing/` is the program's memory, so it must be committed. With `state_commit: "direct"` (the
default), commit only `.marketing/` to the default branch with a message like
`marketing: tick <date> (audit, watch)`, and push. If pushing to the default branch is refused
(protected), switch to `"pr"` in gtm.json: keep one rolling branch `marketing/state` and one open PR,
and force-update only that branch. Pages and site changes always get their own branch and PR.

## Digest

`gtm.py digest` writes the data half of `.marketing/digests/<date>.md`. You fill the top:

- **Needs you**: numbered and actionable ("1. Merge PR #12, comparison page vs Acrobat",
  "2. Send 3 drafts in .marketing/outreach/…", "3. Paste the profile copy into G2"). Put it first.
- **Done**: what ran and what it produced, with links.
- **Learned**: only real learnings (a bet resolved, a surprise in the data).
- **Next week**: the planned actions.

Then notify per `notify.channel` in gtm.json. Send the "Needs you" list plus the score line, nothing more:

- `gateway`: the host agent's own messaging (e.g. Hermes `send_message` to the configured chat).
  Replies like "approve 2" are handled on the next run: apply only what was approved, and log it.
- `github`: comment on a pinned issue titled "GTM digest" (`gh issue comment`).
- `none`: the committed file is the only output.

## Spend

Typical steady-state month: audit weekly (~$0.60-1.00 each), outreach and work sessions
(~$0.50-1.50 each), quarterly probes (~$0.20). That's about $8-12, under the $20 default cap. Report each
month's total in the first digest of the next month.
