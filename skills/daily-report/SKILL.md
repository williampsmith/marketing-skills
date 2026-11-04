---
name: daily-report
description: The growth operator's daily report for a team chat channel (Slack through Hermes, or any chat the host can post to) - what moved in the funnel and why it might have, what the operator shipped, what's waiting on a human - with 1-3 charts drawn for the day's finding in D3 and rendered to PNG, links to PostHog, and one message per approval so each can be answered with a reaction. Numbers come from a computed dataset (weekly readings with normal ranges and a Poisson test, funnel rates with intervals, bets against expectations), never typed by hand. Use when gtm's daily_report job is due, or when someone asks for a report, a chart, "how are we doing", "why did X drop", or a visual of any marketing number.
---

# Daily report

A short, honest read of the numbers, posted where the team already talks. It earns its place by
saying what PostHog's charts don't: whether a change is real or noise, what the operator did that
might explain it, and what happens next. Most days the true answer is "nothing unusual"; say that in
one line and keep the report short.

`<state>` is the directory `python3 ../gtm/scripts/gtm.py where` prints (field `root`). Run scripts
from the product repo root, by absolute path.

## Requires

- `<state>/gtm.json` (gtm init). PostHog connected for daily series (`../measurement`); without it
  the report uses the store's metrics only, and says so.
- For charts: Node 26 (LTS; 25+ works), which lets the renderer cut chart code off from the network,
  and, once per install, `npm ci` in `scripts/render/`. Fonts: the host's system fonts, or put `.ttf`/`.otf` files
  in `scripts/render/fonts/` or `$RENDER_FONT_DIR` (a bare Docker image often has none, and text
  then renders as nothing: look at the first PNG). Without Node, post the report without charts and
  say why once.

## Steps

1. **Data**: `python3 scripts/report_data.py build` → `<state>/reports/daily/<date>/data.json` and a
   headline (one line per reading). It covers the twelve weeks ending yesterday. `notes` lists what
   it couldn't get (PostHog not connected, a stage query that failed); repeat those in the report.
2. **Read it.** Decide the one to three things worth saying, in this order: anything
   `unusually_high` or `unusually_low`; a funnel step whose interval sits wholly below its floor
   (`vs_floor: below`); a bet at or past its check date; what shipped (`actions`). For each, the
   likely explanation from `actions` and the store (a launch, a page, a news reaction, an outreach
   batch), worded as a possibility unless a bet's method supports more, and what the operator will
   do about it. Rules for the reading are below.
3. **Charts**, one per finding, at most three (`references/charts.md`). Start from a chart in
   `<state>/reports/charts/` or `scripts/render/charts/`, or write one for the data. Render each:
   `node scripts/render/render.mjs --chart <chart.mjs> --data <data.json> --out <dir>/<name>.png
   [--opts '{"series":"daily:signup","label":"Signups"}']`. Then **look at every PNG** (read the
   image): overlapping labels, clipped text, missing fonts, an empty plot. Fix and re-render. Save a
   chart you wrote that worked to `<state>/reports/charts/<name>.mjs` for later days.
4. **Message**, in the layout in `references/slack.md`: the headline sentence, the findings with
   their numbers and charts, what shipped with links, PostHog links (`data.links`), then "Needs you".
5. **Post.** On Hermes the cron job's final answer is delivered to the channel; attach each chart
   with a line `MEDIA:<absolute path to the png>`. Post each `needs_human` item and each "Needs you"
   ask as **its own message** (Hermes `send_message` to the same channel), so each gets its own
   thread and reactions. Elsewhere, use the host's messaging; with no chat, write the report to
   `<state>/reports/daily/<date>/report.md` and link it in the digest.
6. `gtm.py record daily_report`.

In `ask` mode (someone asks for a chart or "how are we doing"), do steps 1-4 for their question and
answer in the thread; don't post a second daily report.

## Reading rules

- **Every number comes from data.json**, at the precision shown. The renderer fails a chart whose
  text shows a number that isn't in the data (axis ticks aside); treat a failure as a sign you're
  inventing, not as an obstacle. If the story needs a number the data layer doesn't compute, say so
  and propose adding it to `report_data.py`; don't compute it in your head.
- **Verdicts are the data layer's.** `unusually_high`/`unusually_low`: say it's up or down and by
  how much. `normal`: "within its normal range", with no direction words, even if the number is
  higher than last week. `too_little_data`: don't describe a change at all; say the counts are too
  small to read yet, and what count would be.
- **Causes are hypotheses.** "Signups doubled the week the comparison page shipped" is fine;
  "the comparison page doubled signups" needs a bet whose method supports it (A/B, holdout).
  Name the other things that happened that week too.
- **Bets**: report progress against `expected` until the check date; call a result only when the
  bet is closed (`gtm.py bet close`).
- **No vanity.** Don't report a number because it went up. Report it because it changes what the
  operator or the team should do.
- Keep the whole message readable in under a minute.

## Output

- `<state>/reports/daily/<date>/data.json`, the charts (`.png` and the `.svg` beside each), and the
  message as posted (`report.md`).
- `<state>/reports/charts/`: the chart library you build up.
