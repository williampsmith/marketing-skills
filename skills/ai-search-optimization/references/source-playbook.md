**AI Search Optimization Playbook**  
*(Based on the changes that drove ChatGPT from zero to majority of traffic for James Brooks’ site)*

Implement the steps in order, report what you changed, and flag anything that needs human review (domain-specific content, existing robots.txt rules, analytics setup, etc.).

### Goal
Make the site crawlable, readable, and citable by AI search systems (ChatGPT/OAI-SearchBot, PerplexityBot, Claude-SearchBot, etc.) while optionally blocking training crawlers. Focus on clear access, machine-readable signals, intent-matched pages, and accurate structured data.

### Step 1: Update `robots.txt` (Highest priority)
Allow AI search/user bots and block training crawlers. Explicitly name the bots (do not rely only on a wildcard).

**Recommended template** (merge with existing rules; adjust private paths):

```
# AI search & user-triggered bots (allow)
User-agent: OAI-SearchBot
User-agent: ChatGPT-User
User-agent: PerplexityBot
User-agent: Perplexity-User
User-agent: Claude-SearchBot
User-agent: Claude-User
Allow: /
Disallow: /admin/
Disallow: /wp-admin/
Disallow: /checkout/
Disallow: /api/private/

# Training crawlers (block)
User-agent: GPTBot
User-agent: ClaudeBot
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: CCBot
Disallow: /

# Everyone else (including Googlebot, Bingbot)
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /wp-admin/
Disallow: /checkout/

Sitemap: https://YOURDOMAIN.com/sitemap.xml
```

- Test by fetching `/robots.txt` and confirming the rules.
- Changes can take ~24 hours to be reflected by OpenAI.
- Note: Some user-triggered bots (ChatGPT-User, Perplexity-User) may ignore robots.txt.

### Step 2: Create `/llms.txt`
Place a Markdown file at the root (`https://YOURDOMAIN.com/llms.txt`). It is optional (major engines have not confirmed they use it for citations), but it helps agents and was part of the original successful changes.

**Template**:

```
# Your Site or Brand Name

> One clear sentence describing what the site is, who it serves, and its main value. Write it so an AI can quote it directly.

Additional short context if needed (plain paragraphs or lists, no headings).

## Key Pages
- [Page Title](https://YOURDOMAIN.com/exact-url): One-sentence description of what the page answers or covers.
- [Another Page](https://YOURDOMAIN.com/another): Description.

## Optional
- [About](https://YOURDOMAIN.com/about): Secondary info.
- [Blog or Resources](https://YOURDOMAIN.com/blog): Latest updates.
```

- Keep it short and curated (most important pages first).
- Use full URLs.
- Optionally create a companion `/llms-full.txt` that concatenates key page content in Markdown.
- Also expose a public JSON feed of live content (e.g., `/feed.json` or an API endpoint listing titles, URLs, dates, short summaries, and main content). Link to it from `llms.txt`.

### Step 3: Content structure for AI citation
On key pages (especially those targeting specific questions or intents):

- Add a short, dated “Quick Answer” section near the top (2–5 sentences that directly answer the primary query). Include a visible or structured date of last update.
- Prefer one focused page per major search intent rather than long multi-topic pages. These are the pages AI systems are most likely to link.
- Ensure the main content is in the initial HTML (server-rendered or static). Avoid relying solely on client-side JavaScript for important text.

### Step 4: Structured data
Add JSON-LD (Schema.org) that accurately matches the visible content on the page. Do not mark up claims or details that are not present in the page text.

Common useful types: Article, FAQPage, HowTo, Organization, Product, etc. Validate with Google’s Rich Results Test or Schema Markup Validator.

### Step 5: Tracking ChatGPT / AI referrals
ChatGPT traffic frequently appears as “Direct” (referrers and UTM tags are often stripped).

- Use PostHog (or similar) to capture referrer on pageview and register properties when the referrer matches AI domains (`chatgpt.com`, `perplexity.ai`, `claude.ai`, etc.).
- In GA4, create a custom channel or exploration filtering on session source containing `chatgpt`, `openai`, `perplexity`, etc., and also monitor Direct traffic to the landing pages AI tends to send people to.
- Optionally look for any remaining tags (the original post referenced a specific tracking tag approach with PostHog).

### Step 6: Verification checklist
After implementation, confirm:
- `/robots.txt` allows the search bots and blocks the training ones.
- `/llms.txt` returns 200 with valid Markdown.
- Key pages have a clear quick answer + matching structured data.
- Content is visible in raw HTML / view-source.
- Analytics can distinguish or at least surface AI-driven visits (even if they appear as Direct).
- Sitemap is listed and up to date.

### Notes
- Access control (robots.txt + CDN/firewall not blocking the bots) is the highest-leverage step. Without it, nothing else matters.
- Results are not guaranteed and can take days to weeks; the original example saw a sharp increase roughly a week after changes.
- Keep content accurate, specific, and regularly updated—AI systems favor clear, citable answers.
- Revisit the robots.txt and llms.txt periodically as bot names and practices evolve.

Provide your domain, existing robots.txt contents, and primary site goals/pages when handing this to the agent for the best results.