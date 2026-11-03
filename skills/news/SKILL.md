---
name: news
description: Watch current events in the product's category - news, Google News, Hacker News, X and (optionally) federal court filings via CourtListener, all searched through treg - and turn the stories that matter into work - a dated fact added to an existing page, a timely post, or a pitch to the journalist covering it. Keeps a scored, deduplicated queue in the state store, flags sensitive stories, and enforces each outlet's shelf life. Use when gtm's news_watch or news_act job is due, when the user asks "what's in the news we could write about", "newsjacking", "timely content", "react to this story", or to set up the news watch for a product.
---

# News

A story in the category is worth something only when the product's team can say something true and
useful about it that the coverage doesn't. Usually that's the mechanism: how the thing in the
headline actually happened, and how a reader avoids it. The value of a story decays fast for a
reaction post (days), slower for a press pitch (about a week), and hardly at all for a page that
uses it as a dated example.

`<state>` is the directory printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Run
scripts from the product repo root, by absolute path. Drafts pass the `../writing` gates.

## Requires

- treg (CLI) for every source but CourtListener. Without it the sweep can't run; say so in the digest.
- `<state>/product-context.md`, for the category's words and what the product proves.
- Optional: `COURTLISTENER_TOKEN` in the environment (free account at courtlistener.com) for court
  filings. Only federal courts, and only documents someone bought on PACER, so coverage is partial.

## Set up (once)

Build `<state>/news.json` from product-context.md. Keep it small: a handful of queries, each a
phrase a journalist would put in a headline about the problem, not about the product.

```bash
python3 <plugin>/skills/news/scripts/news_watch.py init \
  --query "improperly redacted" --query "redaction failure PDF" --query "unredacted documents released" \
  --term redact \
  --signal unredact --signal "improperly redact" --signal "botched redaction" --signal "sloppy redaction" \
  --signal "copy and paste" --signal "hidden text" --signal "easily recovered" \
  --exclude "redacted version released" \
  --source news --source google_news --source hackernews
```

- **queries** are what's searched; **terms** are the category's words (a story needs one to count);
  **signals** are the phrases that make a story ours and score highest; **exclude** removes false
  friends (unless the story also carries a signal). Terms and signals match at the start of a word
  with any ending, so `redact` covers redacted, redaction and redactions. That example is for a
  redaction tool: "redactions" in the news often means information withheld on purpose, which
  isn't a failure, so the signals do the separating.
- `init` extends the existing config, so you can run it again later. `--source` adds a source and
  `--drop-source` removes one.
- Run `init --source x` when buyers argue about the problem on X. Replies, reposts and posts under
  `x_min_engagement` interactions are dropped, mentions are masked, and posts rank below reporting.
- Run `init --source courtlistener` with `--court-query '"inadvertently filed" unredacted'`-style
  queries for court-record signals (errata, corrected redacted versions, motions to seal or strike).
- `python3 news_watch.py sweep --dry-run` prints every planned search and the worst-case cost. Show
  it to the human before the first real sweep.

## `news_watch` (sensor, every 2 days)

1. `python3 news_watch.py sweep --max-usd 0.10`. It searches each source through treg with a cost
   ceiling per call, groups syndicated copies of a story, drops what it has seen before or what is
   older than `max_age_days`, scores the rest and queues those at or above `min_score` in
   `<state>/news/candidates.jsonl`. The report is `<state>/news/<date>.md`.
2. `gtm.py record news_watch --cost <cost_usd>`.
3. Exit 1 means nothing worked: every search failed, a provider's answer changed shape, or the
   budget let nothing run. Alert in the digest ("news watch is broken"); don't read it as a quiet
   week. Individual errors are listed in the report. A call whose charge treg doesn't report, or that
   fails, counts at its ceiling (`reserved_usd`), so the cap holds either way.

Scores are deterministic (signals, terms, recency, how many outlets, engagement) and explained in each
row's `why`. They rank; they don't decide. You decide in `news_act`. A story that scored too low is
scored again on later sweeps, so one that more outlets pick up can still make the queue.

## `news_act` (when new candidates are queued)

`gtm.py tick` adds this job when the sweep queued something new. Work at most `max_actions` (3)
candidates, best score first: `python3 news_watch.py list`.

For each, **read the story itself** (`treg.web.extract`, free; checked 2026-11-02) before deciding.
A headline match is a lead, not a fact. Then decide, in this order of value:

| decision | when | what you produce |
|---|---|---|
| `refresh` | an existing page explains the mechanism the story shows | a PR adding the story as a dated example, quoted from the primary source, with `dateModified` bumped (the `../content` refresh rules). Never expires |
| `react` | the story is fresh (`react_by` not passed) and the team has a true, useful point the coverage misses | a post draft through `../social` (source: the story URL) for a human to post |
| `pitch` | a journalist is covering it now (`pitch_by` not passed) and the product's team can add expertise, data or a demonstration | a pitch draft through `../citation-outreach` to that journalist, from the byline; press stays at per-batch approval |
| `skip` | anything else, including namesakes and stories where the only honest angle is "buy our product" | nothing |

Record each: `python3 news_watch.py decide <id> --as refresh --page <slug>` (or `react`, `pitch`,
`skip`, with `--note`).

- If reading the story shows it involves deaths, victims, children, abuse or similar and the sweep
  didn't flag it, add `--sensitive`. The flag only ever goes on, and it stays even if the decision is
  refused.
- An undated candidate (`react_by` empty) has no react or pitch window until you read its date from
  the story and pass `--published YYYY-MM-DD`. Then `gtm.py record news_act --event <the job's event>` so the job doesn't
come back until the next sweep queues more.

A `react` or `pitch` after its window is refused: a late reaction is worse than none. Use the
story as a refresh instead.

## Rules for using the news

- **Primary sources only.** Quote the filing, the regulator, the company's own statement, or the
  original report, with a URL and access date. Never a fact you only saw in an aggregator or an AI
  answer.
- **Explain the mechanism, never repeat the leak.** When the story is about exposed information,
  describe how it was exposed and how to avoid it. Never quote, link to or reproduce the exposed
  content itself, even if it's public now.
- **Only what is already public.** Use failures that were reported or acknowledged in the record.
  Don't go looking for new ones in other people's documents.
- **Sensitive stories** (the sweep flags deaths, victims, children, abuse and similar, plus
  `sensitive_extra` in news.json): a refresh that explains the mechanism without naming people is
  fine; a reaction or pitch needs a human's approval quoted (`--quote`), and an unattended run
  can't make that call at all. When in doubt, skip.
- **Vendor-neutral first.** The post or page must be worth reading by someone who never buys. The
  product appears where it honestly fits, in a separate section or a final line, never as the point.
- **No dunking.** Don't mock the people or organisations in the story. Competitors' failures in
  the news are a fact to cite carefully, not a campaign.
- Product claims come from the claims ledger (`../writing`), as everywhere else.

## Output

- `<state>/news.json` (config), `<state>/news/seen.json`, `<state>/news/candidates.jsonl`,
  `<state>/news/<date>.md`.
- Drafts land where their skill puts them (`<state>/social/`, `<state>/outreach/`, a page PR).
- The digest lists what was queued, what was decided and anything waiting on a human.

See `references/sources.md` for endpoints, costs and what each source is good for.
