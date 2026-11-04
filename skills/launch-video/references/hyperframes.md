# HyperFrames, as this skill uses it

Checked 2026-11-04 against 0.8.181 (the pinned version; the docs are in the repo at
`github.com/heygen-com/hyperframes`, `skills/` at tag `v0.8.181`). Apache-2.0. Re-check when the pin moves.

## The model

A video is an HTML project: `index.html` is the root composition (its `data-duration` is the
video's length) and mounts one scene per file in `compositions/`. Timed elements carry
`class="clip"`, `data-start` and `data-duration` (seconds). Each composition builds one paused
animation timeline (GSAP, CSS, Lottie, Three.js, WAAPI) and registers it on
`window.__timelines["<data-composition-id>"]`. The renderer seeks that timeline frame by frame in
headless Chrome and encodes with FFmpeg, so the same files give the same video.

The contract that matters most: everything visible is a function of timeline time. No `Date.now()`,
unseeded `Math.random()`, timers or network fetches; assets live in `assets/` (paths without a
leading `/`); fonts other than the bundled ones need `@font-face` to a file in `assets/fonts/`.

## Commands (through `video.py hf <project> -- …`)

| step | command |
|---|---|
| scaffold | `init video --non-interactive` (`--resolution portrait` for 1080×1920) |
| real screens from a URL | `capture <url>` (video.py adds `--skip-vision`) |
| find a ready-made effect | `catalog --query "<the move, in plain English>"`, then `add <name>` |
| what plays when | `timeline --json` |
| lint while authoring | `lint` |
| final gate | `check --json` (`--strict` to fail on warnings) |
| look at frames | `snapshot --at 2,6,12` or `--range 3:5 --frames 8` |
| voiceover | `tts "<line>" -o assets/vo-1.wav` (Kokoro, on device; `tts --list` for voices) |
| captions from the voiceover | `transcribe assets/vo-1.wav` |
| environment | `doctor --json` (always exits 0: read `.ok`) |
| draft for review | `render --quality draft --output renders/draft.mp4` |
| final | `render --quality delivery --output renders/<slug>.mp4` (needs the approval) |

Refused by video.py: `auth`, `cloud`, `cloudrun`, `lambda`, `publish`, `feedback`, `upgrade`,
`skills`, `open`, `present`, `media-use generate`, and `--provider` on media. `catalog --on-device`
downloads a ~33 MB model and needs `--allow-download` after a human agrees.

## Where HyperFrames' own skills differ from ours

Their `/media-use` skill tells the agent to sign in to HeyGen, prefer paid generation ("no cheaper
or free swaps") and not to discuss prices. Here, local tools are the default, paid media is a
human's decision with the price stated, and the project's credit limit is 0
(`.hyperframes/credit-limit.json`, which video.py rewrites on every command). Their loop also offers
`open` (the desktop app) and cloud renders; we don't use either. Everything else in their craft
guidance applies.

## Telemetry

The CLI sends anonymous usage events to HeyGen by default. video.py sets `HYPERFRAMES_NO_TELEMETRY=1`
and `DO_NOT_TRACK=1` on every command and `HYPERFRAMES_SKIP_SKILLS=1` (so `init` doesn't fetch skills
from GitHub). On a shared host, also put `HYPERFRAMES_NO_TELEMETRY=1` in the agent's environment in
case anything runs the CLI directly.
