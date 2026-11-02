#!/usr/bin/env python3
"""Build the review page for a batch of creative assets. Nothing is published from here: a human
reviews the page and replies with the ids they approve.

    python3 review_page.py <state>/creative/<batch>

Reads <batch>/manifest.json, a list of assets:
    {"id": "hook-03", "file": "hook-03.mp4", "channel": "short_video", "format": "ugc_hook",
     "claim_row": "Checks every export and refuses to save one that fails", "script": "...",
     "ai_generated": true, "disclosure": "AI-generated presenter", "cost_usd": 0.86}
and writes <batch>/review.html: one self-contained page (no external resources, light and dark
themes) showing each asset by relative path with its channel, format, script, claim row,
disclosure and cost.

Refuses (exit 1, writes nothing) when an asset has no claim_row, or is AI-generated
(`ai_generated` true, the default) without a disclosure. Every value is HTML-escaped. Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402,F401  (shared engine; keeps the import contract of the plugin's scripts)

IMAGE = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif")
VIDEO = (".mp4", ".webm", ".mov", ".m4v")
AUDIO = (".mp3", ".wav", ".m4a", ".ogg")

CSS = """
:root{--bg:#f6f7f5;--fg:#1d2327;--muted:#5c676e;--card:#fff;--rule:#d9ddda;--accent:#0f6b63}
@media (prefers-color-scheme:dark){:root{--bg:#14191c;--fg:#e3e7e5;--muted:#9aa5a9;--card:#1b2125;--rule:#2c3438;--accent:#5cc2b5}}
body{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;
padding:28px max(16px,env(safe-area-inset-left))}
main{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
h1{margin:0;font-size:1.5rem}.muted{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:8px;min-width:0}
.card img,.card video{width:100%;max-height:420px;object-fit:contain;background:var(--bg);border-radius:6px}
.id{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent);font-weight:600}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:.9rem}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}
pre{white-space:pre-wrap;margin:0;font:inherit}
.reply{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:12px 14px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
"""


def esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def problems(assets: list[dict]) -> list[str]:
    out = []
    seen = set()
    for a in assets:
        if not isinstance(a, dict):
            out.append(f"{a!r}: each asset is an object")
            continue
        aid = a.get("id") or "(no id)"
        if not a.get("id"):
            out.append(f"{aid}: missing id")
        elif aid in seen:
            out.append(f"{aid}: duplicate id (approval is by id)")
        seen.add(aid)
        f = str(a.get("file") or "")
        if "://" in f or f.startswith(("/", "\\")) or ".." in Path(f).parts:
            out.append(f"{aid}: file must be a relative path inside the batch folder (the page loads nothing remote)")
        try:
            float(a.get("cost_usd") or 0)
        except (TypeError, ValueError):
            out.append(f"{aid}: cost_usd must be a number")
        if not str(a.get("claim_row") or "").strip():
            out.append(f"{aid}: no claim_row (every asset makes one claim from the ledger)")
        if a.get("ai_generated", True) and not str(a.get("disclosure") or "").strip():
            out.append(f"{aid}: AI-generated media needs a disclosure")
    return out


def media(file: str) -> str:
    f = esc(file)
    low = str(file).lower()
    if low.endswith(IMAGE):
        return f'<img src="{f}" alt="">'
    if low.endswith(VIDEO):
        return f'<video src="{f}" controls preload="metadata"></video>'
    if low.endswith(AUDIO):
        return f'<audio src="{f}" controls preload="none"></audio>'
    return f'<p class="muted">file: <code>{f}</code></p>'


def build(batch: str, assets: list[dict]) -> str:
    cards = []
    total = 0.0
    for a in assets:
        total += float(a.get("cost_usd") or 0)
        cards.append(
            f'<article class="card"><div class="id">{esc(a["id"])}</div>{media(a.get("file", ""))}'
            f'<dl><dt>channel</dt><dd>{esc(a.get("channel"))}</dd><dt>format</dt><dd>{esc(a.get("format"))}</dd>'
            f'<dt>claim</dt><dd>{esc(a.get("claim_row"))}</dd>'
            f'<dt>disclosure</dt><dd>{esc(a.get("disclosure") or "none (not AI-generated)")}</dd>'
            f'<dt>cost</dt><dd>${float(a.get("cost_usd") or 0):.2f}</dd></dl>'
            f'<pre>{esc(a.get("script"))}</pre></article>')
    ids = "&lt;ids&gt;"
    return ("<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Creative review {esc(batch)}</title><style>{CSS}</style><main>"
            f"<header><h1>Creative review: {esc(batch)}</h1><p class='muted'>{len(assets)} assets · "
            f"${total:.2f} generation cost · nothing here is published until a human posts it</p></header>"
            f"<div class='reply'>To approve, reply in the digest thread: "
            f"<code>approve creative {esc(batch)}: {ids}</code> (list the ids you approve; anything not listed is "
            f"rejected).</div><section class='grid'>{''.join(cards)}</section></main>")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch_dir")
    a = ap.parse_args()
    d = Path(a.batch_dir)
    try:
        assets = json.loads((d / "manifest.json").read_text())
    except (OSError, ValueError) as e:
        print(f"can't read {d / 'manifest.json'}: {e}", file=sys.stderr)
        return 1
    if not isinstance(assets, list) or not assets:
        print("manifest.json must be a non-empty list of assets", file=sys.stderr)
        return 1
    bad = problems(assets)
    if bad:
        print("refusing to build the review page:\n" + "\n".join(f"- {b}" for b in bad), file=sys.stderr)
        return 1
    out = d / "review.html"
    out.write_text(build(d.name, assets))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
