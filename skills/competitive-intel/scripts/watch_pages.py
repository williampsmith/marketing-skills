#!/usr/bin/env python3
"""Watch a list of web pages for changes and for whether they mention given names.

    python3 watch_pages.py                       # uses <state>/watch.json
    python3 watch_pages.py --only competitor     # one purpose group
    python3 watch_pages.py --add https://x.com/pricing --purpose competitor --used-by site/compare/x.html

Watch file (<state>/watch.json, where <state> is `gtm.py where`):
    [{"url": "...", "purpose": "competitor|target|profile",
      "used_by": ["path/to/page/that/relies/on/it"], "expect": ["Brand", "Competitor"]}]

Shared by three skills:
  comparison-pages  - competitor pricing/docs changed -> pages that cite them need a refresh
  citation-outreach - did the target page start mentioning us?
  entity-presence   - does each profile still carry the canonical description?

Reads pages through treg's free routed extractor (TinyFish first), falling back
to a plain fetch. Snapshots go in <state>/watch/<id>/. Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import html
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
from marketing_state import state_root  # noqa: E402  (the plugin's shared state-store resolver)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
# Lines that change on every fetch and would make every page look "changed".
NOISE = re.compile(r"(©|copyright|\b20\d\d\b.*all rights reserved|cookie|csrf|nonce|session)", re.I)


def via_treg(url: str) -> tuple[str, str] | None:
    try:
        p = subprocess.run(
            ["treg", "--json", "call", "treg.web.extract", "--method", "POST",
             "--data", json.dumps({"url": url}), "--header", "X-Treg-Route-Prefer: tinyfish",
             "--header", "X-Treg-Route-Max-Cost: 0.01"],
            capture_output=True, text=True, timeout=120)
        d = json.loads(p.stdout.strip().splitlines()[-1])
        page = d["result"]["output"]["pages"][0]
        return page.get("text") or "", page.get("title") or ""
    except Exception:  # noqa: BLE001 - any failure falls back to a plain fetch
        return None


def via_http(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read(3_000_000).decode("utf-8", "replace")
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    page = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?i)<(br|/p|/li|/h\d|/tr|/div)[^>]*>", "\n", page)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", page))
    return text, html.unescape(title.group(1).strip()) if title else ""


def normalize(text: str) -> str:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln and not NOISE.search(ln))


def wid(url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", url.lower().split("//", 1)[-1])[:60].strip("-")
    return f"{slug}-{hashlib.sha1(url.encode()).hexdigest()[:8]}"


def mention(text: str, term: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.I) is not None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", default=None, help="default <state>/watch.json")
    ap.add_argument("--only", default="", help="purpose to check (competitor, target, profile)")
    ap.add_argument("--add", default="", help="add a URL to the watch file and exit")
    ap.add_argument("--purpose", default="competitor")
    ap.add_argument("--used-by", action="append", default=[])
    ap.add_argument("--expect", action="append", default=[])
    ap.add_argument("--no-treg", action="store_true", help="plain HTTP only")
    a = ap.parse_args()

    wf = Path(a.watch or state_root() / "watch.json")
    items = json.loads(wf.read_text()) if wf.exists() else []
    if a.add:
        for it in items:
            if it["url"] == a.add:
                it["used_by"] = sorted(set(it.get("used_by", []) + a.used_by))
                it["expect"] = sorted(set(it.get("expect", []) + a.expect))
                break
        else:
            items.append({"url": a.add, "purpose": a.purpose, "used_by": a.used_by, "expect": a.expect})
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(json.dumps(items, indent=2) + "\n")
        print(f"watching {len(items)} urls")
        return 0

    root = wf.parent / "watch"
    today = dt.date.today().isoformat()
    rows, changed = [], []
    for it in items:
        if a.only and it.get("purpose") != a.only:
            continue
        url = it["url"]
        got = None if a.no_treg else via_treg(url)
        try:
            text, title = got if got else via_http(url)
        except Exception as e:  # noqa: BLE001
            rows.append(f"| {it.get('purpose')} | {url} | FETCH FAILED: {type(e).__name__} | | |")
            continue
        text = normalize(text)
        d = root / wid(url)
        d.mkdir(parents=True, exist_ok=True)
        prev = (d / "latest.md").read_text() if (d / "latest.md").exists() else None
        h = hashlib.sha256(text.encode()).hexdigest()[:12]
        status = "new" if prev is None else ("same" if prev == text else "CHANGED")
        if status == "CHANGED":
            (d / f"{today}.prev.md").write_text(prev)
            diff = "\n".join(difflib.unified_diff(prev.splitlines(), text.splitlines(), "before", "after", n=1, lineterm=""))
            (d / f"{today}.diff").write_text(diff)
            changed.append((it, diff))
        (d / "latest.md").write_text(text)
        (d / "meta.json").write_text(json.dumps({"url": url, "title": title, "hash": h, "checked": today}, indent=2))
        found = ", ".join(f"{t}:{'yes' if mention(text, t) else 'no'}" for t in it.get("expect", []))
        rows.append(f"| {it.get('purpose')} | {url} | {status} | {found} | {', '.join(it.get('used_by', []))} |")

    out = [f"# Watch report — {today}", "", "| purpose | url | status | mentions | used by |", "|---|---|---|---|---|", *rows]
    for it, diff in changed:
        out += ["", f"## Changed: {it['url']}", f"Pages that rely on it: {', '.join(it.get('used_by', [])) or 'none'}",
                "", "```diff", diff[:4000], "```"]
    report = "\n".join(out) + "\n"
    root.mkdir(parents=True, exist_ok=True)
    (root / "report.md").write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
