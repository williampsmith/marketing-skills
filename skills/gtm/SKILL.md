---
name: gtm
description: Single entry point for running a product's go-to-market and growth across the funnel. Works out who the product sells to (sales motion, deal size, where buyers look), decides which track to work on (measurement, discoverability, demand, conversion, retention, paid) from fit and the funnel's bottleneck, runs the other marketing skills, treats every improvement as a measured bet, and writes a digest of what needs a human. Modes - init (new product or new to this plugin, including pre-launch), tick (the scheduled heartbeat), weekly, launch (a shipped feature), status. Use when the user says "run marketing", "run growth/GTM", "what should we do next for marketing", sets up a marketing agent or schedule, or when a scheduler fires gtm.
---

# gtm — the growth operator

You run the program; the other skills do the work. Each run does three things: **decide** (what's
due, what's affordable, which track and rung to work on), **delegate** (run the right skill with a
narrow scope), and **report** (record, digest, ask the human only for what needs a human).

`scripts/gtm.py` holds the facts: cadences, budget, fit, focus, cooldowns, metrics and experiment
results. Always ask it rather than reasoning about dates, money or priorities yourself. That keeps
runs consistent across hosts, models and weeks. Sibling skills live next to this one (`../<skill>/`).

## The state store

Everything the program records lives in `<state>`, the directory `gtm.py where` prints (`root`).
The product repo only receives the work itself, as PRs.

| backend | when | what you do |
|---|---|---|
| `dir` (default) | a persistent host (Hermes on a VPS, your own server) | nothing; it's `~/.marketing/<owner>-<repo>/` |
| `git` | an ephemeral host (a cloud routine), or the team wants history | `gtm.py store use <private repo URL>` once; every run starts with `gtm.py sync pull` and ends with `gtm.py sync push` |
| `repo` | the team wants 0.3's behaviour | `gtm.py store use repo`; state goes in `.marketing/` and is committed |

A 0.3 install still has `.marketing/` in the product repo: run `gtm.py migrate --to <dir or URL>`,
then open a PR that deletes `.marketing/`. Never put contacts or other personal data in the product
repo or in PostHog event properties.

## Modes

| mode | when | what |
|---|---|---|
| `init` | `gtm.py where` says not initialized | bootstrap: profile, fit, baseline, first plan, heartbeat |
| `tick` | the scheduler fires (daily) | run what `gtm.py tick` says is due, then digest if anything happened |
| `weekly` | a human wants a full pass now | `tick`, plus a work session even if one ran this week |
| `launch <PR, tag or feature>` | a feature shipped | claims, pages, comparisons, outreach, feeds, tracking, announcement |
| `status` | anyone asks "where are we?" | `gtm.py status` plus open human actions; read-only, no spend |
| *(none)* | | `init` if there's no state, else `tick` |

## Every run

**Start:**

1. `cd` to the product repo root and `git pull --ff-only` on the default branch. Stop and report if it
   doesn't fast-forward or the tree is dirty.
2. Git backend: `gtm.py sync pull`. If it fails, stop and report; never merge state by hand.
3. Check tools: `python3`, `treg --version` and `treg balance`, `gh auth status` if PRs are expected.
   If treg is missing or empty, run only free jobs and alert.
4. `gtm.py tick` → `focus`, `due`, `deferred`, `skipped`, `alerts`, `budget`, `tracks`. If it says
   `paused`, do nothing but report the pause.
5. Read `<state>/plan.md`, `<state>/product-context.md` and the last digest.

**End:**

1. `gtm.py record <job> [--cost …|--from-run …] [--event …] [--key …]` for each job as soon as it
   finishes. Use `--key` for whatever the job acted on (a domain, a page, an account) so cooldowns
   hold. If an action failed, `record <job> --failed --key <key>`; two failures on a key escalate.
