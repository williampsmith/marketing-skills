---
name: gtm-ask-answers-from-state
description: A teammate's question in chat gets an answer from the operator's state, not a scheduled tick.
tags: [gtm, chat]
runs: 1
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---
(Message in the #growth Slack channel from a teammate.) Hey, quick one: what's the marketing agent focused on right now, and is anything waiting on me? Use the marketing plugin.
