# AI tells: what makes copy read as generated

Readers who decide a page was written on autopilot stop trusting its claims. The tells below come
from three habits of generated text: it reaches for stock phrases, it stacks rhetorical devices,
and it says big things with nothing specific behind them. The fix for all three is the same: say
the specific thing.

The machine-readable lists are in `ai-tells.json` (used by `scripts/claims_guard.py`). This file
explains them and covers the patterns a script can't catch.

## Two kinds of rule

- **Ban**: a tell the first time it appears. Remove it. The `ban` list in the JSON.
- **Cap**: fine when chosen on purpose, a tell when repeated. The `cap` list gives the number of
  uses allowed per document. Above it, cut until each use earns its place.

## Banned phrases (and what to write instead)

| instead of | write |
|---|---|
| "In today's fast-paced / digital / ever-evolving …" | Start with the reader's problem. |
| "Unlock the power / full potential of …", "harness the power" | Say what the reader can now do: "Export a redacted PDF in one step." |
| "Game-changer", "revolutionize", "supercharge", "next-level", "elevate your" | Name the change and its size, with a ledger row behind it, or drop it. |
| "Look no further", "say goodbye to …", "whether you're a … or a …" | Address the one reader the page is for. |
| "It's important / worth noting that …" | State the thing. If it matters, the reader will notice. |
| "Delve into", "tapestry", "navigate the complexities", "a testament to" | Plain verbs: "look at", "mix", "deal with", "shows". |
| "Seamlessly", "cutting-edge", "best-in-class", "world-class" | Describe the behaviour or the evidence. |
| "Rest assured", "at the end of the day" | Delete. |

## Capped words

"not just", "imagine", "simply", "powerful", "robust", "effortless", "transform", "streamline",
"leverage", "crucial" each get one use (two for "simply"). "Ultimate" gets none.

## Patterns a script can't catch (check by reading)

| pattern | why it reads as generated | fix |
|---|---|---|
| "It's not X, it's Y" and "X isn't just A, it's B" | a reflex contrast with no argument behind it | state Y and give the reason |
| Groups of exactly three, everywhere | rhythm over content | use the real number of items |
| A colon or dash before a "reveal" | manufactured suspense | write the sentence straight |
| Rhetorical questions as section openers | stalling | answer the question instead |
| Sentence fragments for punch, several per section | ad-copy tic | one per section at most, in short copy only |
| Every paragraph ends on a summary line | padding | end on the last new fact |
| Hedge stacks ("may potentially help some teams") | no claim at all | either support the claim or remove it |
| Generic examples ("a company", "a user") | no proof of knowledge | use a real scenario from the product or customer language |

## Short copy vs long copy

- **Short copy** (headlines, heroes, CTAs, ads, posts, subject lines): one idea, concrete nouns,
  no adjective the product can't back. Fragments are allowed here, one per unit.
- **Long copy** (articles, page bodies, long emails): answer first, then detail. Paragraphs of 2-4
  sentences. Every section adds a fact, an example or a step; cut sections that only restate.

## Plain-English swaps

| avoid | use |
|---|---|
| utilize | use |
| facilitate | help, let |
| in order to | to |
| a wide range of | many (or the number) |
| at this point in time | now |
| prior to | before |
| comprehensive solution | say what it covers |
| end-to-end | from X to Y |
| robust | name the failure it handles |
