#!/usr/bin/env python3
"""Technical SEO crawl of a site's sitemap: the problems that stop pages from being indexed or ranked.

    python3 crawl_check.py https://example.com [--limit 300] [--json <state>/seo/crawl.json]

For every sitemap URL (following sitemap indexes) it fetches the page once and reports:
    status         non-200, redirect chains (> 1 hop), redirects to another host
    indexability   noindex (meta or X-Robots-Tag), canonical pointing elsewhere, robots.txt disallow
    metadata       missing or duplicate <title> and meta description, titles over 60 characters
    content        pages whose server-rendered HTML has under 150 words of visible text (client-only pages)
    links          internal links that 404; sitemap pages no other crawled page links to (orphans)
Problems listed in gtm.json `accepted_problems` (as "<kind>: <url>" or the bare URL) are left out.
Writes the problems as JSON and the metric `seo_problems` (count) unless --dry-run. Free: plain HTTP
with a polite delay, no treg calls. Stdlib only.
"""
from __future__ import annotations

import argparse
import collections
import html
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

UA = "Mozilla/5.0 (compatible; marketing-operator-seo-check/1.0)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def fetch(url: str) -> tuple[int, dict, str]:
    """One request, no redirect following (tests replace this). Returns status, headers, body."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with OPENER.open(req, timeout=30) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, ""
    except (OSError, ValueError, http.client.HTTPException) as e:  # timeouts, TLS, bad URLs, truncated reads
        return 0, {}, f"{type(e).__name__}: {e}"


def follow(url: str, fetcher=fetch, max_hops: int = 5) -> tuple[int, str, int, dict, str]:
    hops, cur = 0, url
    while True:
        status, headers, body = fetcher(cur)
        if status in (301, 302, 303, 307, 308) and headers.get("location") and hops < max_hops:
            cur = urllib.parse.urljoin(cur, headers["location"])
            hops += 1
            continue
        return status, cur, hops, headers, body


def sitemap_urls(site: str, fetcher=fetch, limit: int = 300) -> list[str]:
    seen, out, queue = set(), [], [site.rstrip("/") + "/sitemap.xml"]
    while queue and len(out) < limit:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        status, _, _, _, body = follow(sm, fetcher)
        if status != 200:
            continue
        locs = [html.unescape(x) for x in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)]
        (queue if "<sitemapindex" in body else out).extend(locs)
    return list(dict.fromkeys(out))[:limit]


def _meta(body: str, name: str) -> str | None:
    m = re.search(rf'<meta[^>]+name=["\']{name}["\'][^>]*content=["\']([^"\']*)', body, re.I) or \
        re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*name=["\']{name}["\']', body, re.I)
    return html.unescape(m.group(1)).strip() if m else None


def _canonical(body: str) -> str | None:
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', body, re.I) or \
        re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', body, re.I)
    return m.group(1) if m else None


def _words(body: str) -> int:
    text = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", " ", body)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return len(re.findall(r"\w+", html.unescape(text)))


def _norm(u: str) -> str:
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", p.query, ""))


RISKY = re.compile(r"(log-?out|sign-?out|cart|checkout|delete|remove|unsubscribe)", re.I)


def _site_host(h: str) -> str:
    return h.lower()[4:] if h.lower().startswith("www.") else h.lower()


def crawl(site: str, limit: int = 300, fetcher=fetch, delay: float = 0.5, accepted: list | None = None) -> dict:
    # the site's real host is where its homepage ends up (apex → www and the reverse count as one site)
    _, home_final, _, _, _ = follow(site.rstrip("/") + "/", fetcher)
    host = _site_host(urllib.parse.urlsplit(home_final).netloc or urllib.parse.urlsplit(site).netloc)
    accepted = set(accepted or [])
    robots = urllib.robotparser.RobotFileParser()
    rs, _, _, _, rbody = follow(site.rstrip("/") + "/robots.txt", fetcher)
    robots.parse(rbody.splitlines() if rs == 200 else [])
    urls = sitemap_urls(site, fetcher, limit)
    problems: list[dict] = []
    titles: dict = collections.defaultdict(list)
    descs: dict = collections.defaultdict(list)
    linked: set = set()
    internal_links: set = set()

    def problem(url, kind, detail):
        problems.append({"url": url, "kind": kind, "detail": detail})

    for i, url in enumerate(urls):
        if i and delay:
            time.sleep(delay)
        if not robots.can_fetch("Googlebot", url):
            problem(url, "robots", "disallowed for Googlebot in robots.txt")
        status, final, hops, headers, body = follow(url, fetcher)
        if hops > 1:
            problem(url, "redirect_chain", f"{hops} hops to {final}")
        elif hops == 1:
            problem(url, "redirect", f"sitemap lists a redirecting URL → {final}")
        if _site_host(urllib.parse.urlsplit(final).netloc) != host:
            problem(url, "offsite", f"ends on another host: {final}")
        if status != 200:
            problem(url, "status", f"HTTP {status}")
            continue
        robots_meta = (_meta(body, "robots") or "") + " " + headers.get("x-robots-tag", "")
        if "noindex" in robots_meta.lower():
            problem(url, "noindex", robots_meta.strip())
        canon = _canonical(body)
        if canon and _norm(urllib.parse.urljoin(final, canon)) != _norm(final):
            problem(url, "canonical", f"canonical points to {canon}")
        t = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
        title = html.unescape(t.group(1)).strip() if t else ""
        if not title:
            problem(url, "title", "missing <title>")
        else:
            titles[title].append(url)
            if len(title) > 60:
                problem(url, "title", f"{len(title)} characters (over 60 gets cut in results)")
        desc = _meta(body, "description")
        if not desc:
            problem(url, "description", "missing meta description")
        else:
            descs[desc].append(url)
        if _words(body) < 150:
            problem(url, "thin_html", "under 150 words in the server-rendered HTML (client-only content?)")
        for href in re.findall(r'<a[^>]+href=["\']([^"\'#]+)', body, re.I):
            absu = urllib.parse.urljoin(final, href)
            if _site_host(urllib.parse.urlsplit(absu).netloc) == host:
                n = _norm(absu)
                if n != _norm(final):
                    linked.add(n)
                internal_links.add(absu)
    for title, us in titles.items():
        if len(us) > 1:
            for u in us:
                problem(u, "duplicate_title", f"shared with {len(us) - 1} other page(s)")
    for d, us in descs.items():
        if len(us) > 1:
            for u in us:
                problem(u, "duplicate_description", f"shared with {len(us) - 1} other page(s)")
    sitemap_norm = {_norm(u) for u in urls}
    for u in urls:
        if _norm(u) not in linked and _norm(u) != _norm(site):
            problem(u, "orphan", "no crawled page links here")
    broken = 0
    for link in sorted(internal_links - set(urls))[:100]:
        if _norm(link) in sitemap_norm or RISKY.search(urllib.parse.urlsplit(link).path):
            continue
        if delay:
            time.sleep(delay)
        status, *_ = follow(link, fetcher)
        if status in (404, 410):
            broken += 1
            problem(link, "broken_link", f"HTTP {status}, linked from the site")
    kept = [p for p in problems if f"{p['kind']}: {p['url']}" not in accepted and p["url"] not in accepted]
    counts = collections.Counter(p["kind"] for p in kept)
    return {"site": site, "pages": len(urls), "problems": kept, "counts": dict(counts),
            "accepted": len(problems) - len(kept)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--json", help="default <state>/seo/crawl.json")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between page fetches")
    ap.add_argument("--dry-run", action="store_true", help="print only; write no files or metrics")
    a = ap.parse_args()
    try:
        accepted = gtm.load_state().get("accepted_problems", [])
    except SystemExit:
        accepted = []
    out = crawl(a.site, a.limit, delay=a.delay, accepted=accepted)
    if not out["pages"]:
        print(f"no URLs found in {a.site.rstrip('/')}/sitemap.xml", file=sys.stderr)
        return 1
    if not a.dry_run:
        path = Path(a.json) if a.json else gtm.R() / "seo" / "crawl.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2) + "\n")
        gtm.metric_add("seo_problems", len(out["problems"]), source="crawl_check", track="demand")
    print(json.dumps({"pages": out["pages"], "counts": out["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
