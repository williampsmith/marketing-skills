#!/usr/bin/env python3
"""Search Console through treg's connected account: clicks, rankings and pages in search → gtm.py metrics.

    python3 search_console.py [sc-domain:example.com] [--brand acme --brand "acme app"] [--dry-run]

The property defaults to the one stored with `gtm.py connect search_console <property>`.

Writes these metrics (track demand), each a 28-day window ending 3 days ago (Search Console lags):
    search_clicks_28d          total clicks (site total, no dimensions: summing rows undercounts)
    nonbrand_clicks_28d        clicks on queries that don't contain a brand term (anonymised queries are
                               missing from query rows, so this undercounts against the total)
    query_top10_share          share of non-brand queries with ≥ 10 impressions whose average position ≤ 10,
                               or of the queries in <state>/seo/queries.csv when the seo skill keeps a query map
    indexed_ratio              proxy: share of sitemap URLs that appeared in search at least once in 90 days
                               (Search Console's API has no index-coverage report)

The call is free (connected account; Search Console quotas apply). Endpoint checked 2026-11-01:
google-search-console.performance — verify with treg catalog_get. Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

ENDPOINT = "google-search-console.performance"
LAG_DAYS = 3


def run_treg(argv: list[str]) -> subprocess.CompletedProcess:
    """The only process call (tests replace it)."""
    return subprocess.run(argv, capture_output=True, text=True, timeout=120)


def treg_call(site: str, body: dict) -> dict:
    """One Search Console query through treg. Any failure raises; an error is never read as zero."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(body, f)
        path = f.name
    try:
        try:
            p = run_treg(["treg", "--json", "call", ENDPOINT, "--method", "POST", "--query", f"siteUrl={site}",
                          "--data", "@" + path])
        except FileNotFoundError:
            raise RuntimeError("the treg CLI isn't installed or isn't on PATH") from None
    finally:
        Path(path).unlink(missing_ok=True)
    lines = p.stdout.strip().splitlines()
    if p.returncode != 0 or not lines:
        raise RuntimeError(f"treg exited {p.returncode}: {(lines[-1] if lines else p.stderr or 'no output').strip()[:300]}")
    d = json.loads(lines[-1])
    err = _find(d, "error")
    status = _find(d, "status")
    if err or (isinstance(status, int) and status >= 400):
        raise RuntimeError(f"Search Console error: {str(err or status)[:300]}")
    if _find(d, "rows") is None and _find(d, "responseAggregationType") is None:
        raise RuntimeError(f"unrecognised Search Console response: {str(d)[:300]}")
    return d


def _find(obj, key):
    """First value for key anywhere in treg's envelope."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find(v, key)
            if r is not None:
                return r
    return None


def rows_of(resp) -> list[dict]:
    """The Search Console `rows` list wherever treg's envelope put it; [] when the property has no data."""
    r = _find(resp, "rows")
    return r if isinstance(r, list) else []


