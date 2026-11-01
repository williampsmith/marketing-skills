---
name: citation-outreach
description: Get a product mentioned, accurately, on the third-party pages AI answer engines already cite when they recommend competitors - listicles, comparison articles, Reddit and forum threads, review directories, videos. Ranks the exact cited URLs from an ai-visibility-audit run, reads and triages each one, finds the right contact through treg (verified emails only), drafts specific, honest pitches and replies for a human to send, and tracks which pages start naming the product. Use when the user asks for outreach, digital PR, link building for AI search, "get us into the best-X lists", Reddit strategy for AEO, or what to do with the audit's citation targets.
---

# Citation outreach

**Why it works.** For most "which tool should I use" questions, an answer engine searches, reads
5-30 pages and writes down what they agree on. Your own site is one of those pages at most, and an
obviously biased one. When the pages it reads name a competitor and not you, the answer does the
same. The audit shows you exactly which pages those are. Earn an accurate mention on them and
you're in the material the answer is built from. That's PR, except the engine has told you which
outlets matter.

**What this skill will not do.** Fake reviews, sock-puppet accounts, undisclosed posts, paid
placements presented as editorial, or sending messages without a human approving each one. These
are against the FTC endorsement guides and the 2024 fake-review rule, and against platform rules.
Moderators, editors and increasingly the engines themselves discount them anyway. Every message is
honest, disclosed, and useful to the recipient's readers whether or not they name you.

## Requires

- A recent `ai-visibility-audit` run (`.marketing/runs/<date>/answers.jsonl`), plus
  `.marketing/profile.md` and `.marketing/claims.md` (pitches make claims, so the ledger gates them).
- treg for reading pages (free), contact finding (paid, verified), and Reddit and backlink lookups.

## State

```
.marketing/outreach/
  targets.json        ranked cited URLs + status (script-managed, status preserved across runs)
  <target-slug>.md    triage notes + the draft for one target
  tracker.md          one line per target: status, owner, dates, outcome
.marketing/watch.json targets you pitched, watched for a mention (shared with other skills)
```

## The run

### 1. Rank the targets

```bash
python3 <skill>/scripts/outreach_targets.py .marketing/runs/<latest> --top 30
```

The ranking weighs how often each URL was cited, on how many engines, and on how many prompts you
lost to a competitor. URLs on your own and competitors' domains are excluded. If a competitor's
second domain or a vendor that isn't in the panel shows up (a mirror domain, a vendor's blog),
add it to `competitors` in the panel and rerun. Those pages are theirs, not targets.

Add two secondary sources when the audit alone is thin (state the price first):

- **Live threads**: `catalog_search "reddit search posts"` (~$0.001-0.002 a call) on the gap prompts'
  wording, sorted new. A thread from this month that already ranks or gets cited is worth more than
  an archived one, because you can still take part.
- **Link intersect**: `catalog_search "domains sharing backlink sources"` (DataForSEO ~$0.024):
  sites linking to two or more competitors but not to you. These are editors who already cover the category.

### 2. Triage: read every target before deciding anything

Read each page (`treg.web.extract` with `X-Treg-Route-Prefer: tinyfish`, free). Record in
`<target-slug>.md`:

- What the page is: a listicle, comparison, how-to, thread, directory, video, reference or news.
- Who runs it: author, publication, last-updated date, whether it takes updates or corrections, and
  any disclosure or affiliate policy.
- Whether it already mentions you, and accurately. If it's accurate, mark it `landed` and protect it.
  If it's inaccurate, that's the highest priority, because it's a correction.
- Which competitors it names and why, in the page's own words.
- What it lacks that you can honestly supply: a missing option, an outdated fact, an untested claim,
  a failure mode nobody mentions.

Then choose **one** action per target:

| page kind | action | notes |
|---|---|---|
| Editorial listicle / roundup | **pitch an addition** to the author or editor | lead with what their readers gain; offer a fact, test, or asset |
| How-to / explainer | **pitch a contribution**: data, a quote, a correction | don't ask for a link; offer substance |
| Inaccurate mention | **correction request** with evidence | fastest win; be precise and polite |
| Reddit / forum thread (active) | **a reply from a real, named team member, with disclosure** | answer the question fully first, name alternatives fairly, check the subreddit's rules, one reply |
| Reddit / forum thread (old or archived) | **skip**, or answer only if the forum allows it and the thread still gets traffic | never necro-post to market |
| Hacker News | **skip** marketing replies | engage only as a genuine participant |
| Directory / review site | **claim or create the listing** (a human logs in), then ask real customers for reviews | hand off to `entity-presence` |
| Video | **creator outreach**: a review copy or a demo for the creator | disclosure is the creator's duty; mention it |
| Wikipedia | **never edit it yourself** (conflict-of-interest rules) | at most a disclosed talk-page note with independent sources |
| Gov / standard / encyclopedia | **skip** pitching | cite them in your own pages instead |

If many targets need something you don't have, such as benchmark data, a public test, or a free
checker tool, propose that **linkable asset** to the user as a `one-pager` (or a small tool). One
good asset can unlock a dozen pitches.

### 3. Find the right person (treg, verified only)

- An article's author from its URL: `catalog_search "author email from article url"` (e.g.
  `tomba.people.email.find.author`, ~$0.009).
- A named person at a domain: routed `treg.people.email.find` with
  `X-Treg-Route-Verify: true` and a `X-Treg-Route-Max-Cost`.
- **Verify every address before it goes in a draft**, and never write a guessed address (no
  `info@` unless the page lists it). Prefer the publication's published editorial or corrections
  contact when there is one. Treat `catch_all` and `risky` as risky.
- Collect only what you need to send one message. Don't build a dossier on a person.

### 4. Draft (a human sends)

One file per target. Under 120 words for an email; a forum reply as long as the question needs.

- Subject: specific to their page ("Your 2026 PDF redaction roundup: one option missing that works offline").
- First line: the exact page and what it gets right. No flattery.
- What's missing and why it matters **to their readers**, with one checkable fact. Product claims
  must be OK rows in `.marketing/claims.md`, copied with their qualifiers.
- What you offer: a test result, data, a quote from a named person, a review license.
- Disclosure: who you are and that it's your product.
- No reciprocal links, no payment offers, no follow-up threats. One follow-up after about 10 days, at most.

Forum replies answer the question first, give the general method, name the options including
competitors fairly, and disclose in the same sentence that mentions the product.

### 5. Track and measure

- Update `targets.json` status (`triaged → drafted → sent → landed | declined | skip`) and
  `tracker.md` (who sent it, when).
- Add each pitched URL to the watch list so you see when it starts naming you:
  `python3 ../comparison-pages/scripts/watch_pages.py --add <url> --purpose target --expect "<Brand>"`
  (the sibling skill's script; it reads pages through treg for free).
- A target is **landed** when the page names you accurately. It's a **win** when a later audit shows
  the prompts it was cited on flip to named. Expect weeks: the editor has to update the page, and the
  engines have to re-crawl it.
- Report: targets triaged, drafts waiting for a human, sent, landed, and the flips each landing
  contributed to.

## Spend

Triage reads are free. Contact finding costs ~$0.005-0.01 per verified address. Reddit search is
~$0.002 a call. A batch of 30 targets usually costs under $0.50. State the estimate before finding
contacts, report the actual spend, and rate calls that invite a `review`.
