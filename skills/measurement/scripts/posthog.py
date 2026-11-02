#!/usr/bin/env python3
"""PostHog for the marketing operator: send the operator's events, read the funnel back.

    python3 posthog.py check                     # which keys are set; one read-only query (exit 1 if it fails)
    python3 posthog.py flush [--dry-run]         # send <state>/posthog-outbox.jsonl
    python3 posthog.py query "SELECT count() FROM events WHERE event = 'signed up'"
    python3 posthog.py pull [--dry-run]          # funnel stages, source capture, custom queries → gtm.py metrics
    python3 posthog.py sync                      # flush, then pull; each runs even if the other fails
    python3 posthog.py tracking-check [--url URL] # events in the last 2 days → tracking_ok

Keys come only from the environment, never from the state store:
    POSTHOG_PROJECT_API_KEY   phc_…  capture only (sends events)
    POSTHOG_PERSONAL_API_KEY  phx_…  scoped to query read on one project
    POSTHOG_PROJECT_ID        the numeric project id
    POSTHOG_HOST              us (default) | eu | a full https URL for a self-hosted instance

What to read is configured in <state>/gtm.json under "measurement" (see references/posthog-setup.md):
    "stage_events": {"visit": "$pageview", "signup": "signed up", ...}   # one PostHog event per funnel stage
    "source_properties": ["$initial_referring_domain", "$initial_utm_source", "heard_from"]
    "queries": {"<metric>": "<HogQL returning one number>"}             # revenue and anything custom
Stage counts are 28-day windows (the funnel templates assume it). Stdlib only; Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402  (the state engine: metrics, state root)

HOSTS = {"us": ("https://us.i.posthog.com", "https://us.posthog.com"),
         "eu": ("https://eu.i.posthog.com", "https://eu.posthog.com")}
BATCH = 100
WINDOW_DAYS = 28

# Only these properties ever leave the store, per event; free text is redacted of emails and phones.
ALLOWED = {
    "marketing_metric": ("metric", "date", "value", "source", "track", "cost_usd"),
    "marketing_bet": ("id", "track", "channel", "tactic", "metric", "baseline", "expected", "method", "status",
                      "opened", "check", "closed", "change", "cost_usd"),
}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


class PostHogError(RuntimeError):
    pass


def hosts() -> tuple[str, str]:
    h = os.environ.get("POSTHOG_HOST", "us").strip().rstrip("/")
    if h.lower() in HOSTS:
        return HOSTS[h.lower()]
    if not h.startswith("https://"):
        raise PostHogError(f"POSTHOG_HOST must be us, eu or an https URL, not {h!r}")
    m = re.match(r"https://(us|eu)\.i\.posthog\.com$", h)
    if m:  # the ingestion host people copy from posthog-js's api_host
        return HOSTS[m.group(1)]
    return h, h


def http(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: int = 60) -> dict:
    """The only network call in this module (tests replace it). Every failure is a PostHogError."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise PostHogError(f"{method} {url} → HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise PostHogError(f"{method} {url} → {e.reason}") from None
    except (OSError, ValueError) as e:  # timeouts, resets, a non-JSON answer from a wrong host
        raise PostHogError(f"{method} {url} → {type(e).__name__}: {e}") from None


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (marketing-operator tracking check)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(3_000_000).decode("utf-8", "replace")


def env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise PostHogError(f"{name} is not set")
    return v


# --------------------------------------------------------------------------- send
def distinct_id() -> str:
    from marketing_state import resolve
    return f"marketing-operator:{resolve().slug}"


def _redact(v):
    if isinstance(v, str):
        return PHONE.sub("[phone]", EMAIL.sub("[email]", v))[:500]
    return v


def clean(event: str, props: dict) -> dict:
    """Never send personal data to PostHog: an allowlist of keys per event, emails and phones redacted."""
    keys = ALLOWED.get(event, ())
    out = {k: _redact(props[k]) for k in keys if k in props}
    res = props.get("result")
    if isinstance(res, dict):
        out.update({f"result_{k}": res[k] for k in ("effect", "expected_effect", "ratio") if k in res})
    return out


def flush(dry_run: bool = False) -> dict:
    with gtm.locked():  # metric_add appends to the outbox; don't lose rows written mid-flush
        return _flush(dry_run)