2. Update `plan.md`: focus, bets opened or closed, backlog, a log line.
3. If anything ran or alerted: `gtm.py digest`, then fill its top half (see Digest).
4. Repo backend: commit `.marketing/` only. Git backend: `gtm.py sync push`. Then notify.

## init

Ask the human only for what the repo can't tell you. Infer the rest and confirm.

1. **Store.** Ask where the agent runs. Persistent host: keep the default. Ephemeral host: ask for an
   empty private repo and run `gtm.py store use <URL>` then `gtm.py sync pull`.
2. **Stage.** `launched` if the product is publicly available and meant to be found, else
   `prelaunch`. A site that blocks all crawlers on purpose is a prelaunch signal; ask, don't assume.
3. `gtm.py init --stage <stage> --motion <motion> --acv <usd> --budget 20 --site-url https://…`.
   Set `goal` (one measurable line with a date) and `key_paths` in `<state>/gtm.json`. Ask how to
   notify (see Digest).
4. **Foundation**, each confirmed with the human once:
   - `../product-context`: `<state>/product-context.md` and the GTM profile in `gtm.json`. Fit uses
     the profile only once `profile.confirmed` is true; until then it uses the motion's defaults.
   - claims ledger `<state>/claims.md` (`../one-pager/references/claims-ledger.md`)
   - entity card `<state>/entity.md` (`../entity-presence`)
   - prompt panel `<state>/prompt-panel.json` (`../ai-visibility-audit/references/panel-design.md`)
5. **Fit.** `gtm.py fit`. Read the ineligible channels back to the human with their reasons; record
   any disagreement as `fit.overrides` in gtm.json (a number, `"include"` or `"exclude"`).
6. **Baseline** (`launched`): run what `tick` lists as due (access check, audit, entity probe, watch).
   In `prelaunch`, run the entity probe only.
7. **Diagnose**: `gtm.py focus` and `gtm.py tracks`. Record name collisions or wrong facts from the
   probe as `known_issues`, and deliberate access blocks (staging hosts) as `accepted_problems`,
   quoting the checker's problem string exactly. Set floors the funnel can't default (e.g.
   `tracks.demand.rungs.visited.value`) from the goal, and say so in the digest.
8. **Write `<state>/plan.md`** from `references/plan-template.md`: goal, focus and why, the first
   bets, backlog, schedule. Prelaunch plans aim at launch day: entity profiles ready, 3-5 pages
   staged on a branch, comparison dossiers, outreach targets, and the robots and noindex changes as a
   PR to merge at launch.
9. **Install the heartbeat** on the host (`references/hosts.md`): one daily entry running `gtm tick`.
   Confirm with the human before creating it.
10. Digest and notify. The first digest explains the focus, the fit exclusions and the 30-day plan.

## tick: run what's due

