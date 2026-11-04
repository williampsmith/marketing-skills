---
name: launch-video
description: Make a short motion-design launch video for a shipped feature or release with HyperFrames (HTML, CSS and animation rendered to MP4) - facts taken from what actually merged, real product screens, every on-screen word and voiceover line checked against the claims ledger, local voiceover and music only, a human approving the preview before the final render, and the MP4 left for a human to post. Use when gtm's launch mode tiers a launch as major (or medium and the team wants video), when someone asks for a launch video, release video, feature demo video or motion graphics for a release, or to turn "what's in the next release" into a video.
---

# Launch video

A launch video earns attention only if every frame is true: the feature shown is the one that
shipped, the screens are the real product, and each claim is one the team can stand behind. Short
beats long: 20-45 seconds, one point, the feature doing its job on screen.

The craft (composition, motion, typography, timing, captions) belongs to HyperFrames' own skills;
read them when installed (`/hyperframes`, `/hyperframes-cli`, `/media-use`; the Claude Code plugin is
`heygen-com/hyperframes`), and `references/hyperframes.md` otherwise. This skill owns what they don't:
the facts, the claims, the cost and the approval.

`<state>` is `python3 ../gtm/scripts/gtm.py where` (`root`). Run scripts from the product repo root,
by absolute path. `scripts/video.py` is the only way this skill runs HyperFrames: it pins the
version, turns telemetry off, keeps media local and refuses a final render nobody approved.

## Requires

- Node 22+, FFmpeg, and the Chrome that HyperFrames' renderer downloads on first use (a few hundred
  MB on the host). `video.py hf <project> -- doctor --json` checks them.
- `<state>/claims.md` and `<state>/product-context.md` (gtm init).
- Optional: the HyperFrames skills installed in the agent, for the craft.

## Steps

1. **Get current.** `git pull --ff-only` on the product repo (stop and say so if it won't), then
   `python3 scripts/video.py new <slug>` → `<state>/launches/<date>-<slug>/` with a brief template.
2. **Facts.** `python3 scripts/video.py facts --since <last release tag> --gh --out <project>` lists
   what merged since the last release, with PR summaries. Read `facts.md`; keep only user-visible
   changes; read the code or PR when a summary is unclear. Every product statement in the video must
   match an OK row in `claims.md`; add rows (with evidence) for new features first, as gtm's launch
   step 3 does.
3. **Brief.** Fill `brief.md`: audience, the one point, length and format, the real screens to show,
   the voiceover script line by line, and the beats. Pass `../writing` on the script.
   `python3 scripts/video.py copy <project>` collects every on-screen word and the voiceover into
   `copy.txt` and runs the claims guard; fix every unsupported line.
4. **Ask before building** when a person is present: post the brief (point, script, beats) and wait
   for a yes or changes. In a scheduled run, stop here and put the brief in "Needs you".
5. **Build.** `python3 scripts/video.py hf <project> -- init video --non-interactive`, then author the
   composition (HyperFrames' skills). Real screens: screenshots from the running product or
   `hf <project> -- capture <url>` of the product's own pages, never a mock-up passed off as the
   product. Voiceover: `hf <project> -- tts "<line>" -o assets/vo-1.wav` (local Kokoro). Music and
   sound: `hf <project> -- media-use resolve --type bgm --intent "…"` (made local-only by video.py),
   or none. Logos come from the repo.
6. **Check.** `hf <project> -- check --json` until clean; `hf <project> -- snapshot --at <t1>,<t2>,…`
   and look at every frame you'd show (read the images). Re-run `video.py copy`: the composition
   may have gained words since step 3.
7. **Preview for approval.** `hf <project> -- render --quality draft --output renders/draft.mp4` and
   post it (or the snapshots) to the thread with the copy. The person approves the exact files:
   `python3 scripts/video.py approve <project> --quote "<their words>" --approver <platform:id>
   --source <link>` (gtm's Approvals rules; refused in a scheduled run). Any later edit voids it.
8. **Render.** `hf <project> -- render --quality delivery --output renders/<slug>.mp4`, then
   `ffprobe -v error -show_format -show_streams` it: duration matches the root `data-duration`, there
   is an audio stream if there's a voiceover. Post the MP4 for the human to publish, with a suggested
   caption from the claims rows. **Never post or upload it yourself.**
9. `python3 ../gtm/scripts/gtm.py record launch_video --key <tag or slug>`, and note it in plan.md.

## Rules

- **What shipped, not what's planned.** A feature behind a flag that's off, or merged after the tag,
  isn't in the video.
- **Claims from the ledger**, word for word in meaning; numbers only with evidence. No "fastest",
  "only" or "100%" without a row that says so.
- **Real product, real data shapes.** No real customer data on screen: use the product's demo or
  seed data, and blur anything that could be personal.
- **Local media by default.** HeyGen voices, avatars, generated music or images cost money and need
  an account: they're a human's decision, outside `video.py` (which refuses them), with the price
  stated first and the spend recorded with `gtm.py record launch_video --cost`.
- **No uploads.** No cloud, Lambda or HeyGen-hosted rendering, no `feedback`, no telemetry. The
  project stays in `<state>`.
- The pinned version (`PIN` in `scripts/video.py`) moves only deliberately, after reading its release
  notes; HyperFrames ships several releases a day.

## Output

`<state>/launches/<date>-<slug>/`: `facts.md`, `brief.md`, `copy.txt`, `approval.json`, and `video/`
(the HyperFrames project; `renders/` holds the MP4s and is never committed to a git state store).
