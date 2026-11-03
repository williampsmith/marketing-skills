#!/usr/bin/env python3
"""Watch current events in the product's category and keep a scored queue of stories worth acting on.

    python3 news_watch.py init --query "improperly redacted" --term redaction --signal unredacted
    python3 news_watch.py sweep [--max-usd 0.10] [--dry-run]       # search, dedupe, score, queue
    python3 news_watch.py list [--status new|all] [--limit 20]
    python3 news_watch.py decide ID --as refresh|react|pitch|skip [--page SLUG] [--note TEXT] [--quote "..."]

Config is <state>/news.json (written by `init`, edited by hand or by the agent from
product-context.md):

    queries   searches to run on every source ("improperly redacted", "redaction failure PDF")
    terms     the category's words; a story must contain one to count ("redaction", "redacted")
    signals   phrases that make a story ours, weighted above terms ("unredacted", "copy and paste")
    exclude   phrases that mark a false friend ("redacted version released")
    sources   news, google_news, hackernews, x, courtlistener (the last needs COURTLISTENER_TOKEN)
    court_queries   CourtListener full-text queries, e.g. "\"inadvertently filed\" unredacted"

Every source but CourtListener goes through treg (`treg --json call …`); each call carries a cost ceiling
and the sweep stops before --max-usd. CourtListener's API is free with a token from the environment.

What it stores, all in the state store (never the product repo):
    <state>/news/seen.json          story ids already queued, so a story is offered once
    <state>/news/candidates.jsonl   the queue: score, dates, outlets, decision
    <state>/news/<date>.md          the sweep's report

Scoring is deterministic and explainable: signal and term matches, recency, how many outlets carry the
story, and engagement where the source has it. Stories that mention death, victims, children and the like
are flagged `sensitive`: they may only feed a page refresh that explains the mechanism, unless a human
quotes their approval.

Endpoints checked 2026-11-02 (verify with treg catalog_get): treg.web.search.news,
treg.google.serp.news, crawl4ai.hackernews.search.stories, treg.x.search.posts; CourtListener
REST v4 /search/ with type=rd. Stdlib only; Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

SOURCES = ("news", "google_news", "hackernews", "x", "courtlistener")
ENDPOINTS = {  # checked 2026-11-02
    "news": "treg.web.search.news",
    "google_news": "treg.google.serp.news",
    "hackernews": "crawl4ai.hackernews.search.stories",
    "x": "treg.x.search.posts",
}
# Ceiling per call (X-Treg-Route-Max-Cost) and what the budget check assumes a call costs before it runs.
CALL_CEILING_USD = {"news": 0.01, "google_news": 0.005, "hackernews": 0.002, "x": 0.005, "courtlistener": 0.0}
COURTLISTENER = "https://www.courtlistener.com/api/rest/v4/search/"
DECISIONS = ("refresh", "react", "pitch", "skip")
# Sensitive vocabulary. Stems match any word ending ("abus" → abuse, abused, abusive); short words match
# exactly so "die" doesn't catch "diesel" or "minor" "minority".
SENSITIVE_STEMS = ("death", "murder", "suicid", "victim", "survivor", "shooting", "assault", "abus", "child",
                   "traffick", "overdos", "funeral", "sexual", "molest", "teenager", "harass", "stalk")
SENSITIVE_WORDS = ("die", "dies", "died", "dying", "dead", "kill", "kills", "killed", "killing", "rape", "raped",
                   "rapes", "raping", "kid", "kids", "teen", "teens", "girl", "girls", "boy", "boys", "minor", "minors")
DEFAULT_CONFIG = {
    "queries": [], "terms": [], "signals": [], "exclude": [],
    "sources": ["news", "google_news", "hackernews"],
    "court_queries": [],
    "max_age_days": 30, "react_days": 3, "pitch_days": 7, "min_score": 0.45,
    "x_min_engagement": 10,
    "sensitive_extra": [],
}
SEEN_KEEP_DAYS = 180
# Posts are opinions about a story, not the story: they rank below reporting on the same evidence.
SOURCE_WEIGHT = {"news": 1.0, "google_news": 1.0, "courtlistener": 1.0, "hackernews": 0.95, "x": 0.8}


# --------------------------------------------------------------------------- config and storage
def cfg_path() -> Path:
    return gtm.R() / "news.json"


def news_dir() -> Path:
    return gtm.R() / "news"


def load_config() -> dict:
    p = cfg_path()
    if not p.exists():
        raise SystemExit(f"no {p}: run `news_watch.py init` first (see the news skill)")
    c = {**DEFAULT_CONFIG, **json.loads(p.read_text())}
    bad = [s for s in c["sources"] if s not in SOURCES]
    if bad:
        raise SystemExit(f"unknown sources in news.json: {', '.join(bad)} (use {', '.join(SOURCES)})")
    if not c["queries"] and not c["court_queries"]:
        raise SystemExit("news.json has no queries: add some with `news_watch.py init --query …`")
    if not c["terms"] and not c["signals"]:
        raise SystemExit("news.json needs terms or signals, or every story would score zero")
    if not plan(c):
        raise SystemExit("news.json plans no searches: queries need a source other than courtlistener, "
                         "court_queries need the courtlistener source")
    return c


def candidates() -> list[dict]:
    return gtm.read_jsonl(news_dir() / "candidates.jsonl")


# --------------------------------------------------------------------------- dates and text
def parse_date(x) -> dt.date | None:
    """Best effort over the formats providers return. Unknown → None (treated as undated)."""
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        x = float(x) / 1000 if float(x) > 1e11 else float(x)  # epoch milliseconds
        try:
            return dt.datetime.fromtimestamp(x, dt.timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    s = str(x).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return dt.date.fromisoformat(m.group(1))
        except ValueError:
            return None
    try:
        return email.utils.parsedate_to_datetime(s).date()
    except (TypeError, ValueError, IndexError):
        pass
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)  # US month/day/year, with or without a time after it
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    plain = re.sub(r"(?<=[A-Za-z])\.", "", s)  # "Sep. 5, 2026"
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return dt.datetime.strptime(plain, fmt).date()
        except ValueError:
            pass
    low = s.lower()
    if low in ("today", "just now"):
        return gtm.today()
    if low == "yesterday":
        return gtm.today() - dt.timedelta(days=1)
    m = re.match(r"(an?|\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", s, re.I)
    if m:
        n = 1 if m.group(1).lower() in ("a", "an") else int(m.group(1))
        unit = m.group(2).lower()
        days = {"second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
        return gtm.today() - dt.timedelta(days=days)
    return None


def canonical_url(u: str) -> str:
    p = urllib.parse.urlsplit(u.strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    host = re.sub(r"^www\.", "", p.netloc.lower())
    return urllib.parse.urlunsplit((p.scheme.lower() or "https", host, p.path.rstrip("/") or "/",
                                    urllib.parse.urlencode(q), ""))


def story_key(title: str) -> str:
    """Stories syndicated across outlets share a headline; group them by its first words."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return hashlib.sha1(" ".join(words[:10]).encode()).hexdigest()[:12]


