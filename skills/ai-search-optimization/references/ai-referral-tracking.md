# Tracking AI-driven visits

There are three layers, from earliest signal to most direct:

1. **Bot fetches** (server or CDN logs): `ChatGPT-User`, `Claude-User` and `Perplexity-User` hits
   are assistants opening your page because someone asked. Search-bot hits (`OAI-SearchBot`,
   `Claude-SearchBot`, `PerplexityBot`) mean you are being indexed. See `bots.md` for log one-liners.
2. **Referred sessions** (analytics): clicks from AI answers.
3. **Outcomes**: sign-ups, trials and purchases attributed to those sessions.

## Referrer domains to match

`chatgpt.com`, `chat.openai.com`, `perplexity.ai`, `claude.ai`, `gemini.google.com`,
`copilot.microsoft.com`, `bing.com/chat`, `you.com`, `phind.com`, `meta.ai`, `chat.mistral.ai`,
`duckduckgo.com` (DuckAssist is mixed in with search) — also `utm_source=chatgpt.com`, which
ChatGPT adds to many links.

## GA4

Admin → Data display → Channel groups → copy the default → add a channel **AI Assistants** *above*
Referral, with the condition: Session source matches regex

```
(chatgpt|openai|perplexity|claude\.ai|gemini\.google|copilot\.microsoft|bing\.com/chat|you\.com|phind|meta\.ai|mistral)
```

Then build an exploration on landing page × session source for that channel, and keep a second
view of **Direct sessions to deep pages** (one-pagers, guides), since AI clicks with no referrer
show up there.

## PostHog

On every `$pageview`, if `document.referrer` or `utm_source` matches the regex above, call
`posthog.register_once({ai_referrer: <host>})` so the first AI touch stays on the person through
conversion. Then build an insight on sign-ups broken down by `ai_referrer`.

```js
const m = (document.referrer + ' ' + location.search).match(/chatgpt|openai|perplexity|claude\.ai|gemini\.google|copilot\.microsoft|you\.com|phind|meta\.ai|mistral/i);
if (m) posthog.register_once({ ai_referrer: m[0].toLowerCase(), ai_landing: location.pathname });
```

## With treg

If the team has connected GA4, Search Console or PostHog to treg (`treg connections`, or a team
tool), the agent can pull the numbers itself: `catalog_search "google analytics report"` and
`google-search-console.performance` cost nothing on the team's own connection. Use them to
close the loop in `ai-visibility-audit`, putting panel wins next to AI-referred sessions per landing page.

## Privacy

Track sources and landing pages, not prompt content (you can't get it, and shouldn't try).
Update the privacy policy if you add new analytics properties.
