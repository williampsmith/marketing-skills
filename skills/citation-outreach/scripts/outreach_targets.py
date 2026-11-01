#!/usr/bin/env python3
"""Rank the exact pages AI engines cite on prompts where we lose.

    python3 outreach_targets.py .marketing/runs/2026-10-31
    python3 outreach_targets.py RUN_DIR --top 40 --out .marketing/outreach/targets.json

Reads answers.jsonl from an ai-visibility-audit run plus the panel's brand and
competitors. A cited URL scores higher when it is cited more often, on more
engines, on more prompts, and on prompts where a competitor is named and we are
not. URLs on our own or competitors' domains are excluded (you can't pitch them).
Whether a target page already names us is checked during triage, by reading it.

Stdlib only. Merges into an existing targets file without losing the status of
targets already worked.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

BUCKET_WEIGHT = {"category": 3, "problem": 3, "jobs": 2, "comparison": 3, "alternatives": 3, "brand": 1}
KIND_RULES = [
    ("forum", r"reddit\.com|news\.ycombinator\.com|stackexchange\.com|stackoverflow\.com|quora\.com|community\.|forum|discourse"),
    ("video", r"youtube\.com|youtu\.be|vimeo\.com|tiktok\.com"),
    ("directory", r"g2\.com|capterra\.com|trustradius\.com|alternativeto\.net|producthunt\.com|saashub\.com|getapp\.com|softwareadvice\.com|slant\.co|trustpilot\.com|apps\.apple\.com|microsoft\.com/store"),
    ("reference", r"wikipedia\.org|wikidata\.org|britannica\.com"),
    ("gov_or_standard", r"\.gov(\.|/|$)|\.mil|nist\.|iso\.org|europa\.eu|ico\.org\.uk"),
]


def clean(url: str) -> str:
    u = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith("utm_")]
    return urlunparse((u.scheme, u.netloc.lower().removeprefix("www."), u.path.rstrip("/") or "/", "", urlencode(q), ""))


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def owns(d: str, doms: list[str]) -> bool:
    return any(d == x or d.endswith("." + x) for x in doms)


def kind(url: str) -> str:
    for k, pat in KIND_RULES:
        if re.search(pat, url, re.I):
            return k
    return "editorial"


def alias_re(names: list[str]) -> re.Pattern:
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in names) + r")(?![\w-])", re.I)


def build(answers: list[dict], panel: dict) -> list[dict]:
    brand = panel["brand"]
    me = alias_re([brand["name"], *brand.get("aliases", [])])
    comps = {c["name"]: alias_re([c["name"], *c.get("aliases", [])]) for c in panel.get("competitors", [])}
    excluded = [d.lower() for d in brand.get("domains", [])]
    for c in panel.get("competitors", []):
        excluded += [d.lower() for d in c.get("domains", [])]

    agg: dict[str, dict] = {}
    for r in answers:
        if r.get("error") or not r.get("text"):
            continue
        named_me = bool(me.search(r["text"]))
        named_comps = [n for n, p in comps.items() if p.search(r["text"])]
        lost = not named_me and bool(named_comps)
        w = BUCKET_WEIGHT.get(r.get("bucket") or "", 2)
        for raw in r.get("sources", []):
            u = clean(raw)
            if owns(domain(u), excluded):
                continue
            t = agg.setdefault(u, {"url": u, "domain": domain(u), "kind": kind(u), "score": 0, "citations": 0,
                                   "engines": set(), "prompts": set(), "lost_prompts": set(), "competitors_named": collections.Counter()})
            t["citations"] += 1
            t["engines"].add(r["engine"])
            t["prompts"].add(r["prompt_id"])
            t["score"] += w * (3 if lost else 1)
            if lost:
                t["lost_prompts"].add(r["prompt_id"])
                t["competitors_named"].update(named_comps)
    out = []
    for t in agg.values():
        t["score"] = t["score"] * (1 + 0.5 * (len(t["engines"]) - 1))
        out.append({**t, "score": round(t["score"], 1), "engines": sorted(t["engines"]), "prompts": sorted(t["prompts"]),
                    "lost_prompts": sorted(t["lost_prompts"]), "competitors_named": dict(t["competitors_named"].most_common())})
    return sorted(out, key=lambda t: -t["score"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--panel", default=".marketing/prompt-panel.json")
    ap.add_argument("--out", default=".marketing/outreach/targets.json")
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args()
    panel = json.loads(Path(a.panel).read_text())
    answers = [json.loads(ln) for ln in (Path(a.run_dir) / "answers.jsonl").read_text().splitlines() if ln.strip()]
    ranked = [t for t in build(answers, panel) if t["lost_prompts"]][: a.top]

    out = Path(a.out)
    existing = {t["url"]: t for t in json.loads(out.read_text())} if out.exists() else {}
    for t in ranked:
        old = existing.get(t["url"], {})
        t["status"] = old.get("status", "new")       # new -> triaged -> drafted -> sent -> landed | declined | skip
        t["action"] = old.get("action")
        t["notes"] = old.get("notes", "")
        existing[t["url"]] = t
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = sorted(existing.values(), key=lambda t: -t.get("score", 0))
    out.write_text(json.dumps(merged, indent=2) + "\n")

    print(f"{len(ranked)} targets from {Path(a.run_dir).name} -> {out}\n")
    print(f"{'score':>6} {'kind':15} {'eng':>3} {'lost':>4} status     url")
    for t in ranked:
        print(f"{t['score']:>6} {t['kind']:15} {len(t['engines']):>3} {len(t['lost_prompts']):>4} {t['status']:10} {t['url'][:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
