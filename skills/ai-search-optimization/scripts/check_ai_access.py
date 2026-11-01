#!/usr/bin/env python3
"""Check whether AI search bots can reach, read and cite a site.

    python3 check_ai_access.py https://example.com
    python3 check_ai_access.py https://example.com /pricing /docs/quickstart --json out.json

Reports, per bot: what robots.txt says, and what the server returns when asked
with that bot's user agent (403s and bot challenges show up here). Then
/llms.txt, the sitemap, and for each page whether the main text, title,
description, canonical, JSON-LD and a modified date are in the raw HTML.

A spoofed user agent tests user-agent rules only. CDNs that verify bots by IP
(Cloudflare, Akamai, Vercel) can block the spoof and let the real bot through,
or the reverse: confirm in the CDN's bot / AI-crawler settings and its logs.
Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urljoin, urlparse

# token -> (role, user agent sent). Roles: search = builds the engine's index,
# user = fetches live when a person asks, train = model training only.
BOTS = {
    "OAI-SearchBot": ("search", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot"),
    "ChatGPT-User": ("user", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"),
    "GPTBot": ("train", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot"),
    "Claude-SearchBot": ("search", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-SearchBot/1.0; +Claude-SearchBot@anthropic.com"),
    "Claude-User": ("user", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-User/1.0; +Claude-User@anthropic.com"),
    "ClaudeBot": ("train", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ClaudeBot/1.0; +claudebot@anthropic.com"),
    "PerplexityBot": ("search", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot"),
    "Perplexity-User": ("user", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user"),
    "Googlebot": ("search", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    "Bingbot": ("search", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36"),
    "DuckAssistBot": ("user", "DuckAssistBot/1.2; (+http://duckduckgo.com/duckassistbot.html)"),
    "MistralAI-User": ("user", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; MistralAI-User/1.0; +https://docs.mistral.ai/robots"),
    "Applebot": ("search", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)"),
    "Meta-ExternalAgent": ("train", "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    "CCBot": ("train", "CCBot/2.0 (https://commoncrawl.org/faq/)"),
}
# Tokens that are robots.txt switches only (no crawler of their own).
TOKENS_ONLY = {"Google-Extended": "Gemini training/grounding; does NOT affect Google Search or AI Overviews",
               "Applebot-Extended": "Apple model training; does NOT affect Applebot search"}
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
CHALLENGE = re.compile(r"just a moment|cf-chl|challenge-platform|attention required|captcha|access denied", re.I)


def fetch(url: str, ua: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read(200_000).decode("utf-8", "replace") if e.fp else ""
        return e.code, dict(e.headers or {}), body
    except Exception as e:  # noqa: BLE001 - report any network failure as a row
        return 0, {}, f"{type(e).__name__}: {e}"


def visible_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?is)<(nav|footer|header)[^>]*>.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", page))).strip()


def page_signals(page: str) -> dict:
    def meta(name):
        m = re.search(rf'(?is)<meta[^>]+(?:name|property)=["\']{name}["\'][^>]*content=["\']([^"\']*)', page)
        return m.group(1) if m else None
    ld = re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page)
    types, ld_ok = [], True
    for block in ld:
        try:
            data = json.loads(block)
            items = data if isinstance(data, list) else data.get("@graph", [data])
            types += [str(i.get("@type")) for i in items if isinstance(i, dict)]
        except json.JSONDecodeError:
            ld_ok = False
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    canon = re.search(r'(?is)<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', page)
    words = len(visible_text(page).split())
    return {
        "title": html.unescape(title.group(1).strip()) if title else None,
        "description": meta("description"),
        "canonical": canon.group(1) if canon else None,
        "jsonld_types": types, "jsonld_valid": ld_ok,
        "modified": meta("article:modified_time") or (re.search(r'"dateModified"\s*:\s*"([^"]+)"', page) or [None, None])[1],
        "raw_html_words": words,
        "noindex": bool(re.search(r'(?is)<meta[^>]+name=["\']robots["\'][^>]*noindex', page)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site")
    ap.add_argument("paths", nargs="*", default=["/"])
    ap.add_argument("--json", dest="json_out")
    a = ap.parse_args()
    base = a.site.rstrip("/")
    if not urlparse(base).scheme:
        base = "https://" + base
    out: dict = {"site": base}
    problems: list[str] = []

    st, hdrs, robots = fetch(base + "/robots.txt", BROWSER_UA)
    out["robots_status"] = st
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots.splitlines() if st == 200 else [])
    sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots) if st == 200 else []
    print(f"robots.txt: HTTP {st}; sitemaps listed: {sitemaps or 'none'}")
    if st != 200:
        problems.append("robots.txt missing or unreachable")
    if not sitemaps:
        problems.append("robots.txt lists no Sitemap:")
    named = set(re.findall(r"(?im)^\s*user-agent:\s*(\S+)", robots)) if st == 200 else set()

    print(f"\n{'bot':20} {'role':7} {'robots':8} {'named':6} {'GET /':6} note")
    out["bots"] = {}
    for bot, (role, ua) in BOTS.items():
        allowed = rp.can_fetch(bot, base + a.paths[0]) if st == 200 else True
        code, h, body = fetch(base + a.paths[0], ua)
        note = ""
        if code in (401, 403, 429, 503) or (code == 200 and CHALLENGE.search(body[:5000]) and len(visible_text(body).split()) < 80):
            note = "blocked or challenged by the server/CDN"
        if h.get("cf-mitigated") or h.get("Cf-Mitigated"):
            note = "Cloudflare challenge (cf-mitigated)"
        is_named = any(n.lower() == bot.lower() for n in named)
        print(f"{bot:20} {role:7} {'allow' if allowed else 'DISALLOW':8} {'yes' if is_named else '-':6} {code:<6} {note}")
        out["bots"][bot] = {"role": role, "robots_allows": allowed, "named": is_named, "status": code, "note": note}
        if role in ("search", "user") and (not allowed or note):
            problems.append(f"{bot} ({role}) cannot read {a.paths[0]}: robots={'allow' if allowed else 'disallow'} http={code} {note}")
    for tok, why in TOKENS_ONLY.items():
        allowed = rp.can_fetch(tok, base + "/") if st == 200 else True
        print(f"{tok:20} token   {'allow' if allowed else 'DISALLOW':8} — {why}")
        out["bots"][tok] = {"role": "token", "robots_allows": allowed}

    for name in ("/llms.txt", "/llms-full.txt"):
        code, h, body = fetch(base + name, BROWSER_UA)
        ctype = h.get("Content-Type") or h.get("content-type") or ""
        ok = code == 200 and body.lstrip().startswith("#") and "<html" not in body[:500].lower()
        print(f"\n{name}: HTTP {code} {ctype} {'(markdown, starts with H1)' if ok else ''}")
        out[name] = {"status": code, "content_type": ctype, "ok": ok, "links": len(re.findall(r"\]\(https?://", body)) if ok else 0}
        if name == "/llms.txt" and not ok:
            problems.append("/llms.txt missing or not markdown")

    out["pages"] = {}
    print(f"\n{'page':40} {'http':5} {'words':6} {'jsonld':28} {'modified':12} title")
    for p in a.paths:
        code, h, body = fetch(urljoin(base + "/", p.lstrip("/")), BROWSER_UA)
        s = page_signals(body) if code == 200 else {}
        out["pages"][p] = {"status": code, **s}
        print(f"{p[:40]:40} {code:<5} {s.get('raw_html_words', 0):<6} {','.join(s.get('jsonld_types', []))[:28]:28} "
              f"{(s.get('modified') or '-')[:10]:12} {(s.get('title') or '-')[:50]}")
        if code != 200:
            problems.append(f"{p}: HTTP {code}")
            continue
        if s["raw_html_words"] < 150:
            problems.append(f"{p}: only {s['raw_html_words']} words in raw HTML — content is probably client-rendered")
        if not s["jsonld_types"]:
            problems.append(f"{p}: no JSON-LD")
        if not s["jsonld_valid"]:
            problems.append(f"{p}: a JSON-LD block does not parse")
        if not s["description"]:
            problems.append(f"{p}: no meta description")
        if not s["modified"]:
            problems.append(f"{p}: no machine-readable modified date")
        if s["noindex"]:
            problems.append(f"{p}: meta robots noindex")

    out["problems"] = problems
    print("\nProblems:" if problems else "\nNo problems found.")
    for x in problems:
        print(" -", x)
    if a.json_out:
        with open(a.json_out, "w") as f:
            json.dump(out, f, indent=2)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