def fetch_sitemap_urls(site_url: str, limit: int = 5000) -> list[str]:
    seen, urls, queue = set(), [], [site_url.rstrip("/") + "/sitemap.xml"]
    while queue and len(urls) < limit:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            req = urllib.request.Request(sm, headers={"User-Agent": "marketing-operator/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read(20_000_000).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - a missing sitemap just yields no ratio
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
        if "<sitemapindex" in body:
            queue.extend(locs)
        else:
            urls.extend(locs)
    return urls[:limit]


def is_brand(query: str, brands: list[str]) -> bool:
    q = query.lower()
    return any(b.lower() in q for b in brands if b)


def window(days: int) -> tuple[str, str]:
    end = dt.date.today() - dt.timedelta(days=LAG_DAYS)
    return (end - dt.timedelta(days=days - 1)).isoformat(), end.isoformat()


def query_map(root: Path) -> set[str]:
    p = root / "seo" / "queries.csv"
    if not p.exists():
        return set()
    with p.open() as f:
        return {r["query"].strip().lower() for r in csv.DictReader(f) if r.get("query")}


def update_query_map(root: Path, positions: dict) -> None:
    """Write each mapped query's average position and today's date back into the seo query map."""
    p = root / "seo" / "queries.csv"
    if not positions or not p.exists():
        return
    with p.open(newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    for col in ("position", "last_checked"):
        if col not in fields:
            fields.append(col)
    for r in rows:
        q = (r.get("query") or "").strip().lower()
        if q in positions:
            r["position"] = positions[q]
            r["last_checked"] = dt.date.today().isoformat()
    tmp = p.with_suffix(".csv.tmp")
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(p)


def measure(site: str, site_url: str, brands: list[str], days: int, call=treg_call, sitemap=fetch_sitemap_urls) -> dict:
    start, end = window(days)
    total = rows_of(call(site, {"startDate": start, "endDate": end}))
    clicks = int(sum(r.get("clicks", 0) for r in total)) if total else None  # no rows: no data yet, not zero
    qrows = rows_of(call(site, {"startDate": start, "endDate": end, "dimensions": ["query"], "rowLimit": 25000}))
    nonbrand = [r for r in qrows if not is_brand(r["keys"][0], brands)]
    mapped = query_map(gtm.R())
    if mapped:
        pool = [r for r in qrows if r["keys"][0].lower() in mapped]
        denom = len(mapped)
        basis = "query map"
    else:
        pool = [r for r in nonbrand if r.get("impressions", 0) >= 10]
        denom = len(pool)
        basis = "non-brand queries with 10+ impressions"
    top10 = sum(1 for r in pool if r.get("position", 99) <= 10)
    positions = {r["keys"][0].lower(): round(r.get("position", 0), 1) for r in pool} if mapped else {}
    out = {"window": [start, end], "search_clicks_28d": clicks,
           "nonbrand_clicks_28d": int(sum(r.get("clicks", 0) for r in nonbrand)) if clicks is not None else None,
           "query_top10_share": round(top10 / denom, 4) if denom else None, "top10_basis": basis,
           "_positions": positions}
    if site_url:
        urls = sitemap(site_url)
        if urls:
            s90, e90 = window(90)
            prow = rows_of(call(site, {"startDate": s90, "endDate": e90, "dimensions": ["page"], "rowLimit": 25000}))
            seen = {r["keys"][0].rstrip("/") for r in prow if r.get("impressions", 0) > 0}
            out["indexed_ratio"] = round(sum(1 for u in urls if u.rstrip("/") in seen) / len(urls), 4)
            out["sitemap_urls"] = len(urls)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site", nargs="?", help="Search Console property (default: the one `gtm.py connect` stored)")
    ap.add_argument("--site-url", help="site to read the sitemap from (default gtm.json site_url)")
    ap.add_argument("--brand", action="append", default=[], help="brand term; repeatable (default: from gtm.json)")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write no metrics")
    a = ap.parse_args()
    s = gtm.load_state()
    stored = s["connections"].get("search_console")
    site = a.site or (stored if isinstance(stored, str) else None)
    if not site:
        print("no property: pass it, or `gtm.py connect search_console sc-domain:example.com`", file=sys.stderr)
        return 1
    brands = a.brand or s.get("brand_terms") or []
    if not brands:
        print("no brand terms: pass --brand or set brand_terms in gtm.json (non-brand numbers need them)", file=sys.stderr)
        return 1
    try:
        out = measure(site, a.site_url or s.get("site_url", ""), brands, 28)
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"search console: {e}", file=sys.stderr)
        return 1
    if not a.dry_run:
        update_query_map(gtm.R(), out.pop("_positions", {}))
        for m in ("search_clicks_28d", "nonbrand_clicks_28d", "query_top10_share", "indexed_ratio"):
            if out.get(m) is not None:
                gtm.metric_add(m, out[m], source="search-console", track="demand")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
