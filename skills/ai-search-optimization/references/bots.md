# AI crawlers and fetchers (checked 2026-10-31)

Bot names change. Before you rely on this list, check each vendor's crawler page; the URLs are
below, and `treg.web.extract` reads them for free. `scripts/check_ai_access.py` checks the main ones (its `BOTS`
table), so update both together.

| robots token | vendor | role | feeds | vendor docs |
|---|---|---|---|---|
| OAI-SearchBot | OpenAI | search | ChatGPT search results and citations | platform.openai.com/docs/bots |
| ChatGPT-User | OpenAI | user | live fetch when a ChatGPT user or GPT action opens a page | same |
| GPTBot | OpenAI | training | future OpenAI models | same |
| Claude-SearchBot | Anthropic | search | Claude's search index | support.anthropic.com (crawler article) |
| Claude-User | Anthropic | user | live fetch when a Claude user asks | same |
| ClaudeBot | Anthropic | training | future Claude models | same |
| PerplexityBot | Perplexity | search | Perplexity index and citations | docs.perplexity.ai (bots) |
| Perplexity-User | Perplexity | user | live fetch for a user's question | same |
| Googlebot | Google | search | Google Search, AI Overviews and AI Mode (no separate AI bot) | developers.google.com/search/docs/crawling-indexing |
| Google-Extended | Google | token | Gemini training and grounding only | same |
| Bingbot | Microsoft | search | Bing, Copilot, and much of ChatGPT search's web results | bing.com/webmasters |
| Applebot | Apple | search | Siri, Spotlight, Apple Intelligence answers | support.apple.com/119829 |
| Applebot-Extended | Apple | token | Apple model training only | same |
| DuckAssistBot | DuckDuckGo | user | DuckAssist answers | duckduckgo.com/duckduckgo-help-pages |
| MistralAI-User | Mistral | user | Le Chat live fetch | docs.mistral.ai/robots |
| Meta-ExternalAgent | Meta | training | Meta AI models | developers.facebook.com/docs/sharing/webmasters/crawler |
| Amazonbot | Amazon | search/training | Alexa, Rufus | developer.amazon.com/amazonbot |
| CCBot | Common Crawl | training | the open corpus most model labs train on | commoncrawl.org/ccbot |

## Rules that trip people up

- **Most-specific group wins.** A bot named in a group ignores `User-agent: *` entirely, so repeat
  the private-path disallows in every named group.
- **Several `User-agent` lines can share one group**, as in the template. Some legacy parsers
  mishandle this. If a vendor's tester disagrees, give that bot its own group.
- **`Allow` vs `Disallow` precedence**: Google uses the longest matching path. Others vary, so
  avoid relying on subtle overlaps.
- **Blocking Bingbot hides you from ChatGPT** in many queries, because ChatGPT search leans on
  Bing's index. Never block it on a site that wants AI visibility.
- **Cloudflare managed robots.txt** can prepend its own AI-blocking rules to your file. Fetch the
  live `/robots.txt`, not the repo copy.
- **Verified bots.** OpenAI, Google, Bing and others publish IP ranges or reverse-DNS checks.
  A WAF rule should allow verified bots, not user-agent strings, which anyone can spoof.

## Reading logs for AI demand

```bash
# hits per AI user agent, last log file (adjust the path / format to the server)
grep -oE 'OAI-SearchBot|ChatGPT-User|GPTBot|Claude-SearchBot|Claude-User|ClaudeBot|PerplexityBot|Perplexity-User|bingbot|Googlebot' access.log | sort | uniq -c | sort -rn
# which pages ChatGPT users made the assistant open
grep 'ChatGPT-User' access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20
```

On Cloudflare, the same data is in AI Crawl Control (per-bot requests and allowed or blocked
counts) and in Log Explorer or Logpush.
