---
name: launch-video-uses-wrapper
description: Asked for a launch video, the agent uses the launch-video skill and its video.py wrapper (facts from git, pinned HyperFrames), not the raw CLI.
tags: [launch-video]
runs: 1
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---
We just tagged a release. Start a 30-second launch video for what's new since the previous tag, using the marketing plugin. Get as far as the facts and a brief; don't render anything.
