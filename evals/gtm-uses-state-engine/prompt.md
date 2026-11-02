---
name: gtm-uses-state-engine
description: Asked what to do next for marketing, the agent runs the gtm skill and asks gtm.py rather than guessing.
tags: [smoke, gtm]
runs: 1
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---
We just set up the marketing plugin for our product. What should our marketing agent work on next, and why? Use the plugin's own tooling to decide, don't guess.
