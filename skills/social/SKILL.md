---
name: social
description: Draft organic social posts and community answers from what the product already has - launches, new pages, closed bets and real customer questions - for a human to post. One idea per post, built on its single most useful point, written to each channel's conventions (LinkedIn, X, Reddit and other communities). Never posts, replies, votes or creates accounts on its own. Measures engagement and clicks after a human posts. Use when a work session picks a social tactic (founder_posts, community_answers), after a launch or a new page ships, or when the user asks for LinkedIn posts, a thread, Reddit answers, community engagement or a social calendar. Visual assets come from ../creative; paid placement from ../paid (when installed).
---

# Social

Organic social earns attention by being useful on its own. The post has to be worth reading by
someone who never clicks, and the click is a bonus. So posts come from substance the product
already has: a launch, a page that answers a real question, a bet that taught something, a question
customers keep asking.

`<state>` is the directory printed by `python3 ../gtm/scripts/gtm.py where` (field `root`). Every
draft passes the `../writing` gates (claims from the ledger, no AI-tell phrasing).

## Sources, in order of value

1. **Launches** (`<state>/launches/`): what a user can do now that they couldn't, shown.
2. **Pages** that shipped: the page's single most useful point, stated in the post, with the page
   linked once.
3. **Closed bets** with a result worth sharing (a learning the human accepted), told as what was
   tried and what happened, with numbers only if they're the product's own and sourced.
4. **Customer language** in `<state>/product-context.md`: a question buyers ask, answered.

Skip a post when the honest answer to "why would someone who never clicks care?" is "they wouldn't".

## Channel conventions

| channel | shape | rules |
|---|---|---|
| LinkedIn | a person's post (founder or expert), 80-200 words or a document post from `../creative`; first two lines carry the point | link in the post only if it's the point; one idea; no engagement bait ("comment YES") |
| X | one post, or a short thread when there are steps; the point in the first post | no hashtag strings; one link |
| Reddit and forums | an answer to the thread's actual question, complete without the product | read the community's rules first; disclose affiliation in the answer ("I work on <product>"); mention the product only if it truly answers the question; never post the same answer twice |
| Hacker News, Product Hunt | launches only, posted by a human who will stay in the thread | never ask for upvotes |

## Community answers (`community_answers` tactic)

For the `review_communities` channel:

1. Find threads where buyers ask the problem in their own words (`../customer-research` evidence,
   or `scrapecreators.reddit.search.posts` and similar; checked 2026-11-02, verify with
   `catalog_get`). Prefer recent threads still getting answers and threads that rank in search or
   are cited in AI answers (`../citation-outreach` targets).
2. Draft an answer that solves the asker's problem with steps they can follow today. Mention the
   product once, with the disclosure, only where it's the honest best fit; otherwise answer
   without it. Drafts that only work as promotion are dropped.
3. Save the draft with the thread link for a human to post from their own account.

## Drafts

Save each draft as `<state>/social/<date>-<slug>.md`:

```markdown
channel: linkedin
author: <who posts it>
source: <launch, page, bet id or thread link>
claim rows: <ledger rows used, or none>
---
<the post>
```

List new drafts in the digest's **Needs you** (at most three per digest; the rest wait). The human
posts, edits or drops them. The agent never posts, replies, votes, follows, or creates or uses
accounts on any platform: platform rules forbid automating these, and detection costs the account.

## Measure

After a human posts, record what happened from the platform's analytics or PostHog, a few days
later: `gtm.py metric add social:<slug>:impressions …`, `…:engagement_rate`, `…:clicks`, and first
steps attributed in PostHog when the post linked to the site. A bet on a social tactic (for example
`founder_posts`) uses one of these as its metric. Patterns that win become proposals in the digest;
they become learnings only through `gtm.py learnings`.

## Don't

- Don't write posts with nothing in them but the product.
- Don't invent a story, customer, quote or number.
- Don't post as a person who hasn't approved the words.
- Don't use the same text on several channels or in several communities.