def phrase_in(text: str, phrase: str) -> bool:
    """A phrase at a word start, with any word ending: "redact" matches redacted, redactions, redacting."""
    return re.search(rf"(?<![\w-]){re.escape(phrase.lower())}\w*", text) is not None


def word_in(text: str, word: str) -> bool:
    """Exact word (the sensitive list: "minor" must not match "minority")."""
    return re.search(rf"(?<![\w-]){re.escape(word.lower())}(?![\w-])", text) is not None


def _s(x) -> str:
    if isinstance(x, dict):
        return str(x.get("name") or x.get("title") or "")
    return "" if x is None else str(x)


# --------------------------------------------------------------------------- normalise each source
def _row(source, title, url, outlet, published, snippet="", engagement=0, query="") -> dict | None:
    title, url = _s(title).strip(), _s(url).strip()
    if not title or not url.startswith(("http://", "https://")):
        return None
    pub = parse_date(published)
    return {"source": source, "title": re.sub(r"\s+", " ", title)[:300], "url": url,
            "outlet": _s(outlet).strip()[:120], "published": pub.isoformat() if pub else "",
            "snippet": re.sub(r"\s+", " ", _s(snippet)).strip()[:500], "engagement": int(engagement or 0),
            "query": query}


def normalize(source: str, out, query: str) -> list[dict]:
    """Map a provider's native rows to one shape. Unknown fields are ignored, not guessed."""
    rows = []
    if not isinstance(out, dict):
        return rows
    if source in ("news", "google_news"):
        for r in out.get("results") or []:
            rows.append(_row(source, r.get("title"), r.get("url") or r.get("link"),
                             r.get("publisher") or r.get("source") or r.get("site_name"),
                             r.get("published_at") or r.get("publishedDate") or r.get("published") or r.get("date"),
                             r.get("snippet") or r.get("description") or "", query=query))
    elif source == "hackernews":
        for r in out.get("rows") or out.get("results") or []:
            rows.append(_row(source, r.get("title"), r.get("url") or r.get("hn_url"), "Hacker News",
                             r.get("created"), r.get("text") or "",
                             engagement=(r.get("points") or 0) + (r.get("comments") or 0), query=query))
    elif source == "x":
        for r in out.get("posts") or []:
            pid = str(r.get("id") or "")
            text = _s(r.get("text")).strip()
            if (not pid.isdigit() or r.get("isReply") or r.get("isRetweet") or r.get("retweeted_status")
                    or text.startswith("@") or re.match(r"RT\s+@", text)):
                continue  # replies and reposts are conversation, not news
            # no author names or handles are kept: the post id is enough to open it, and mentions are masked
            text = re.sub(r"(?<!\w)@\w{1,15}", "@user", text)
            rows.append(_row(source, text[:140], f"https://x.com/i/status/{pid}", "X",
                             r.get("createdUtc") or r.get("createdAt") or r.get("created_at"), text,
                             engagement=sum(int(r.get(k) or 0) for k in ("likeCount", "retweetCount", "replyCount", "quoteCount")),
                             query=query))
    elif source == "courtlistener":
        for r in out.get("results") or []:
            path = r.get("absolute_url") or ""
            desc = r.get("short_description") or r.get("description") or ""
            title = f"{r.get('caseName') or 'Unknown case'}: {desc}".strip(": ")
            rows.append(_row(source, title, "https://www.courtlistener.com" + path if path.startswith("/") else path,
                             r.get("court") or r.get("court_id") or "court",
                             r.get("entry_date_filed") or r.get("dateFiled"), r.get("snippet") or "", query=query))
    return [r for r in rows if r]