def _flush(dry_run: bool) -> dict:
    root = gtm.R()
    box = root / "posthog-outbox.jsonl"
    rows = gtm.read_jsonl(box)
    if not rows:
        return {"sent": 0}
    if dry_run:
        return {"would_send": len(rows), "first": {"event": rows[0]["event"],
                                                   "properties": clean(rows[0]["event"], rows[0].get("properties", {}))}}
    key = env("POSTHOG_PROJECT_API_KEY")
    capture, _ = hosts()
    did = distinct_id()
    day_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()
    sent = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        batch = [{"event": r["event"], "timestamp": r.get("timestamp"), "uuid": r.get("uuid"),
                  "properties": {**clean(r["event"], r.get("properties", {})), "distinct_id": did,
                                 "$process_person_profile": False}} for r in chunk]
        body = {"api_key": key, "batch": batch}
        if all((r.get("timestamp") or "") < day_ago for r in chunk):
            body["historical_migration"] = True  # a backlog from before PostHog was connected
        http("POST", f"{capture}/batch/", body)
        sent += len(chunk)
        # keep what is left if a later chunk fails, so nothing is lost (a resend carries the same uuid)
        gtm.write_jsonl(box, rows[i + BATCH:])
    gtm.append_jsonl(root / "posthog-sent.log", {"date": dt.date.today().isoformat(), "sent": sent})
    return {"sent": sent}


# --------------------------------------------------------------------------- read
def query(hogql: str) -> list:
    pid = env("POSTHOG_PROJECT_ID")
    key = env("POSTHOG_PERSONAL_API_KEY")
    _, app = hosts()
    d = http("POST", f"{app}/api/projects/{pid}/query/", {"query": {"kind": "HogQLQuery", "query": hogql}},
             {"Authorization": f"Bearer {key}"})
    if "results" not in d:
        raise PostHogError(f"unexpected query response: {str(d)[:300]}")
    return d["results"]


def scalar(hogql: str) -> float | None:
    rows = query(hogql)
    if not rows or not rows[0] or rows[0][0] is None:
        return None
    try:
        return float(rows[0][0])
    except (TypeError, ValueError):
        raise PostHogError(f"expected a number, got {rows[0][0]!r}") from None


def lit(x: str) -> str:
    """A HogQL string literal: event names and property keys are data, never SQL."""
    return "'" + str(x).replace("\\", "\\\\").replace("'", "\\'") + "'"


def stage_query(event: str, days: int = WINDOW_DAYS) -> str:
    return (f"SELECT count(DISTINCT person_id) FROM events WHERE event = {lit(event)} "
            f"AND timestamp > now() - INTERVAL {int(days)} DAY")


def source_query(event: str, props: list[str], days: int = WINDOW_DAYS) -> str:
    """Share of people reaching the first step whose source is known (a referrer that isn't direct,
    a UTM source, or a "how did you hear" answer)."""
    cols = ", ".join(f"any(person.properties[{lit(p)}]) AS p{i}" for i, p in enumerate(props))
    known = " OR ".join(f"(p{i} IS NOT NULL AND toString(p{i}) NOT IN ('', '$direct'))" for i in range(len(props)))
    return (f"SELECT countIf({known}) / greatest(count(), 1) FROM "
            f"(SELECT person_id, {cols} FROM events WHERE event = {lit(event)} "
            f"AND timestamp > now() - INTERVAL {int(days)} DAY GROUP BY person_id)")


def plan_pull(s: dict) -> list[tuple[str, str, str]]:
    """(metric, track, hogql) for everything `pull` reads, from gtm.json `measurement`."""
    m = s.get("measurement") or {}
    stage_events = m.get("stage_events") or {}
    t = gtm.template(s)
    out = []
    for st in t["stages"]:
        ev = stage_events.get(st["id"])
        if ev:
            out.append((f"stage:{st['id']}", st["track"], stage_query(ev)))
    first_step = t["rungs"]["first_step"]
    if stage_events.get(first_step):
        props = m.get("source_properties") or ["$initial_referring_domain", "$initial_utm_source", "heard_from"]
        out.append(("source_capture_rate", "measurement", source_query(stage_events[first_step], props)))
    for metric, q in (m.get("queries") or {}).items():
        out.append((metric, (m.get("query_tracks") or {}).get(metric, ""), q))
    return out


