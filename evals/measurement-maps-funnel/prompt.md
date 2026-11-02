---
name: measurement-maps-funnel
description: Asked to set up funnel measurement for a self-serve product, the agent uses the measurement skill and maps funnel stages to PostHog events.
tags: [smoke, measurement]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---
Our product is a self-serve SaaS for redacting PDFs. We already use PostHog. The app sends these events: `$pageview` on the marketing site, `account_created` when someone signs up, `document_redacted` the first time they redact a file, `checkout_completed` when they start paying, and `session_started` whenever they open the app. Set up funnel measurement for our marketing agent so it can tell where our funnel is weakest. Show me exactly what configuration you'd write.