# --------------------------------------------------------------------------- fetching (tests replace these)
def run_treg(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=120)


def treg_call(endpoint: str, body: dict, ceiling: float) -> tuple[dict, float]:
    """One treg call. Returns (output, usd charged). Any failure raises; a failure is never read as 'no news'."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(body, f)
        path = f.name
    try:
        try:
            p = run_treg(["treg", "--json", "call", endpoint, "--method", "POST", "--data", "@" + path,
                          "--header", f"X-Treg-Route-Max-Cost: {ceiling:.4f}"])
        except FileNotFoundError:
            raise RuntimeError("the treg CLI isn't installed or isn't on PATH") from None
    finally:
        Path(path).unlink(missing_ok=True)
    lines = p.stdout.strip().splitlines()
    if p.returncode != 0 or not lines:
        raise RuntimeError(f"treg exited {p.returncode}: {(lines[-1] if lines else p.stderr or 'no output').strip()[:300]}")
    d = json.loads(lines[-1])
    if d.get("error"):
        raise RuntimeError(f"treg: {str(d.get('error'))[:300]}")
    res = d.get("result", d)
    out = res.get("output", res) if isinstance(res, dict) else {}
    micro = (d.get("_treg") or {}).get("charged_micro")
    if micro is None and isinstance(res, dict):
        micro = (res.get("_treg") or {}).get("charged_micro")
    return out, (None if micro is None else micro / 1_000_000)


def http_get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "marketing-skills news_watch", **headers})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read(5_000_000).decode("utf-8", "replace"))


def courtlistener(query: str, since: dt.date) -> dict:
    token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("COURTLISTENER_TOKEN isn't set")
    params = {"q": query, "type": "rd", "order_by": "entry_date_filed desc",
              "filed_after": since.strftime("%m/%d/%Y")}
    return http_get_json(COURTLISTENER + "?" + urllib.parse.urlencode(params), {"Authorization": f"Token {token}"})


# The list each source's answer must carry. Missing means the provider's shape changed: an error, not "no news".
EXPECTED = {"news": ("results",), "google_news": ("results",), "hackernews": ("rows", "results"),
            "x": ("posts",), "courtlistener": ("results",)}


def check_shape(source: str, out) -> None:
    if not isinstance(out, dict) or not any(isinstance(out.get(k), list) for k in EXPECTED[source]):
        keys = ", ".join(sorted(out)[:8]) if isinstance(out, dict) else type(out).__name__
        raise RuntimeError(f"unexpected response shape (no {' or '.join(EXPECTED[source])}; got {keys})")


def body_for(source: str, q: str) -> dict:
    if source == "hackernews":
        return {"query": q}
    if source in ("news", "google_news"):
        return {"q": q, "limit": 20}
    return {"q": q}


# --------------------------------------------------------------------------- scoring
def is_sensitive(text: str, cfg: dict) -> bool:
    text = text.lower()
    return (any(phrase_in(text, w) for w in (*SENSITIVE_STEMS, *cfg.get("sensitive_extra", [])))
            or any(word_in(text, w) for w in SENSITIVE_WORDS))


def score(c: dict, cfg: dict, coverage: int, group_text: str = "") -> tuple[float, list[str], bool]:
    text = f"{c['title']} {c['snippet']}".lower()
    why = []
    sig = [x for x in cfg["signals"] if phrase_in(text, x)]
    # an exclusion removes a false friend; a story that also carries a signal is ours anyway
    if not sig and any(phrase_in(text, x) for x in cfg["exclude"]):
        return 0.0, ["excluded phrase"], False
    terms = [x for x in cfg["terms"] if phrase_in(text, x)]
    if not sig and not terms:
        return 0.0, ["no category term"], False
    s = 0.0
    if sig:
        s += 0.45 + 0.05 * min(len(sig) - 1, 2)
        why.append("signals: " + ", ".join(sig[:3]))
    if terms:
        s += 0.2
        why.append("terms: " + ", ".join(terms[:3]))
    pub = parse_date(c["published"])
    if pub:
        age = max(0, (gtm.today() - pub).days)
        rec = max(0.0, 1 - age / max(1, cfg["max_age_days"]))
        s += 0.2 * rec
        why.append(f"{age}d old")
    else:
        s += 0.05
        why.append("undated")
    if coverage > 1:
        s += min(0.1, 0.03 * (coverage - 1))
        why.append(f"{coverage} outlets")
    if c["engagement"]:
        s += min(0.05, 0.01 * math.log10(1 + c["engagement"]))
    s *= SOURCE_WEIGHT.get(c["source"], 1.0)
    sensitive = is_sensitive(f"{text} {group_text}", cfg)
    if sensitive:
        why.append("sensitive")
    return round(min(1.0, s), 3), why, sensitive


# --------------------------------------------------------------------------- commands
def cmd_init(a) -> int:
    p = cfg_path()
    if p.exists() and not a.force:
        c = json.loads(p.read_text())
    else:
        c = dict(DEFAULT_CONFIG)
    for key, vals in (("queries", a.query), ("terms", a.term), ("signals", a.signal),
                      ("exclude", a.exclude), ("court_queries", a.court_query)):
        c[key] = sorted(set(c.get(key, [])) | {v.strip() for v in vals if v.strip()})
    bad = [s for s in a.source + a.drop_source if s not in SOURCES]
    if bad:
        print(f"unknown source {', '.join(bad)} (use {', '.join(SOURCES)})", file=sys.stderr)
        return 1
    if a.source or a.drop_source:
        # --source adds to the list (the first --source on a new config replaces the defaults)
        base = [] if (a.source and (a.force or not p.exists())) else c.get("sources", [])
        c["sources"] = [s for s in SOURCES if (s in base or s in a.source) and s not in a.drop_source]
    p.parent.mkdir(parents=True, exist_ok=True)
    gtm.atomic_write(p, json.dumps(c, indent=2) + "\n")
    print(json.dumps(c, indent=2))
    return 0


def plan(cfg: dict) -> list[tuple[str, str]]:
    calls = []
    for src in cfg["sources"]:
        qs = cfg["court_queries"] if src == "courtlistener" else cfg["queries"]
        calls += [(src, q) for q in qs]
    return calls


def cmd_sweep(a) -> int:
    cfg = load_config()
    calls = plan(cfg)
    if a.dry_run:
        est = sum(CALL_CEILING_USD[s] for s, _ in calls)
        print(json.dumps({"calls": [{"source": s, "query": q} for s, q in calls],
                          "worst_case_usd": round(est, 4), "max_usd": a.max_usd}, indent=2))
        return 0
    since = gtm.today() - dt.timedelta(days=cfg["max_age_days"])
    # charged: what treg reported. reserved: calls whose charge is unknown (not reported, or the call
    # failed after it may have been billed), counted at their ceiling. The cap applies to the sum.
    charged, reserved, raw, errors, skipped, ran = 0.0, 0.0, [], [], [], 0
    for src, q in calls:
        ceiling = CALL_CEILING_USD[src]
        if charged + reserved + ceiling > a.max_usd + 1e-9:
            skipped.append(f"{src}: {q} (budget)")
            continue
        ran += 1
        try:
            if src == "courtlistener":
                out = courtlistener(q, since)
            else:
                usd = None
                try:
                    out, usd = treg_call(ENDPOINTS[src], body_for(src, q), ceiling)
                finally:
                    if usd is None:
                        reserved += ceiling
                    else:
                        charged += usd
            check_shape(src, out)
            raw += normalize(src, out, q)
        except Exception as e:  # noqa: BLE001 - one source failing must not stop the others
            errors.append(f"{src}: {q}: {type(e).__name__}: {str(e)[:200]}")
    spent = charged + reserved

    with gtm.locked():
        nd = news_dir()
        nd.mkdir(parents=True, exist_ok=True)
        seen_p = nd / "seen.json"
        seen = json.loads(seen_p.read_text()) if seen_p.exists() else {}
        # {id: {"date", "queued"}}; a bare date is the 0.9.0 format and counts as queued
        seen = {k: (v if isinstance(v, dict) else {"date": v, "queued": True}) for k, v in seen.items()}
        cutoff = (gtm.today() - dt.timedelta(days=SEEN_KEEP_DAYS)).isoformat()
        seen = {k: v for k, v in seen.items() if v["date"] >= cutoff}
        queue = candidates()
        waiting = {c["id"] for c in queue if c["status"] == "new"}

        # group syndicated copies of one story; keep the dated, most-engaged copy as the lead
        groups: dict[str, list[dict]] = {}
        for r in raw:
            pub = parse_date(r["published"])
            if pub and pub < since:
                continue
            if r["source"] == "x" and r["engagement"] < cfg["x_min_engagement"]:
                continue
            groups.setdefault(story_key(r["title"]), []).append(r)
        fresh = []
        for key, rows in groups.items():
            urls = {canonical_url(r["url"]) for r in rows}
            ids = {hashlib.sha1(u.encode()).hexdigest()[:12] for u in urls} | {key}
            # a story already queued is offered once; one that scored too low before is scored again,
            # since more outlets picking it up can lift it over the line
            if key in waiting or any(seen.get(i, {}).get("queued") for i in ids):
                continue
            lead = sorted(rows, key=lambda r: (not r["published"], -r["engagement"]))[0]
            outlets = sorted({r["outlet"] for r in rows if r["outlet"]})
            group_text = " ".join(f"{r['title']} {r['snippet']}" for r in rows)
            sc, why, sensitive = score(lead, cfg, len(outlets) or 1, group_text)
            queued = sc >= cfg["min_score"]
            for i in ids:
                seen[i] = {"date": gtm.today().isoformat(), "queued": queued}
            if not queued:
                continue
            pub = parse_date(lead["published"])
            # an undated story gets no react or pitch window until someone reads its date (decide --published)
            fresh.append({"id": key, "found": gtm.today().isoformat(), "status": "new", "score": sc, "why": why,
                          "sensitive": sensitive, "title": lead["title"], "url": lead["url"],
                          "outlets": outlets, "sources": sorted({r["source"] for r in rows}),
                          "published": lead["published"], "snippet": lead["snippet"], "query": lead["query"],
                          "react_by": (pub + dt.timedelta(days=cfg["react_days"])).isoformat() if pub else "",
                          "pitch_by": (pub + dt.timedelta(days=cfg["pitch_days"])).isoformat() if pub else "",
                          "also": sorted({r["url"] for r in rows} - {lead["url"]})[:5]})
        fresh.sort(key=lambda c: -c["score"])
        # the queue first, then seen: a crash in between re-offers stories, which `waiting` then dedupes
        gtm.write_jsonl(nd / "candidates.jsonl", queue + fresh)
        gtm.atomic_write(seen_p, json.dumps(seen, indent=1, sort_keys=True) + "\n")
        report = [f"# News sweep — {gtm.today().isoformat()}", "",
                  f"{len(calls)} searches, {len(raw)} results, {len(groups)} stories, {len(fresh)} new candidates, "
                  f"${charged:.4f} charged" + (f", ${reserved:.4f} reserved for calls with no reported charge" if reserved else "")
                  + ".", ""]
        for c in fresh:
            flag = " **sensitive**" if c["sensitive"] else ""
            report.append(f"- [{c['score']:.2f}]{flag} [{c['title']}]({c['url']}) — {', '.join(c['outlets']) or c['sources'][0]}"
                          f", {c['published'] or 'undated'}; react by {c['react_by'] or 'read its date first'} (`{c['id']}`)")
        if errors:
            report += ["", "## Errors", *[f"- {e}" for e in errors]]
        if skipped:
            report += ["", "## Skipped for budget", *[f"- {s}" for s in skipped]]
        gtm.atomic_write(nd / f"{gtm.today().isoformat()}.md", "\n".join(report) + "\n")
    print(json.dumps({"searches": ran, "planned": len(calls), "results": len(raw), "new": len(fresh),
                      "cost_usd": round(spent, 4), "charged_usd": round(charged, 4), "reserved_usd": round(reserved, 4),
                      "errors": errors, "skipped_for_budget": skipped,
                      "top": [{k: c[k] for k in ("id", "score", "title", "sensitive", "react_by")} for c in fresh[:10]]},
                     indent=2))
    # nothing ran, or everything that ran failed: a broken sweep, not a quiet week
    return 1 if ran == 0 or len(errors) == ran else 0


def cmd_list(a) -> int:
    rows = candidates()
    if a.status != "all":
        rows = [r for r in rows if r["status"] == a.status]
    rows.sort(key=lambda r: (-r["score"], r["found"]))
    print(json.dumps(rows[: a.limit], indent=2))
    return 0


def cmd_decide(a) -> int:
    with gtm.locked():
        rows = candidates()
        hit = [r for r in rows if r["id"] == a.id]
        if not hit:
            print(f"no candidate {a.id}", file=sys.stderr)
            return 1
        c = hit[-1]  # the newest row if a story was ever queued twice
        today = gtm.today().isoformat()
        if a.sensitive and not c.get("sensitive"):
            c["sensitive"] = True  # one way: reading the story can only add the flag, and it sticks
            gtm.write_jsonl(news_dir() / "candidates.jsonl", rows)
        if a.published and not c.get("published"):
            pub = parse_date(a.published)
            if not pub:
                print("--published takes YYYY-MM-DD", file=sys.stderr)
                return 1
            cfg = {**DEFAULT_CONFIG, **(json.loads(cfg_path().read_text()) if cfg_path().exists() else {})}
            c.update({"published": pub.isoformat(),
                      "react_by": (pub + dt.timedelta(days=cfg["react_days"])).isoformat(),
                      "pitch_by": (pub + dt.timedelta(days=cfg["pitch_days"])).isoformat()})
        if a.decision in ("react", "pitch"):
            by = c["react_by"] if a.decision == "react" else c["pitch_by"]
            if not by:
                print(f"this story has no date, so no {a.decision} window: read it and pass --published YYYY-MM-DD",
                      file=sys.stderr)
                return 1
            if today > by:
                print(f"too late to {a.decision} (window closed {by}); a page refresh still works", file=sys.stderr)
                return 1
            if c.get("sensitive"):
                if os.environ.get("MARKETING_UNATTENDED"):
                    print("a sensitive story can't be used for a reaction or pitch in an unattended run; "
                          "queue it for a human or use it as a refresh that explains the mechanism", file=sys.stderr)
                    return 1
                if not a.quote:
                    print("a sensitive story needs the human's approval quoted: --quote \"<their words>\"", file=sys.stderr)
                    return 1
        if a.decision == "refresh" and not a.page:
            print("a refresh names the page it updates: --page <slug or path>", file=sys.stderr)
            return 1
        c.update({"status": a.decision, "decided": today})
        for k in ("page", "note", "quote"):
            if getattr(a, k):
                c[k] = getattr(a, k)
        gtm.write_jsonl(news_dir() / "candidates.jsonl", rows)
    print(json.dumps(c, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create or extend <state>/news.json")
    p.add_argument("--query", action="append", default=[])
    p.add_argument("--term", action="append", default=[])
    p.add_argument("--signal", action="append", default=[])
    p.add_argument("--exclude", action="append", default=[])
    p.add_argument("--court-query", action="append", default=[])
    p.add_argument("--source", action="append", default=[], help="add a source")
    p.add_argument("--drop-source", action="append", default=[], help="remove a source")
    p.add_argument("--force", action="store_true", help="start from defaults instead of extending")
    p = sub.add_parser("sweep", help="search every source, dedupe, score, queue")
    p.add_argument("--max-usd", type=gtm.finite_float, default=0.10)
    p.add_argument("--dry-run", action="store_true", help="print the planned searches and worst-case cost")
    p = sub.add_parser("list", help="the queue")
    p.add_argument("--status", default="new", choices=("new", "all", *DECISIONS))
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("decide", help="record what to do with a candidate")
    p.add_argument("id")
    p.add_argument("--as", dest="decision", required=True, choices=DECISIONS)
    p.add_argument("--page", default="")
    p.add_argument("--note", default="")
    p.add_argument("--quote", default="")
    p.add_argument("--sensitive", action="store_true", help="mark the story sensitive after reading it (one way)")
    p.add_argument("--published", default="", help="the story's date, read from it, for an undated candidate")
    a = ap.parse_args()
    return {"init": cmd_init, "sweep": cmd_sweep, "list": cmd_list, "decide": cmd_decide}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