def pull(dry_run: bool = False) -> dict:
    s = gtm.load_state()
    plan = plan_pull(s)
    if dry_run:
        return {"would_query": [{"metric": p[0], "hogql": p[2]} for p in plan], "errors": []}
    if not plan:
        raise PostHogError("nothing to pull: set measurement.stage_events in gtm.json")
    written, errors = [], []
    for metric, track, q in plan:
        try:
            v = scalar(q)
        except PostHogError as e:
            errors.append(f"{metric}: {e}")
            continue
        if v is not None:
            gtm.metric_add(metric, round(v, 6), source="posthog", track=track)
            written.append({"metric": metric, "value": round(v, 6)})
    return {"written": written, "errors": errors}


def sync() -> dict:
    out, errors = {}, []
    for name, fn in (("flush", flush), ("pull", pull)):
        try:
            out[name] = fn()
            errors += [f"{name}: {e}" for e in out[name].get("errors", [])]
        except PostHogError as e:
            out[name] = {"error": str(e)}
            errors.append(f"{name}: {e}")
    out["errors"] = errors
    return out


def tracking_check(url: str | None) -> dict:
    """Tracking is alive when PostHog received events in the last 2 days. The site's HTML is checked
    only to explain a silence (bundled posthog-js and reverse proxies don't show in the HTML)."""
    s = gtm.load_state()
    t = gtm.template(s)
    first = t["rungs"]["first_step"]
    ev = ((s.get("measurement") or {}).get("stage_events") or {}).get(first)
    events_2d = scalar("SELECT count() FROM events WHERE timestamp > now() - INTERVAL 2 DAY") or 0
    first_2d = scalar(f"SELECT count() FROM events WHERE event = {lit(ev)} AND timestamp > now() - INTERVAL 2 DAY") \
        if ev else None
    ok = events_2d > 0
    notes, snippet = [], None
    if not ok:
        url = url or s.get("site_url")
        if url:
            try:
                page = fetch_page(url)
                snippet = bool(re.search(r"posthog\.init|i\.posthog\.com|/static/array\.js|posthog-js", page))
            except Exception as e:  # noqa: BLE001 - an unreachable site is a finding, not a crash
                notes.append(f"{url} unreachable ({type(e).__name__})")
            if snippet is False:
                notes.append(f"no PostHog snippet in {url}'s HTML (fine if posthog-js is bundled or proxied)")
        notes.append("PostHog received no events in the last 2 days")
    if ev is None:
        notes.append(f"no event mapped for the first step ({first}) in measurement.stage_events")
    elif ok and not first_2d:
        notes.append(f"no '{ev}' events in 2 days; on a quiet product that can be normal (not counted as broken)")
    gtm.metric_add("tracking_ok", 1 if ok else 0, source="tracking-check", track="measurement",
                   note=f"events_2d={int(events_2d)} first_step_2d={first_2d}")
    return {"tracking_ok": ok, "events_2d": events_2d, "first_step_event": ev, "first_step_2d": first_2d,
            "snippet_in_html": snippet, "notes": notes}


def check() -> dict:
    out = {k: bool(os.environ.get(k)) for k in
           ("POSTHOG_PROJECT_API_KEY", "POSTHOG_PERSONAL_API_KEY", "POSTHOG_PROJECT_ID")}
    out["host"] = os.environ.get("POSTHOG_HOST", "us")
    out["query_ok"] = False
    if out["POSTHOG_PERSONAL_API_KEY"] and out["POSTHOG_PROJECT_ID"]:
        try:
            out["query_ok"] = scalar("SELECT 1") == 1
        except PostHogError as e:
            out["error"] = str(e)
    out["ok"] = bool(out["query_ok"] and out["POSTHOG_PROJECT_API_KEY"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p = sub.add_parser("flush")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("query")
    p.add_argument("hogql")
    p = sub.add_parser("pull")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("sync")
    p = sub.add_parser("tracking-check")
    p.add_argument("--url")
    a = ap.parse_args()
    try:
        if a.cmd == "check":
            out = check()
        elif a.cmd == "flush":
            out = flush(a.dry_run)
        elif a.cmd == "query":
            out = query(a.hogql)
        elif a.cmd == "pull":
            out = pull(a.dry_run)
        elif a.cmd == "sync":
            out = sync()
        else:
            out = tracking_check(a.url)
    except PostHogError as e:
        print(f"posthog: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    if isinstance(out, dict):
        if out.get("errors") or (a.cmd == "check" and not out["ok"]):
            return 1
        if a.cmd == "tracking-check" and not out["tracking_ok"]:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
