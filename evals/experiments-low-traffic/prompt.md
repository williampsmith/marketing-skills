---
name: experiments-low-traffic
description: Asked for an A/B test the traffic can't support, the agent says it would take too long and suggests a holdout or a directional before/after bet.
tags: [smoke, experiments]
runs: 1
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---
Our pricing page gets about 120 visitors a day and 3% of them sign up. I want to A/B test a new headline and I expect it to lift signups by about 10%. Using the marketing plugin's experiments skill, set this test up and tell me how long to run it.