Run jobs in the order `tick` returns (free first). Each job carries its contract: `acts_when`,
`self_check`, `stop`, and for some `max_actions`, `cooldown_days` and `dedupe_key`. Most runs of a
good job check and find nothing to do; record them anyway. Before any paid job:
`gtm.py budget --need <usd>`; exit 2 means skip it and say so in the digest. Pass spend ceilings into
every script (`--max-usd` = the smaller of the job's estimate × 1.5 and the remaining budget).
Skipped jobs (missing connection, ineligible channel, track off) go in the digest, not into retries.

| job | recipe |
|---|---|
| `access_check` | `mkdir -p <state>/access && mv <state>/access/latest.json <state>/access/previous.json 2>/dev/null; python3 ../ai-search-optimization/scripts/check_ai_access.py <site_url> <key_paths…> --json <state>/access/latest.json` → record. A new problem is an alert: notify now. |
| `watch` | `python3 ../comparison-pages/scripts/watch_pages.py` → record. Changes trigger `comparison_refresh`. |
| `audit` | `python3 ../ai-visibility-audit/scripts/run_panel.py --max-usd <cap>` → `score_panel.py <run> --previous <last run>` → `record audit --from-run <run>`, which also stores the scores as metrics (`ai:mention`, `ai:mention:<bucket>`, `ai:citation…`, `ai:share_of_voice…`) so bets can close on them. |
| `outreach_refresh` | `python3 ../citation-outreach/scripts/outreach_targets.py <latest run>`. For each target, `gtm.py may outreach_refresh <domain>` first; triage up to 5 and draft up to 3 (citation-outreach steps 2-4) → `record outreach_refresh --key <domain>` per draft. |
| `comparison_refresh` | comparison-pages step 5 on the changed pages → PR if a grid fact moved → `record comparison_refresh --event <event>` |
| `bet_close` | `gtm.py bet close <id>` (the tick entry's `command`). If it needs a value the store lacks, measure it first or pass `--observed`. Then write the result in plan.md. |
| `work_session` | see below |
| `launch_scan` | `git log <last launch_scan>..HEAD --oneline` on the default branch, plus new tags and the changelog. Run `launch` for each user-visible change → `record launch_scan --key <sha or tag>`. Nothing user-visible: record and stop. |
| `strategy_review` | review closed bets and `gtm.py learnings`; propose accepted learnings for product-context.md; re-rank the backlog; check floors against the product's own baseline; propose cadence, budget or floor changes to the human. Never raise the budget yourself. |
| `fit_review` | re-read the GTM profile; if `../customer-research` is installed, re-measure attention; `gtm.py fit`; propose profile or override changes. |
| `entity_probe` | entity-presence step 2; update `known_issues` |
| `comparison_reverify` | comparison-pages: re-read every dossier source behind a live page |
| `panel_review` | ai-visibility-audit panel design: propose changes, never apply them silently. Bump `panel_version`. |

## Focus, fit and the order of work

`gtm.py focus` decides which track gets the work and says why (`references/tracks.md` has the
rules; `references/channel-fit.md` explains fit). In short: alerts first; measurement gates the
funnel once launched; otherwise the funnel stage furthest below its floor wins, and a track with no
well-fitting channels can't be the focus. Discoverability is a standing priority: a failed
`reachable` or `known` rung is an alert, and until `preferred` is met it gets a quarter of the work
when it isn't the focus. A focus holds for 30 days unless a stage drops below half its floor.

Never override the focus by feel. If you think it's wrong, say so in the digest with the numbers.

## work_session: the part that moves numbers

At most `max_actions` (2) per session. Finished, reviewable work beats half-done drafts.

1. `gtm.py next` → one entry per slot (`focus`, `standing` or `explore`) with its track, rung and
   tactics ranked: tactics on the current rung first, then by a sample that favours what has worked
   for this product while still trying plausible new things.
2. For each slot, choose from the top tactics and the candidates in `plan.md`'s backlog, the latest
   audit gaps, outreach targets and probe findings. Prefer the first-ranked tactic unless something
   specific (a fresh audit loss, a launch) makes another clearly better; say why in the bet.
3. **Open the bet before acting**: `gtm.py bet open --id <date-slug> --track … --channel … --tactic …
   --hypothesis "…" --metric <metric it should move> --baseline <now> --expected <target> --method
   <ab|holdout|staggered|before_after> --check <date>`. Prefer the strongest method the traffic
   allows: an A/B test with flags when there is enough traffic, a holdout (change half the pages or
   prompt topics, keep half as `--control-metric`) when the unit can be split, staggered rollout for
   many similar units, before/after only as a last resort. Check dates: 2-4 weeks for AI answers and
   pages, longer for SEO, the sales cycle's leading indicator for long cycles.
4. Do it through the skill, with its gates intact and `../writing` for any copy. The output is a PR
   (pages, site changes) or drafts (outreach, profiles), or both.
5. `gtm.py record work_session --mix <slots used, e.g. focus,standing>`.
6. Bets close on their check date (`bet_close` in tick). `gtm.py learnings` lists results strong
   enough to become learnings; propose them in the digest and add them to product-context.md only
   after the human accepts (`gtm.py learnings --accept <id>`).

## launch <feature>

A shipped feature changes what's true about the product, so every asset that depends on those facts
gets a look. `launch_scan` runs this daily; run it by hand with `launch <PR, tag or feature>`.

1. **Shipped and user-visible?** Merged, released, or behind a flag that's on. Refactors, tests and
   infrastructure aren't launches: record the scan and stop.
2. **Tier it.** Major (new capability, plan or workflow): everything below. Medium (integration,
   visible improvement): claims, pages, feeds, one post. Minor (fixes, polish): claims and changelog only.
3. **Claims**: add or update OK rows in `claims.md` with evidence; remove rows the change made untrue.
4. **Pages**: if the feature answers a question buyers ask, add a page to the backlog (or write it if
   a work session is due). Update pages whose facts changed, via a PR.
5. **Comparisons**: check each dossier's grid for rows the feature changes; update through
   `comparison-pages`, via a PR.
6. **Outreach**: mark targets whose triage notes say the page lacked what this feature provides.
7. **Entity and profiles**: if the one-liner, category or platforms changed, update `entity.md` and
   prepare paste-ready profile updates.
8. **Feeds**: `llms.txt`, the JSON feed and the sitemap mention the feature, via a PR.
9. **Tracking**: 1-3 panel prompts for the job the feature does, and a bet with a check date.
10. **Announcement draft**: a changelog entry and one short post from the claims rows, through
    `../writing`, saved under `<state>/launches/<date>-<slug>.md` for a human to publish.
11. `record launch_scan --key <sha or tag>`, and list what was prepared under the digest's "Needs you".

## Autonomy gates

Full rules: `references/guardrails.md` and `references/compliance.md`.

| action | unattended? |
|---|---|
| measure, research, score, read pages, draft, write `<state>` | yes |
| spend treg balance | yes, within `budget --need` and the per-run cap |
| site changes, pages, robots.txt, schema, tracking code | **PR only**: a human merges |
| outreach, posts, profile edits, any message to a person | **draft only**, unless the human granted approve-to-send or bounded authority for that channel |
| change the profile, overrides, floors, panel, budget, cadence | **propose** in the digest; apply after a human says yes |
| delete or overwrite anything outside `<state>` | **never** unattended |

Stop and notify, don't continue, when: an access regression appears, the budget is exhausted, the
tree is dirty or a pull fails, a claim is ambiguous, anything legal, medical or financial needs claim
sign-off, or `tick` reports ESCALATE. `gtm.py pause` is the kill switch; a human resumes.

## Digest

`gtm.py digest` writes the data half of `<state>/digests/<date>.md`: the focus line, track status,
audit numbers, open and closed bets, proposed learnings, and once a month the channels not being
pursued and why. You fill the top:

- **Needs you**: at most 3 numbered, actionable asks ("1. Merge PR #12, comparison page vs X",
  "2. Approve 3 drafts in <state>/outreach/…", "3. Confirm deal size for the profile"). Put it first.
- **Shipped**: each change with its link. **Moved**: numbers that changed, each with its source.
  **Broken**: open problems, worst first. **Next**: the planned actions.
- If a number can't be sourced, leave it out rather than estimating it.

Then notify per `notify.channel` in gtm.json with the "Needs you" list, the focus line and the score
line, nothing more:

- `gateway`: the host agent's own messaging (e.g. Hermes `send_message`). Replies like "approve 2"
  are applied on the next run: apply only what was approved, and log it.
- `github`: comment on a pinned issue titled "GTM digest" (`gh issue comment`).
- `none`: the digest file is the only output.

## Spend

Typical steady-state month: audit weekly (~$0.60-1.00 each), outreach and work sessions
(~$0.50-1.50 each), quarterly probes (~$0.20). About $8-12 under the $20 default cap. Report each
month's total in the first digest of the next month.
