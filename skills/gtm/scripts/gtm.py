#!/usr/bin/env python3
"""gtm state engine: what's due, which track to work on, what we've spent and learned.

The deterministic half of the gtm skill. The agent supplies the judgment; this script makes sure
every run, on any host and any model, agrees on the facts: dates, money, fit, focus, cooldowns and
experiment results.

    python3 gtm.py where                         # the state store this repo resolves to
    python3 gtm.py init [--stage launched] [--motion self_serve] [--budget 20]
    python3 gtm.py tick                          # JSON: focus, due jobs, skipped, alerts, budget, tracks
    python3 gtm.py status                        # human summary, read-only
    python3 gtm.py focus                         # which track to work on and why
    python3 gtm.py fit                           # channel fit for this product
    python3 gtm.py tracks | ladder               # rung status per track (ladder = discoverability)
    python3 gtm.py next                          # work-session slots and ranked tactics
    python3 gtm.py budget [--need 1.50]          # exit 2 if --need would exceed the monthly cap
    python3 gtm.py record JOB [--cost 0.6 | --from-run DIR] [--key K] [--failed] [--mix focus,secondary]
    python3 gtm.py may JOB KEY                   # exit 3 if KEY is inside JOB's cooldown
    python3 gtm.py metric add NAME VALUE [--source S] [--track T] [--date D]
    python3 gtm.py metric get NAME [--days 90]
    python3 gtm.py bet open --id ID --track T --channel C --tactic X --metric M --baseline B --expected E \\
                            --method holdout --check 2026-12-10 [--control-metric M2 --control-baseline B2]
    python3 gtm.py bet close ID [--observed X] [--control-observed Y] [--p-value P] [--n N]
    python3 gtm.py bet list [--status open]
    python3 gtm.py learnings [--accept ID | --reject ID]
    python3 gtm.py profile [--motion M --acv N --cycle-days N --regulated R --attention ch=0.3] [--confirm]
    python3 gtm.py pause [--reason R] | resume   # kill switch
    python3 gtm.py digest                        # data half of digests/<date>.md
    python3 gtm.py store use SPEC                # remember a store (path, git URL or "repo") for this repo
    python3 gtm.py sync pull|push [--message M]  # git backend only
    python3 gtm.py migrate --to SPEC             # move a 0.3 .marketing/ out of the product repo

State lives in the store (see marketing_state.py), never assumed to be in the product repo.
Stdlib only; Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import shutil
import sys
from functools import lru_cache
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REFS = SCRIPTS.parent / "references"
sys.path.insert(0, str(SCRIPTS))
import marketing_state as ms  # noqa: E402

SCHEMA = 2
TRACKS = ["measurement", "discoverability", "demand", "conversion", "retention", "paid"]
STRONG_METHODS = ("ab", "holdout", "staggered")
METHODS = ("ab", "holdout", "staggered", "before_after")

# --------------------------------------------------------------------------- jobs
# Every job states its contract. gtm.py enforces cadence, dependencies, stages, cost, `requires`,
# cooldowns (`cooldown_days` per `dedupe_key`), and `stop_after_failures`. The prose fields
# (acts_when, self_check, stop) are the agent's instructions and are echoed in tick output.
DEFAULT_JOBS = {
    "access_check": {
        "every_days": 1, "usd": 0.0, "stages": ["launched"], "skill": "ai-search-optimization",
        "track": "discoverability", "kind": "sensor",
        "acts_when": "a search or user bot can no longer read a key page",
        "self_check": "re-fetch the failing URL once before alerting",
        "stop": "alert immediately; never change robots.txt or the CDN yourself"},
    "watch": {
        "every_days": 7, "usd": 0.0, "stages": ["prelaunch", "launched"], "skill": "comparison-pages",
        "track": "discoverability", "kind": "sensor",
        "acts_when": "a watched page changed or a mention appeared or disappeared",
        "self_check": "ignore changes that are only dates, prices in other currencies or cookie banners",
        "stop": "record and let comparison_refresh handle changes"},
    "audit": {
        "every_days": 7, "usd": 1.0, "stages": ["launched"], "skill": "ai-visibility-audit",
        "track": "discoverability", "kind": "sensor",
        "acts_when": "always records; acts on prompts won or lost since the last run",
        "self_check": "treat a single-sample change as noise unless it repeats across engines",
        "stop": "skip when the budget gate says no"},
    "outreach_refresh": {
        "every_days": 7, "usd": 0.5, "stages": ["launched"], "skill": "citation-outreach", "after": "audit",
        "track": "discoverability", "kind": "improvement", "max_actions": 3,
        "cooldown_days": 45, "dedupe_key": "target domain",
        "acts_when": "a cited page in a lost prompt has no draft yet and its domain is outside cooldown",
        "self_check": "the page is still live and still cited, and a human could plausibly add us",
        "stop": "drafts only; two declines from one domain removes it"},
    "work_session": {
        "every_days": 7, "usd": 1.5, "stages": ["prelaunch", "launched"], "skill": "gtm",
        "track": "focus", "kind": "improvement", "max_actions": 2,
        "acts_when": "always; uses `gtm.py next` for the slots and tactics",
        "self_check": "every action opens a bet with a metric and a check date first",
        "stop": "same fix failed twice: escalate instead of retrying"},
    "launch_scan": {
        "every_days": 1, "usd": 0.0, "stages": ["prelaunch", "launched"], "skill": "gtm",
        "track": "all", "kind": "sensor", "dedupe_key": "commit or tag",
        "acts_when": "a user-visible change merged or was tagged since the last scan",
        "self_check": "only market what users can use today; flagged-off features wait",
        "stop": "no user-visible change: record and stop"},
    "strategy_review": {
        "every_days": 30, "usd": 0.0, "stages": ["prelaunch", "launched"], "skill": "gtm",
        "track": "all", "kind": "review",
        "acts_when": "monthly",
        "self_check": "propose, don't apply, changes to budget, cadence, floors or panel",
        "stop": "never raise the budget yourself"},
    "fit_review": {
        "every_days": 90, "usd": 0.0, "stages": ["prelaunch", "launched"], "skill": "gtm",
        "track": "all", "kind": "review",
        "acts_when": "quarterly, or when the GTM profile changed",
        "self_check": "attention weights come from customer-research evidence, not guesses",
        "stop": "propose profile changes to the human"},
    "entity_probe": {
        "every_days": 90, "usd": 0.2, "stages": ["prelaunch", "launched"], "skill": "entity-presence",
        "track": "discoverability", "kind": "sensor",
        "acts_when": "an assistant misidentifies or misdescribes the product",
        "self_check": "the error repeats in at least two samples",
        "stop": "record known_issues; fixes go through work sessions"},
    "comparison_reverify": {
        "every_days": 90, "usd": 0.1, "stages": ["launched"], "skill": "comparison-pages",
        "track": "discoverability", "kind": "sensor",
        "acts_when": "a source behind a live comparison page no longer says what the page claims",
        "self_check": "read the source itself, not a cached copy",
        "stop": "open a PR correcting the page; never leave a known-wrong claim live"},
    "panel_review": {
        "every_days": 90, "usd": 0.0, "stages": ["launched"], "skill": "ai-visibility-audit",
        "track": "discoverability", "kind": "review",
        "acts_when": "quarterly",
        "self_check": "changes to the stable core break comparability; version them",
        "stop": "propose; apply after a human says yes"},
}

# Discoverability thresholds on audit metrics (mention rate per bucket group). Editable in gtm.json.
DEFAULT_LADDER = {
    "known":      {"buckets": ["brand"], "min_mention": 0.8},
    "associated": {"buckets": ["category", "problem", "jobs"], "min_mention": 0.3},
    "preferred":  {"buckets": ["comparison", "alternatives"], "min_mention": 0.5, "max_avg_rank": 2.0},
}
DISCOVERABILITY_RUNGS = ["reachable", "known", "associated", "preferred"]
DISCOVERABILITY_SKILLS = {
    "reachable": ["ai-search-optimization"],
    "known": ["entity-presence", "ai-search-optimization"],
    "associated": ["one-pager", "citation-outreach"],
    "preferred": ["comparison-pages", "citation-outreach"],
}

# Rungs per track. `value: None` means the floor is product-specific: the rung reports
# "set a floor" until gtm.json tracks.<track>.rungs.<id>.value is set.
DEFAULT_TRACK_RUNGS = {
    "measurement": [
        {"id": "instrumented", "metric": "tracking_ok", "op": ">=", "value": 1, "max_age_days": 3,
         "skills": ["measurement"], "why": "the conversion event fires in the tracking check"},
        {"id": "attributed", "metric": "source_capture_rate", "op": ">=", "value": 0.8, "max_age_days": 14,
         "skills": ["measurement"], "why": "a source is captured for most first steps, AI referrers included"},
        {"id": "funnel_visible", "kind": "funnel_visible", "skills": ["measurement"],
         "why": "every funnel stage has a recent count"},
    ],
    "demand": [
        {"id": "indexed", "metric": "indexed_ratio", "op": ">=", "value": 0.9, "max_age_days": 14,
         "skills": ["seo"], "why": "most of the sitemap is indexed"},
        {"id": "ranking", "metric": "query_top10_share", "op": ">=", "value": 0.3, "max_age_days": 14,
         "skills": ["seo", "content"], "why": "a share of the query map ranks in the top 10"},
        {"id": "visited", "kind": "funnel_count", "stage": "first", "op": ">=", "value": None,
         "skills": ["seo", "content", "social"], "why": "top-of-funnel volume reaches the floor"},
        {"id": "pipeline", "metric": "leads_28d", "op": ">=", "value": None, "max_age_days": 14,
         "skills": ["outbound", "content"], "why": "channel-attributed leads or meetings reach the floor"},
    ],
    "conversion": [
        {"id": "first_step", "kind": "funnel_rate", "stage": "first_step", "skills": ["cro"],
         "why": "visit to first step at or above the floor"},
        {"id": "activating", "kind": "funnel_rate", "stage": "activating", "skills": ["activation"],
         "why": "first step to activation at or above the floor"},
        {"id": "paying", "kind": "funnel_rate", "stage": "paying", "skills": ["activation", "experiments"],
         "why": "activation to paid at or above the floor"},
    ],
    "retention": [
        {"id": "retained", "metric": "churn_rate_monthly", "op": "<=", "value": 0.05, "max_age_days": 35,
         "skills": ["lifecycle"], "why": "monthly churn at or under the ceiling"},
        {"id": "expanding", "metric": "nrr", "op": ">=", "value": 1.0, "max_age_days": 35,
         "skills": ["lifecycle"], "why": "net revenue retention at or above 100%"},
        {"id": "referring", "metric": "referral_share", "op": ">=", "value": 0.1, "max_age_days": 35,
         "skills": ["lifecycle"], "why": "a share of new customers comes from referrals"},
    ],
    "paid": [
        {"id": "tracked", "metric": "paid_conversions_tracked", "op": ">=", "value": 1, "max_age_days": 7,
         "skills": ["paid", "measurement"], "why": "paid conversions reach the analytics tool"},
        {"id": "profitable", "metric": "cac_payback_months", "op": "<=", "value": 12, "max_age_days": 35,
         "skills": ["paid", "creative"], "why": "CAC pays back within the target"},
        {"id": "scaling", "metric": "paid_scaling_ok", "op": ">=", "value": 1, "max_age_days": 35,
         "skills": ["paid"], "why": "spend rose under caps with payback held"},
    ],
}
DEFAULT_TRACKS_ENABLED = {"measurement": True, "discoverability": True, "demand": True,
                          "conversion": True, "retention": True, "paid": False}
SHARES = {"focus": 0.60, "standing": 0.25}
FOCUS_HOLD_DAYS = 30


# --------------------------------------------------------------------------- paths and io
@lru_cache(maxsize=None)
def _root_for(cwd: str, env_state: str, env_home: str) -> Path:
    return ms.state_root(Path(cwd))


def R() -> Path:
    return _root_for(os.getcwd(), os.environ.get("MARKETING_STATE", ""), os.environ.get("MARKETING_HOME", ""))


def STATE() -> Path:
    return R() / "gtm.json"


def today() -> dt.date:
    return dt.date.today()


def _date(x: str) -> dt.date:
    return dt.date.fromisoformat(x[:10])


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def append_jsonl(p: Path, row: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row) + "\n")


def write_jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


@lru_cache(maxsize=None)
def channel_fit_ref() -> dict:
    return json.loads((REFS / "channel-fit.json").read_text())


@lru_cache(maxsize=None)
def funnel_ref() -> dict:
    return json.loads((REFS / "funnel-templates.json").read_text())


def outbox(event: str, props: dict) -> None:
    """Queue an event for PostHog. The measurement skill flushes it; without PostHog it just grows."""
    append_jsonl(R() / "posthog-outbox.jsonl",
                 {"event": event, "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(), "properties": props})


# --------------------------------------------------------------------------- state
def default_state(stage: str = "launched") -> dict:
    return {
        "schema": SCHEMA,
        "stage": stage,
        "goal": "",
        "site_url": "",
        "key_paths": ["/"],
        "repo_default_branch": "main",
        "budget_usd_month": 20.0,
        "per_run_cap_usd": 5.0,
        "notify": {"channel": "none"},
        "paused": False,
        "profile": {"motion": "self_serve", "acv_usd": None, "cycle_days": None, "regulated": "none",
                    "geo": [], "buying_committee": "1", "attention": {}, "confirmed": False},
        "connections": {"posthog": False, "search_console": False, "revenue_source": None},
        "fit": {"overrides": {}},
        "tracks": {t: {"enabled": e, "rungs": {}} for t, e in DEFAULT_TRACKS_ENABLED.items()},
        "floors": {},
        "focus": None,
        "work_mix": {"focus": 0, "standing": 0, "explore": 0},
        "accepted_problems": [],
        "known_issues": [],
        "ladder": DEFAULT_LADDER,
        "jobs": {k: dict(v) for k, v in DEFAULT_JOBS.items()},
        "last_run": {},
        "keys": {},
        "failures": {},
    }


def upgrade(s: dict) -> dict:
    """Fill in anything a 0.3 (or partial) gtm.json lacks. Never overwrites a set value."""
    d = default_state(s.get("stage", "launched"))
    for k, v in d.items():
        if k not in s:
            s[k] = v
        elif isinstance(v, dict) and isinstance(s[k], dict) and k in ("profile", "connections", "fit", "work_mix"):
            for kk, vv in v.items():
                s[k].setdefault(kk, vv)
    for t, e in DEFAULT_TRACKS_ENABLED.items():
        s["tracks"].setdefault(t, {"enabled": e, "rungs": {}})
        s["tracks"][t].setdefault("enabled", e)
        s["tracks"][t].setdefault("rungs", {})
    for name, job in DEFAULT_JOBS.items():
        cur = s["jobs"].setdefault(name, {})
        for k, v in job.items():
            cur.setdefault(k, v)
    s["schema"] = SCHEMA
    return s


def load_state() -> dict:
    if not STATE().exists():
        sys.exit(f"no gtm.json in the state store ({R()}): run `gtm.py init` (gtm init mode) first")
    return upgrade(json.loads(STATE().read_text()))


def save_state(s: dict) -> None:
    STATE().parent.mkdir(parents=True, exist_ok=True)
    STATE().write_text(json.dumps(s, indent=2) + "\n")


# --------------------------------------------------------------------------- spend
def spend_rows() -> list[dict]:
    return read_jsonl(R() / "spend.jsonl")


def month_spend(rows: list[dict], on: dt.date | None = None) -> float:
    key = (on or today()).strftime("%Y-%m")
    return round(sum(r.get("usd", 0) for r in rows if r.get("date", "").startswith(key)), 4)


def budget_info(s: dict) -> dict:
    cap = float(s.get("budget_usd_month", 20))
    spent = month_spend(spend_rows())
    return {"cap": cap, "spent_month": spent, "remaining": round(cap - spent, 4)}


# --------------------------------------------------------------------------- metrics
def _metric_file(name: str) -> Path:
    safe = name.replace("/", "_").replace(":", "__")
    return R() / "metrics" / f"{safe}.jsonl"


def metric_rows(name: str) -> list[dict]:
    return sorted(read_jsonl(_metric_file(name)), key=lambda r: r["date"])


def metric_latest(name: str, on_or_after: str | None = None) -> dict | None:
    rows = metric_rows(name)
    if on_or_after:
        rows = [r for r in rows if r["date"] >= on_or_after]
    return rows[-1] if rows else None


def metric_add(name: str, value: float, source: str = "", track: str = "", date: str | None = None,
               cost: float | None = None, note: str = "") -> dict:
    row = {"metric": name, "date": date or today().isoformat(), "value": value, "source": source,
           "track": track, "cost_usd": cost, "note": note}
    append_jsonl(_metric_file(name), row)
    outbox("marketing_metric", row)
    return row


def import_audit(run_dir: Path) -> list[dict]:
    """Write an audit's scores as metrics (ai:mention, ai:mention:<bucket>, …) so bets can close on them."""
    sc_path = run_dir / "score.json"
    if not sc_path.exists():
        return []
    sc = json.loads(sc_path.read_text())
    date = run_dir.name if run_dir.name[:4].isdigit() else today().isoformat()
    existing = {(r["metric"], r["date"]) for r in read_jsonl(_metric_file("ai:mention"))}
    if ("ai:mention", date[:10]) in existing:
        return []
    rows = []
    for key, short in (("mention_rate", "mention"), ("citation_rate", "citation"), ("share_of_voice", "share_of_voice")):
        if key in sc.get("overall", {}):
            rows.append(metric_add(f"ai:{short}", sc["overall"][key], source=f"audit {run_dir.name}",
                                   track="discoverability", date=date[:10]))
        for bucket, v in (sc.get("by_bucket") or {}).items():
            if key in v:
                rows.append(metric_add(f"ai:{short}:{bucket}", v[key], source=f"audit {run_dir.name}",
                                       track="discoverability", date=date[:10]))
    return rows


# --------------------------------------------------------------------------- discoverability (the 0.3 ladder)
def latest_run_dir() -> Path | None:
    runs_dir = R() / "runs"
    if not runs_dir.exists():
        return None
    runs = sorted(p for p in runs_dir.glob("20*") if (p / "score.json").exists())
    return runs[-1] if runs else None


def latest_access() -> dict | None:
    p = R() / "access" / "latest.json"
    return json.loads(p.read_text()) if p.exists() else None


def ladder(s: dict) -> dict:
    out: dict = {"rungs": {}, "current": None}
    acc = latest_access()
    accepted = set(s.get("accepted_problems", []))
    if acc is None:
        out["rungs"]["reachable"] = {"met": None, "why": "no access check yet"}
    else:
        blocking = [p for p in acc.get("problems", [])
                    if p not in accepted and ("(search)" in p or "(user)" in p or "noindex" in p)]
        out["rungs"]["reachable"] = {"met": not blocking, "why": blocking[:5] or "search and user bots can read the site"}

    run = latest_run_dir()
    score = json.loads((run / "score.json").read_text()) if run else None
    for rung in ("known", "associated", "preferred"):
        cfg = s["ladder"][rung]
        if not score:
            out["rungs"][rung] = {"met": None, "why": "no audit run yet"}
            continue
        rows = [score["by_bucket"][b] for b in cfg["buckets"] if b in score["by_bucket"]]
        n = sum(r["answers"] for r in rows)
        if not n:
            out["rungs"][rung] = {"met": None, "why": f"panel has no {'/'.join(cfg['buckets'])} prompts"}
            continue
        mention = sum(r["mention_rate"] * r["answers"] for r in rows) / n
        ranks = [r["avg_rank_when_named"] for r in rows if r.get("avg_rank_when_named")]
        avg_rank = sum(ranks) / len(ranks) if ranks else None
        met = mention >= cfg["min_mention"]
        if "max_avg_rank" in cfg:
            met = met and avg_rank is not None and avg_rank <= cfg["max_avg_rank"]
        if rung == "known" and s.get("known_issues"):
            met = False
        out["rungs"][rung] = {"met": met, "mention": round(mention, 3), "avg_rank": avg_rank, "answers": n,
                              "threshold": cfg, "run": run.name,
                              **({"known_issues": s["known_issues"]} if rung == "known" and s.get("known_issues") else {})}
    for r in DISCOVERABILITY_RUNGS:
        if out["rungs"][r]["met"] is not True:
            out["current"] = r
            break
    out["work_on"] = DISCOVERABILITY_SKILLS.get(out["current"], [])
    return out


# --------------------------------------------------------------------------- funnel
def template(s: dict) -> dict:
    motion = s["profile"].get("motion") or "self_serve"
    t = funnel_ref()["templates"].get(motion)
    if t is None:
        sys.exit(f"unknown motion {motion!r}; use one of {', '.join(funnel_ref()['templates'])}")
    return t


def funnel(s: dict) -> dict:
    """Counts, conversion rates and bottleneck scores per stage of the product's funnel template."""
    t = template(s)
    ref = funnel_ref()
    min_sample = int(s.get("floors", {}).get("min_sample", ref["min_sample"]))
    max_age = int(ref["max_age_days"])
    by_id: dict = {}
    stages = []
    prev_id = None
    for st in t["stages"]:
        m = metric_latest(f"stage:{st['id']}")
        age = (today() - _date(m["date"])).days if m else None
        row = {"id": st["id"], "track": st["track"], "label": st["label"],
               "count": m["value"] if m else None, "age_days": age, "fresh": m is not None and age <= max_age}
        src = st.get("from") or prev_id
        if src and "floor_rate" in st:
            floor = float(s.get("floors", {}).get(st["id"], st["floor_rate"]))
            base = by_id.get(src)
            rate = None
            enough = False
            if base and base["count"] and row["count"] is not None and base["fresh"] and row["fresh"]:
                rate = row["count"] / base["count"]
                enough = base["count"] >= min_sample
            row.update({"from": src, "rate": None if rate is None else round(rate, 4), "floor": floor,
                        "enough_data": enough, "score": round(rate / floor, 3) if enough and floor else None})
        by_id[st["id"]] = row
        stages.append(row)
        prev_id = st["id"]
    first = stages[0]
    reach_short = first["count"] is None or not first["fresh"] or first["count"] < min_sample
    return {"motion": s["profile"].get("motion"), "stages": stages, "min_sample": min_sample,
            "reach_is_bottleneck": reach_short, "north_star": t["north_star"], "rungs": t["rungs"]}


# --------------------------------------------------------------------------- tracks
def _cmp(v: float, op: str, target: float) -> bool:
    return v >= target if op == ">=" else v <= target


def rung_config(s: dict, track: str) -> list[dict]:
    over = s["tracks"].get(track, {}).get("rungs", {})
    return [{**r, **over.get(r["id"], {})} for r in DEFAULT_TRACK_RUNGS[track]]


def eval_rung(s: dict, track: str, r: dict, fun: dict) -> dict:
    kind = r.get("kind", "metric")
    base = {"id": r["id"], "skills": r.get("skills", []), "about": r.get("why", "")}
    if kind == "metric":
        if r.get("value") is None:
            return {**base, "met": None, "why": f"set a floor: gtm.json tracks.{track}.rungs.{r['id']}.value"}
        m = metric_latest(r["metric"])
        if not m:
            return {**base, "met": None, "why": f"no `{r['metric']}` metric yet"}
        age = (today() - _date(m["date"])).days
        if age > r.get("max_age_days", 30):
            return {**base, "met": None, "why": f"`{r['metric']}` is {age} days old"}
        return {**base, "met": _cmp(float(m["value"]), r["op"], float(r["value"])), "value": m["value"],
                "threshold": f"{r['op']} {r['value']}", "why": f"{r['metric']} = {m['value']} ({m['date']})"}
    if kind == "funnel_visible":
        missing = [st["id"] for st in fun["stages"] if not st["fresh"]]
        return {**base, "met": not missing, "why": "every stage has a recent count" if not missing
                else f"no recent count for: {', '.join(missing)}"}
    if kind == "funnel_count":
        st = fun["stages"][0]
        if r.get("value") is None:
            return {**base, "met": None, "why": f"set a floor: gtm.json tracks.{track}.rungs.{r['id']}.value ({st['label']} per 28 days)"}
        if st["count"] is None or not st["fresh"]:
            return {**base, "met": None, "why": f"no recent stage:{st['id']} count"}
        return {**base, "met": _cmp(float(st["count"]), r["op"], float(r["value"])), "value": st["count"],
                "threshold": f"{r['op']} {r['value']}", "why": f"{st['label']}: {st['count']}"}
    if kind == "funnel_rate":
        sid = fun["rungs"][r["stage"]]
        st = next(x for x in fun["stages"] if x["id"] == sid)
        if st.get("rate") is None:
            return {**base, "met": None, "why": f"no recent counts for {st.get('from')} → {sid}"}
        if not st["enough_data"]:
            return {**base, "met": None, "why": f"fewer than {fun['min_sample']} in {st['from']}; too few to judge"}
        return {**base, "met": st["rate"] >= st["floor"], "value": st["rate"], "threshold": f">= {st['floor']}",
                "why": f"{st['from']} → {sid}: {st['rate']:.1%} (floor {st['floor']:.1%})"}
    raise ValueError(f"unknown rung kind {kind}")


def track_status(s: dict, track: str, fun: dict | None = None) -> dict:
    enabled = s["tracks"].get(track, {}).get("enabled", True)
    if track == "discoverability":
        lad = ladder(s)
        rungs = [{"id": r, **lad["rungs"][r], "skills": DISCOVERABILITY_SKILLS[r]} for r in DISCOVERABILITY_RUNGS]
    else:
        fun = fun or funnel(s)
        rungs = [eval_rung(s, track, r, fun) for r in rung_config(s, track)]
    current = next((r for r in rungs if r["met"] is not True), None)
    met = sum(1 for r in rungs if r["met"] is True)
    return {"track": track, "enabled": enabled, "current": current["id"] if current else None,
            "work_on": current["skills"] if current else [], "progress": round(met / len(rungs), 3),
            "complete": current is None, "rungs": rungs}


def all_tracks(s: dict) -> dict:
    fun = funnel(s)
    return {t: track_status(s, t, fun) for t in TRACKS}


# --------------------------------------------------------------------------- fit
def closed_bets(**match) -> list[dict]:
    return [b for b in bets() if b.get("status") in ("won", "lost", "inconclusive")
            and all(b.get(k) == v for k, v in match.items())]


OUTCOME = {"won": 1.0, "lost": 0.0, "inconclusive": 0.5}


def fit(s: dict) -> dict:
    ref = channel_fit_ref()
    d = ref["defaults"]
    p = s["profile"]
    motion = p.get("motion") or "self_serve"
    confirmed = bool(p.get("confirmed"))
    # an unconfirmed profile contributes only its motion: no economics, cycle, regulation or attention
    acv = p.get("acv_usd") if confirmed else None
    cycle = p.get("cycle_days") if confirmed else None
    regulated = (p.get("regulated") or "none") if confirmed else "none"
    overrides = s["fit"].get("overrides", {})
    min_fit = float(s["fit"].get("min", d["min_fit"]))
    out = {}
    for ch, c in ref["channels"].items():
        matrix = float(c["matrix"].get(motion, 0))
        attention = float(p.get("attention", {}).get(ch, 1.0)) if confirmed else 1.0
        cost_floor = float(c["cost_floor_usd"])
        measured_cost = [b["cost_per_customer"] for b in closed_bets(channel=ch) if b.get("cost_per_customer")]
        if measured_cost:
            cost_floor = sorted(measured_cost)[len(measured_cost) // 2]
        if cost_floor <= 0:
            economics, econ_note = 1.0, "organic"
        elif acv is None:
            economics, econ_note = 1.0, "deal size unknown" if confirmed else "profile unconfirmed"
        else:
            economics = min(1.0, acv * d["gross_margin"] * d["payback_target_months"] / 12 / cost_floor)
            econ_note = f"${cost_floor:,.0f} per customer vs ${acv:,.0f} ACV"
        cycle_factor = 1.0
        if c.get("fast_feedback") and cycle and cycle > d["slow_cycle_days"]:
            cycle_factor = max(0.4, d["slow_cycle_days"] / cycle)
        compliance = float(ref["compliance"].get(regulated, {}).get(ch, 1.0))
        prior = matrix * attention * economics * cycle_factor * compliance
        outcomes = [OUTCOME[b["status"]] for b in closed_bets(channel=ch)]
        w = d["prior_weight_bets"]
        posterior = (w * prior + sum(outcomes)) / (w + len(outcomes)) if outcomes else prior
        ov = overrides.get(ch)
        value = posterior
        if isinstance(ov, (int, float)):
            value = float(ov)
        eligible = (value >= min_fit and ov != "exclude") or ov == "include"
        reason = []
        if matrix * attention < min_fit:
            reason.append("buyers aren't there" if attention < 1 else f"low fit for {motion}")
        if economics < 0.5:
            reason.append(f"economics {economics:.2f}: {econ_note}")
        if cycle_factor < 1:
            reason.append(f"{cycle}-day cycle slows feedback")
        if compliance < 1:
            reason.append(f"{regulated} regulation")
        if ov is not None:
            reason.append(f"override: {ov}")
        out[ch] = {"label": c["label"], "tracks": c["tracks"], "matrix": matrix, "attention": attention,
                   "economics": round(economics, 3), "cycle": round(cycle_factor, 3), "compliance": compliance,
                   "prior": round(prior, 3), "bets": len(outcomes), "fit": round(value, 3),
                   "eligible": bool(eligible), "why": "; ".join(reason)}
    return out


def track_eligible(track: str, fits: dict) -> bool:
    if track in ("measurement", "conversion"):
        return True
    return sum(f["fit"] for f in fits.values() if f["eligible"] and track in f["tracks"]) >= 0.5


# --------------------------------------------------------------------------- focus
def _reach_track(tracks: dict, fits: dict) -> str:
    options = [t for t in ("discoverability", "demand")
               if tracks[t]["enabled"] and not tracks[t]["complete"] and track_eligible(t, fits)]
    if not options:
        return "discoverability"
    return min(options, key=lambda t: (tracks[t]["progress"], t != "discoverability"))


def compute_focus(s: dict) -> dict:
    fits = fit(s)
    fun = funnel(s)
    tracks = {t: track_status(s, t, fun) for t in TRACKS}
    stage = s.get("stage", "launched")
    alerts = []
    disc = tracks["discoverability"]
    for r in disc["rungs"]:
        if r["id"] == "reachable" and stage == "prelaunch":
            continue
        if r["id"] in ("reachable", "known") and r["met"] is False:
            why = r.get("why")
            why = why if isinstance(why, str) else ("; ".join(why) if why else
                                                     f"mention {r.get('mention')} below {r.get('threshold')}")
            alerts.append(f"DISCOVERABILITY {r['id']}: {why}")

    scored = sorted((st for st in fun["stages"] if st.get("score") is not None), key=lambda x: x["score"])
    worst = scored[0] if scored else None
    severe = [st for st in scored if st["score"] < 0.5]

    if s.get("paused"):
        return {"track": None, "reason": "paused", "alerts": alerts, "tracks": tracks, "fits": fits, "funnel": fun}
    if stage == "prelaunch":
        cand, reason = "discoverability", "prelaunch: be findable and described correctly on launch day"
    elif not tracks["measurement"]["complete"]:
        cand = "measurement"
        reason = f"measurement gates the funnel: `{tracks['measurement']['current']}` not met"
    elif fun["reach_is_bottleneck"]:
        cand = _reach_track(tracks, fits)
        first = fun["stages"][0]
        reason = (f"too few {first['label']} to judge conversion ({first['count'] or 0} < {fun['min_sample']}); "
                  f"reach is the bottleneck")
    else:
        cand, reason = None, ""
        for st in scored:
            t = st["track"] if st["track"] != "demand" else _reach_track(tracks, fits)
            if tracks[t]["enabled"] and track_eligible(t, fits):
                cand = t
                reason = f"{st['from']} → {st['id']} is {st['rate']:.1%} against a {st['floor']:.1%} floor"
                break
        if cand is None:
            cand = _reach_track(tracks, fits)
            reason = "no stage has enough data; working on reach"

    prev = s.get("focus") or {}
    since = today().isoformat()
    if prev.get("track") == cand:
        since = prev.get("since", since)
    elif prev.get("track") and cand != "measurement" and stage != "prelaunch" and prev.get("stage") == stage:
        pt = tracks.get(prev["track"])
        age = (today() - _date(prev["since"])).days if prev.get("since") else FOCUS_HOLD_DAYS
        valid = pt and pt["enabled"] and not pt["complete"] and track_eligible(prev["track"], fits)
        cand_severe = any(st for st in severe if st["track"] == cand)
        if valid and age < FOCUS_HOLD_DAYS and not cand_severe:
            cand, since = prev["track"], prev["since"]
            reason = f"holding focus since {since} (re-decided after {FOCUS_HOLD_DAYS} days or a severe drop); " + prev.get("reason", "")

    standing = (cand != "discoverability" and tracks["discoverability"]["enabled"]
                and not tracks["discoverability"]["complete"] and fits["ai_search"]["eligible"])
    if standing:
        secondary = "discoverability"
    else:
        rest = [st for st in scored if st["track"] not in (cand,) and tracks.get(st["track"], {}).get("enabled")]
        secondary = rest[0]["track"] if rest else ("measurement" if stage == "prelaunch" and cand != "measurement" else None)
        if secondary == "demand":
            secondary = _reach_track(tracks, fits)
        if secondary == cand:
            secondary = None
    shares = {"focus": SHARES["focus"]}
    if secondary:
        shares["secondary"] = SHARES["standing"]
    shares["explore"] = round(1 - sum(shares.values()), 2)

    not_pursuing = [f"{f['label']} ({f['fit']:.2f}: {f['why'] or 'below the fit floor'})"
                    for f in fits.values() if not f["eligible"]]
    tr = tracks[cand]
    return {"track": cand, "rung": tr["current"], "skills": tr["work_on"], "reason": reason, "since": since,
            "stage": stage, "secondary": secondary, "standing_discoverability": standing, "shares": shares,
            "not_pursuing": not_pursuing, "alerts": alerts, "tracks": tracks, "fits": fits, "funnel": fun,
            "worst_stage": worst["id"] if worst else None}


def persist_focus(s: dict, f: dict) -> None:
    if f.get("track"):
        s["focus"] = {"track": f["track"], "since": f["since"], "reason": f["reason"], "stage": f["stage"],
                      "secondary": f["secondary"]}


def focus_line(f: dict) -> str:
    if not f.get("track"):
        return "Focus: none (paused)"
    sec = f" Secondary: {f['secondary']}" + (" (standing priority)." if f["standing_discoverability"] else ".") \
        if f.get("secondary") else ""
    return f"Focus: {f['track']} (rung `{f['rung']}`) — {f['reason']}.{sec}"


# --------------------------------------------------------------------------- work slots and tactics
def next_slots(s: dict, f: dict, n: int) -> list[str]:
    """Pick slot categories so the long-run mix follows the shares (largest deficit first)."""
    mix = dict(s.get("work_mix") or {})
    shares = {"focus": f["shares"]["focus"], "standing": f["shares"].get("secondary", 0), "explore": f["shares"]["explore"]}
    slots = []
    for _ in range(n):
        total = sum(mix.get(k, 0) for k in shares) + 1
        pick = max(shares, key=lambda k: (shares[k] * total - mix.get(k, 0), k == "focus"))
        if shares[pick] <= 0:
            pick = "focus"
        mix[pick] = mix.get(pick, 0) + 1
        slots.append(pick)
    return slots


def tactics_for(track: str, fits: dict, seed: str, rung_skills: list[str] | None = None) -> list[dict]:
    """Rank a track's tactics by Thompson sampling: prior = channel fit, updated by this product's bets.
    Tactics that work the track's current rung come first."""
    ref = channel_fit_ref()
    rng = random.Random(seed)
    w = ref["defaults"]["prior_weight_bets"]
    rung_skills = rung_skills or []
    out = []
    for ch, c in ref["channels"].items():
        if not fits[ch]["eligible"]:
            continue
        for tid, t in c["tactics"].items():
            if track not in t.get("tracks", c["tracks"]):
                continue
            prior = fits[ch]["fit"]
            a, b = 1 + w * prior, 1 + w * (1 - prior)
            history = closed_bets(tactic=tid)
            for bt in history:
                o = OUTCOME[bt["status"]]
                a += o
                b += 1 - o
            out.append({"tactic": tid, "channel": ch, "skill": t["skill"], "label": t["label"],
                        "on_rung": t["skill"] in rung_skills,
                        "sample": round(rng.betavariate(a, b), 3), "mean": round(a / (a + b), 3),
                        "closed_bets": len(history)})
    return sorted(out, key=lambda x: (not x["on_rung"], -x["sample"]))


def plan_next(s: dict) -> dict:
    f = compute_focus(s)
    if not f.get("track"):
        return {"paused": True}
    n = int(s["jobs"]["work_session"].get("max_actions", 2))
    slots = next_slots(s, f, n)
    seed = today().isoformat()
    explore_tracks = [t for t in TRACKS if t not in (f["track"], f["secondary"])
                      and f["tracks"][t]["enabled"] and track_eligible(t, f["fits"])]
    out = []
    for i, cat in enumerate(slots):
        if cat == "focus":
            track = f["track"]
        elif cat == "standing":
            track = f["secondary"]
        else:
            track = explore_tracks[(today().toordinal() + i) % len(explore_tracks)] if explore_tracks else f["track"]
        out.append({"slot": cat, "track": track, "rung": f["tracks"][track]["current"],
                    "tactics": tactics_for(track, f["fits"], f"{seed}-{i}-{track}", f["tracks"][track]["work_on"])[:5]})
    return {"focus": focus_line(f), "slots": out,
            "record_with": f"gtm.py record work_session --mix {','.join(slots)}"}


# --------------------------------------------------------------------------- bets
def bets() -> list[dict]:
    return read_jsonl(R() / "experiments.jsonl")


def save_bets(rows: list[dict]) -> None:
    write_jsonl(R() / "experiments.jsonl", rows)


def bet_open(a) -> int:
    rows = bets()
    if any(b["id"] == a.id for b in rows):
        print(f"bet {a.id} already exists", file=sys.stderr)
        return 1
    if a.method in ("holdout", "staggered") and not a.control_metric:
        print(f"--method {a.method} needs --control-metric (the untouched half)", file=sys.stderr)
        return 1
    if a.expected == a.baseline:
        print("--expected must differ from --baseline: say what you expect to move", file=sys.stderr)
        return 1
    try:
        check = _date(a.check)
    except ValueError:
        print("--check must be a date (YYYY-MM-DD)", file=sys.stderr)
        return 1
    if check <= today():
        print("--check must be in the future", file=sys.stderr)
        return 1
    b = {"id": a.id, "track": a.track, "channel": a.channel, "tactic": a.tactic, "hypothesis": a.hypothesis,
         "metric": a.metric, "baseline": a.baseline, "expected": a.expected, "method": a.method,
         "control_metric": a.control_metric, "control_baseline": a.control_baseline,
         "opened": today().isoformat(), "check": check.isoformat(), "cost_usd": a.cost_usd, "effort": a.effort,
         "status": "open", "result": None, "decision": None, "learning": None}
    rows.append(b)
    save_bets(rows)
    outbox("marketing_bet", {**b, "change": "opened"})
    print(json.dumps(b, indent=2))
    return 0


def judge(b: dict, observed: float, control_observed: float | None, p_value: float | None, n: int | None,
          min_n: int) -> dict:
    expected_effect = b["expected"] - b["baseline"]
    effect = observed - b["baseline"]
    if b.get("control_metric") and control_observed is not None and b.get("control_baseline") is not None:
        effect -= control_observed - b["control_baseline"]
    ratio = effect / expected_effect if expected_effect else 0.0
    note = ""
    if b["method"] == "ab":
        if p_value is None:
            raise ValueError("an A/B bet needs --p-value from the experiments skill's stats")
        if p_value >= 0.05:
            status, note = "inconclusive", f"p = {p_value:.3f}"
        else:
            status = "won" if ratio > 0 else "lost"
            note = f"p = {p_value:.3f}"
    elif n is not None and n < min_n:
        status, note = "inconclusive", f"n = {n} < {min_n}: underpowered"
    elif ratio >= 0.5:
        status = "won"
    elif ratio <= -0.5:
        status = "lost"
    else:
        status = "inconclusive"
    if b["method"] == "before_after":
        note = (note + "; " if note else "") + "directional: no control"
    return {"status": status, "effect": round(effect, 4), "expected_effect": round(expected_effect, 4),
            "ratio": round(ratio, 3), "note": note}


def bet_close(a) -> int:
    rows = bets()
    b = next((x for x in rows if x["id"] == a.id), None)
    if not b:
        print(f"no bet {a.id}", file=sys.stderr)
        return 1
    if b["status"] != "open":
        print(f"bet {a.id} is already {b['status']}", file=sys.stderr)
        return 1
    if _date(b["check"]) > today() and not a.force:
        print(f"bet {a.id} checks on {b['check']}; pass --force to close early", file=sys.stderr)
        return 1
    observed = a.observed
    if observed is None:
        m = metric_latest(b["metric"], on_or_after=b["check"]) or metric_latest(b["metric"], on_or_after=b["opened"])
        if not m:
            print(f"no `{b['metric']}` value since {b['opened']}; pass --observed or record the metric", file=sys.stderr)
            return 1
        observed = float(m["value"])
    ctrl = a.control_observed
    if ctrl is None and b.get("control_metric"):
        m = metric_latest(b["control_metric"], on_or_after=b["opened"])
        ctrl = float(m["value"]) if m else None
        if ctrl is None:
            print(f"no `{b['control_metric']}` value; pass --control-observed", file=sys.stderr)
            return 1
    try:
        res = judge(b, observed, ctrl, a.p_value, a.n, a.min_n)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    b.update({"status": res["status"], "result": {**res, "observed": observed, "control_observed": ctrl},
              "closed": today().isoformat(), "decision": a.decision or None})
    if a.cost_per_customer:
        b["cost_per_customer"] = a.cost_per_customer
    save_bets(rows)
    outbox("marketing_bet", {**b, "change": "closed"})
    print(json.dumps(b, indent=2))
    return 0


def learning_candidates() -> list[dict]:
    """Closed bets strong enough to become a learning: a strong method, or two bets on one tactic agreeing."""
    closed = [b for b in bets() if b["status"] in ("won", "lost") and not b.get("learning")]
    out = []
    for b in closed:
        same = [x for x in bets() if x["tactic"] == b["tactic"] and x["status"] == b["status"] and x["id"] != b["id"]]
        if b["method"] in STRONG_METHODS or same:
            out.append({"id": b["id"], "tactic": b["tactic"], "channel": b["channel"], "status": b["status"],
                        "evidence": b["method"] if b["method"] in STRONG_METHODS else f"agrees with {same[0]['id']}",
                        "hypothesis": b["hypothesis"], "result": b["result"]})
    return out


# --------------------------------------------------------------------------- due
def requirement_unmet(s: dict, req: str, fits: dict | None) -> str | None:
    kind, _, name = req.partition(":")
    if kind == "connection" and not s["connections"].get(name):
        return f"connect {name} first"
    if kind == "channel" and fits is not None and not fits.get(name, {}).get("eligible"):
        return f"channel {name} isn't a fit for this product"
    if kind == "track" and not s["tracks"].get(name, {}).get("enabled"):
        return f"track {name} is off"
    if kind == "profile" and not s["profile"].get("confirmed"):
        return "the GTM profile isn't confirmed yet"
    return None


def due(s: dict, fits: dict | None = None) -> tuple[list[dict], list[dict], list[str]]:
    stage = s.get("stage", "launched")
    jobs, skipped, alerts = [], [], []
    t = today()
    for name, j in s["jobs"].items():
        if j.get("enabled", True) is False or stage not in j.get("stages", ["launched"]):
            continue
        track = j.get("track")
        if track in TRACKS and not s["tracks"].get(track, {}).get("enabled", True):
            continue
        last = s["last_run"].get(name)
        age = (t - _date(last)).days if last else None
        why = None
        if age is None:
            why = "never run"
        elif age >= j["every_days"]:
            why = f"last run {age}d ago (every {j['every_days']}d)"
        dep = j.get("after")
        if dep and why:
            dep_last = s["last_run"].get(dep)
            if not dep_last or (last and dep_last <= last):
                why = None
        if not why:
            continue
        unmet = [u for u in (requirement_unmet(s, r, fits) for r in j.get("requires", [])) if u]
        entry = {"job": name, "why": why, "skill": j["skill"], "usd": j["usd"], "track": track,
                 "kind": j.get("kind")}
        for k in ("max_actions", "cooldown_days", "dedupe_key", "acts_when", "self_check", "stop"):
            if j.get(k) is not None:
                entry[k] = j[k]
        if unmet:
            skipped.append({**entry, "skipped": "; ".join(unmet)})
        else:
            jobs.append(entry)

    root = R()
    wr = root / "watch" / "report.md"
    if wr.exists():
        txt = wr.read_text()
        seen = s["last_run"].get("comparison_refresh")
        stamp = txt.splitlines()[0].rsplit("— ", 1)[-1] if txt else ""
        if "## Changed:" in txt and stamp and stamp != seen:
            jobs.append({"job": "comparison_refresh", "why": f"watched pages changed ({stamp})",
                         "skill": "comparison-pages", "usd": 0.05, "event": stamp, "track": "discoverability",
                         "kind": "improvement"})
    for b in bets():
        if b["status"] == "open" and _date(b["check"]) <= t:
            jobs.append({"job": "bet_close", "why": f"bet {b['id']} reached its check date {b['check']}",
                         "skill": "gtm", "usd": 0.0, "event": b["id"], "track": b["track"], "kind": "review",
                         "command": f"gtm.py bet close {b['id']}"})
    acc = latest_access()
    prev = root / "access" / "previous.json"
    if acc and prev.exists():
        before = set(json.loads(prev.read_text()).get("problems", []))
        new = [p for p in acc.get("problems", []) if p not in before and p not in s["accepted_problems"]]
        if new:
            alerts.append("ACCESS REGRESSION: " + "; ".join(new[:5]))
    run = latest_run_dir()
    if run:
        sc = json.loads((run / "score.json").read_text())
        lost = (sc.get("diff") or {}).get("lost", [])
        if len(lost) >= 3:
            alerts.append(f"{len(lost)} prompts lost since the previous audit: {', '.join(lost[:6])}")
    for job, keys in (s.get("failures") or {}).items():
        stop_after = int(s["jobs"].get(job, {}).get("stop_after_failures", 2))
        for key, n in keys.items():
            if n >= stop_after:
                alerts.append(f"ESCALATE: {job} failed {n} times on {key}; a human needs to look before it runs again")
    return jobs, skipped, alerts


# --------------------------------------------------------------------------- commands
def cmd_where(a) -> int:
    st = ms.resolve()
    print(json.dumps({**st.as_dict(), "initialized": (st.root / "gtm.json").exists()}, indent=2))
    return 0


def cmd_init(a) -> int:
    exists = STATE().exists()
    if exists and not a.force:
        s = load_state()
        changed = False
        for k, v in (("motion", a.motion), ("acv_usd", a.acv)):
            if v is not None and s["profile"].get(k) != v:
                s["profile"][k] = v
                changed = True
        save_state(s)
        print(f"upgraded {STATE()} to schema {SCHEMA}; settings kept" + (" (profile updated)" if changed else ""))
        return 0
    old = json.loads(STATE().read_text()) if exists else {}
    s = default_state(a.stage)
    for k in ("goal", "site_url", "key_paths", "repo_default_branch", "notify", "accepted_problems",
              "known_issues", "ladder", "last_run", "keys", "profile", "connections", "fit", "tracks", "floors"):
        if k in old:
            s[k] = old[k]
    s.update({"stage": a.stage, "budget_usd_month": a.budget, "per_run_cap_usd": a.per_run_cap})
    if a.site_url:
        s["site_url"] = a.site_url
    if a.motion:
        s["profile"]["motion"] = a.motion
    if a.acv is not None:
        s["profile"]["acv_usd"] = a.acv
    if not s["last_run"]:
        # reviews start their clock at init; launch_scan scans only changes after init
        s["last_run"] = {k: today().isoformat() for k in
                         ("launch_scan", "strategy_review", "panel_review", "comparison_reverify", "fit_review")}
    upgrade(s)
    save_state(s)
    print(f"wrote {STATE()} (stage={a.stage}, motion={s['profile']['motion']}, budget=${a.budget}/month)")
    return 0


def cmd_tick(a) -> int:
    s = load_state()
    if s.get("paused"):
        print(json.dumps({"date": today().isoformat(), "paused": True, "due": [], "deferred": [],
                          "alerts": [f"PAUSED: {s.get('paused_reason') or 'kill switch on'}; run `gtm.py resume`"]}, indent=2))
        return 0
    f = compute_focus(s)
    jobs, skipped, alerts = due(s, f["fits"])
    b = budget_info(s)
    affordable, deferred = [], []
    left = min(b["remaining"], float(s.get("per_run_cap_usd", 5)))
    for j in sorted(jobs, key=lambda j: (j["usd"] > 0, j["usd"])):
        if j["usd"] <= left:
            affordable.append(j)
            left -= j["usd"]
        else:
            deferred.append({**j, "deferred": "budget"})
    persist_focus(s, f)
    save_state(s)
    out = {"date": today().isoformat(), "stage": s.get("stage"), "store": str(R()),
           "focus": {k: f[k] for k in ("track", "rung", "skills", "reason", "since", "secondary", "shares",
                                        "standing_discoverability")},
           "due": affordable, "deferred": deferred, "skipped": skipped, "alerts": f["alerts"] + alerts,
           "budget": b, "tracks": {t: {k: v[k] for k in ("enabled", "current", "progress")} for t, v in f["tracks"].items()},
           "ladder": ladder(s)}
    print(json.dumps(out, indent=2))
    return 0


def cmd_focus(a) -> int:
    s = load_state()
    f = compute_focus(s)
    print(json.dumps({k: v for k, v in f.items() if k not in ("tracks", "fits", "funnel")}, indent=2))
    return 0


def cmd_fit(a) -> int:
    s = load_state()
    fits = fit(s)
    note = None if s["profile"].get("confirmed") else \
        "profile unconfirmed: using the motion's defaults only; confirm with `gtm.py profile --confirm`"
    print(json.dumps({"motion": s["profile"]["motion"], "acv_usd": s["profile"].get("acv_usd"),
                      "profile_confirmed": s["profile"].get("confirmed"), "note": note, "channels": fits}, indent=2))
    return 0


def cmd_tracks(a) -> int:
    s = load_state()
    print(json.dumps({"funnel": funnel(s), "tracks": all_tracks(s)}, indent=2))
    return 0


def cmd_ladder(a) -> int:
    print(json.dumps(ladder(load_state()), indent=2))
    return 0


def cmd_next(a) -> int:
    print(json.dumps(plan_next(load_state()), indent=2))
    return 0


def cmd_budget(a) -> int:
    b = budget_info(load_state())
    print(json.dumps(b))
    if a.need is not None and a.need > b["remaining"]:
        print(f"need ${a.need:.2f} > remaining ${b['remaining']:.2f}", file=sys.stderr)
        return 2
    return 0


def in_cooldown(s: dict, job: str, key: str) -> str | None:
    days = s["jobs"].get(job, {}).get("cooldown_days")
    last = (s.get("keys") or {}).get(job, {}).get(key)
    if days and last and (today() - _date(last)).days < days:
        return f"{key} was handled on {last}; {job} cools down for {days} days"
    return None


def cmd_may(a) -> int:
    s = load_state()
    if s.get("paused"):
        print("paused")
        return 3
    why = in_cooldown(s, a.job, a.key)
    print(why or "ok")
    return 3 if why else 0


def cmd_record(a) -> int:
    s = load_state()
    if a.key and not a.failed:
        why = in_cooldown(s, a.job, a.key)
        if why and not a.force:
            print(f"refused: {why}", file=sys.stderr)
            return 3
    if a.failed:
        if not a.key:
            print("--failed needs --key", file=sys.stderr)
            return 1
        fails = s.setdefault("failures", {}).setdefault(a.job, {})
        fails[a.key] = fails.get(a.key, 0) + 1
        save_state(s)
        print(f"recorded failure {fails[a.key]} for {a.job} on {a.key}")
        return 0
    cost = a.cost or 0.0
    imported = []
    if a.from_run:
        rows = read_jsonl(Path(a.from_run) / "answers.jsonl")
        cost = round(sum(r.get("cost_usd") or 0 for r in rows), 4)
        imported = import_audit(Path(a.from_run))
    s["last_run"][a.job] = a.event or today().isoformat()
    if a.key:
        s.setdefault("keys", {}).setdefault(a.job, {})[a.key] = today().isoformat()
        s.get("failures", {}).get(a.job, {}).pop(a.key, None)
    if a.mix:
        for cat in a.mix.split(","):
            if cat not in ("focus", "standing", "explore"):
                print(f"--mix takes focus, standing or explore, not {cat!r}", file=sys.stderr)
                return 1
            s["work_mix"][cat] = s["work_mix"].get(cat, 0) + 1
    save_state(s)
    if cost or a.note:
        append_jsonl(R() / "spend.jsonl", {"date": today().isoformat(), "job": a.job, "usd": cost, "note": a.note})
    print(f"recorded {a.job} on {s['last_run'][a.job]}" + (f", ${cost:.4f}" if cost else "")
          + (f", {len(imported)} audit metrics" if imported else ""))
    return 0


def cmd_metric(a) -> int:
    if a.action == "add":
        if a.value is None:
            print("metric add needs NAME VALUE", file=sys.stderr)
            return 1
        print(json.dumps(metric_add(a.name, a.value, a.source, a.track, a.date, a.cost, a.note)))
        return 0
    since = (today() - dt.timedelta(days=a.days)).isoformat()
    print(json.dumps([r for r in metric_rows(a.name) if r["date"] >= since], indent=2))
    return 0


def cmd_bet(a) -> int:
    if a.action == "open":
        missing = [k for k in ("id", "track", "channel", "tactic", "metric", "check") if not getattr(a, k)]
        if missing or a.baseline is None or a.expected is None:
            print("bet open needs --id --track --channel --tactic --metric --baseline --expected --check", file=sys.stderr)
            return 1
        return bet_open(a)
    if a.action == "close":
        if not a.id:
            print("bet close needs an id", file=sys.stderr)
            return 1
        return bet_close(a)
    rows = [b for b in bets() if not a.status or b["status"] == a.status]
    print(json.dumps(rows, indent=2))
    return 0


def cmd_learnings(a) -> int:
    if a.accept or a.reject:
        rows = bets()
        target = a.accept or a.reject
        b = next((x for x in rows if x["id"] == target), None)
        if not b:
            print(f"no bet {target}", file=sys.stderr)
            return 1
        b["learning"] = "accepted" if a.accept else "rejected"
        save_bets(rows)
        print(f"{target}: learning {b['learning']}")
        return 0
    print(json.dumps(learning_candidates(), indent=2))
    return 0


def cmd_profile(a) -> int:
    """Show or change the GTM profile. Any change unconfirms it until a human confirms again."""
    s = load_state()
    prof = s["profile"]
    changed = False
    for key, val in (("motion", a.motion), ("acv_usd", a.acv), ("cycle_days", a.cycle_days),
                     ("regulated", a.regulated), ("buying_committee", a.buying_committee)):
        if val is not None and prof.get(key) != val:
            prof[key] = val
            changed = True
    if a.geo is not None:
        prof["geo"] = [g.strip() for g in a.geo.split(",") if g.strip()]
        changed = True
    for item in a.attention or []:
        ch, _, v = item.partition("=")
        if ch not in channel_fit_ref()["channels"]:
            print(f"unknown channel {ch!r}; one of {', '.join(channel_fit_ref()['channels'])}", file=sys.stderr)
            return 1
        try:
            w = float(v)
        except ValueError:
            print(f"--attention takes CHANNEL=0..1, not {item!r}", file=sys.stderr)
            return 1
        if not 0 <= w <= 1:
            print("attention weights are between 0 and 1", file=sys.stderr)
            return 1
        prof.setdefault("attention", {})[ch] = w
        changed = True
    if changed:
        prof["confirmed"] = False
    if a.confirm:
        prof["confirmed"] = True
    save_state(s)
    print(json.dumps(prof, indent=2))
    return 0


def cmd_pause(a) -> int:
    s = load_state()
    s["paused"] = True
    s["paused_reason"] = a.reason
    save_state(s)
    print("paused: tick runs nothing until `gtm.py resume`")
    return 0


def cmd_resume(a) -> int:
    s = load_state()
    s["paused"] = False
    s.pop("paused_reason", None)
    save_state(s)
    print("resumed")
    return 0


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def cmd_status(a) -> int:
    s = load_state()
    b = budget_info(s)
    print(f"store: {R()}")
    print(f"stage: {s.get('stage')}   motion: {s['profile'].get('motion')}   goal: {s.get('goal') or '(unset)'}")
    print(f"budget: ${b['spent_month']:.2f} of ${b['cap']:.2f} this month")
    if s.get("paused"):
        print(f"PAUSED: {s.get('paused_reason') or 'kill switch on'}")
        return 0
    f = compute_focus(s)
    jobs, skipped, alerts = due(s, f["fits"])
    print(focus_line(f))
    for t in TRACKS:
        x = f["tracks"][t]
        state = "off" if not x["enabled"] else ("done" if x["complete"] else f"on `{x['current']}`")
        print(f"  {t:15} {state:28} {x['progress'] * 100:.0f}% of rungs met")
    print("due:", ", ".join(f"{j['job']} ({j['why']})" for j in jobs) or "nothing")
    for j in skipped:
        print(f"skipped: {j['job']} ({j['skipped']})")
    for al in f["alerts"] + alerts:
        print("ALERT:", al)
    opened = [x for x in bets() if x["status"] == "open"]
    if opened:
        print(f"open bets: {', '.join(x['id'] + ' → ' + x['check'] for x in opened)}")
    return 0


def cmd_digest(a) -> int:
    s = load_state()
    root = R()
    b = budget_info(s)
    f = compute_focus(s)
    jobs, skipped, alerts = due(s, f["fits"])
    run = latest_run_dir()
    L = [f"# GTM digest — {today().isoformat()}", "",
         "<!-- the agent fills: Needs you / Shipped / Moved / Broken / Next. Everything below the line is generated. -->",
         "", "## Needs you", "", "_(agent: at most 3 asks — approvals, PRs to review, facts only the owner has)_", "",
         "## Shipped", "", "## Moved", "", "## Broken", "", "## Next", "", "---", "",
         f"**{focus_line(f)}**", "",
         f"**Stage** {s.get('stage')} · **motion** {s['profile'].get('motion')} · "
         f"**spend** ${b['spent_month']:.2f} / ${b['cap']:.0f} this month", ""]
    for al in f["alerts"] + alerts:
        L.append(f"> ⚠ {al}")
    L += ["", "| track | status |", "|---|---|"]
    for t in TRACKS:
        x = f["tracks"][t]
        L.append(f"| {t} | {'off' if not x['enabled'] else ('done' if x['complete'] else x['current'])} |")
    L.append("")
    if run:
        sc = json.loads((run / "score.json").read_text())
        o = sc["overall"]
        L.append(f"**Audit {run.name}**: named {_pct(o['mention_rate'])}, cited {_pct(o['citation_rate'])}, "
                 f"share of voice {_pct(o['share_of_voice'])}.")
        d = sc.get("diff")
        if d:
            L.append(f"Since {sc.get('diff_vs')}: mention {d['overall']['mention_rate']:+.1%}, "
                     f"won {len(d['won'])}, lost {len(d['lost'])}.")
    opened = [x for x in bets() if x["status"] == "open"]
    closed_recent = [x for x in bets() if x.get("closed") and (today() - _date(x["closed"])).days <= 7]
    if opened:
        L.append("**Open bets**: " + "; ".join(f"{x['id']} ({x['tactic']}, checks {x['check']})" for x in opened))
    for x in closed_recent:
        r = x["result"] or {}
        L.append(f"**Closed** {x['id']}: {x['status']} — effect {r.get('effect')} vs expected {r.get('expected_effect')}"
                 + (f" ({r['note']})" if r.get("note") else ""))
    cands = learning_candidates()
    if cands:
        L.append("**Proposed learnings** (accept with `gtm.py learnings --accept ID`): "
                 + "; ".join(f"{c['id']} {c['tactic']} {c['status']} ({c['evidence']})" for c in cands))
    month = today().strftime("%Y-%m")
    if s.get("last_fit_report") != month and f["not_pursuing"]:
        L.append("**Not pursuing this month** (override in gtm.json fit.overrides): " + "; ".join(f["not_pursuing"]))
        s["last_fit_report"] = month
        save_state(s)
    tp = root / "outreach" / "targets.json"
    if tp.exists():
        counts: dict = {}
        for x in json.loads(tp.read_text()):
            counts[x.get("status", "new")] = counts.get(x.get("status", "new"), 0) + 1
        L.append("**Outreach**: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    L += ["", "**Due next tick**: " + (", ".join(j["job"] for j in jobs) or "nothing")]
    if skipped:
        L.append("**Skipped**: " + "; ".join(f"{j['job']} ({j['skipped']})" for j in skipped))
    out = root / "digests" / f"{today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not a.force:
        print(f"{out} exists (agent may have filled it); pass --force to regenerate")
        return 1
    out.write_text("\n".join(L) + "\n")
    print(out)
    return 0


def cmd_store(a) -> int:
    root = ms.repo_root()
    slug = ms.repo_slug(root)
    ms.register(slug, a.spec)
    _root_for.cache_clear()
    print(json.dumps(ms.resolve().as_dict(), indent=2))
    return 0


def cmd_sync(a) -> int:
    st = ms.resolve()
    try:
        msg = ms.pull(st) if a.direction == "pull" else ms.push(st, a.message or f"marketing: {today().isoformat()}")
    except RuntimeError as e:
        print(f"sync failed: {e}", file=sys.stderr)
        return 1
    print(msg)
    return 0


def cmd_migrate(a) -> int:
    root = ms.repo_root()
    src = root / ms.LEGACY_DIR
    if not (src / "gtm.json").exists():
        print(f"nothing to migrate: {src}/gtm.json not found", file=sys.stderr)
        return 1
    if a.to == "repo":
        print("already in the repo backend", file=sys.stderr)
        return 1
    slug = ms.repo_slug(root)
    target = ms._from_spec(a.to, slug, root, "migrate")
    if target.backend == "git":
        try:
            ms.pull(target)
        except RuntimeError as e:
            print(f"could not fetch the state repo: {e}", file=sys.stderr)
            return 1
    if (target.root / "gtm.json").exists() and not a.force:
        print(f"{target.root} already has gtm.json; pass --force to overwrite", file=sys.stderr)
        return 1
    target.root.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        dest = target.root / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    ms.register(slug, a.to)
    _root_for.cache_clear()
    s = upgrade(json.loads(STATE().read_text()))
    s.pop("state_commit", None)
    save_state(s)
    pushed = ms.push(target, "marketing: migrate state out of the product repo") if target.backend == "git" else ""
    print(json.dumps({"migrated_to": str(target.root), "backend": target.backend, "pushed": pushed,
                      "next": ["open a PR in the product repo that deletes .marketing/ (history rewrite is the team's call)",
                               "flush posthog-outbox.jsonl once PostHog is connected (measurement skill)"]}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("where")
    p = sub.add_parser("init")
    p.add_argument("--stage", choices=["prelaunch", "launched"], default="launched")
    p.add_argument("--motion", choices=funnel_ref()["templates"].keys())
    p.add_argument("--acv", type=float, help="annual contract value in USD")
    p.add_argument("--budget", type=float, default=20.0)
    p.add_argument("--per-run-cap", type=float, default=5.0)
    p.add_argument("--site-url", default="")
    p.add_argument("--force", action="store_true", help="reset config (last_run, keys and profile are kept)")
    for name in ("tick", "status", "ladder", "focus", "fit", "tracks", "next", "resume"):
        sub.add_parser(name)
    p = sub.add_parser("profile", help="show or set the GTM profile; changes unconfirm it")
    p.add_argument("--motion", choices=funnel_ref()["templates"].keys())
    p.add_argument("--acv", type=float)
    p.add_argument("--cycle-days", type=int)
    p.add_argument("--regulated", choices=["none", "light", "heavy"])
    p.add_argument("--buying-committee", choices=["1", "2-4", "5+"])
    p.add_argument("--geo", help="comma-separated markets, e.g. US,UK,DE")
    p.add_argument("--attention", action="append", help="CHANNEL=0..1 from customer research; repeatable")
    p.add_argument("--confirm", action="store_true", help="the human confirmed the profile")
    p = sub.add_parser("pause")
    p.add_argument("--reason", default="")
    p = sub.add_parser("budget")
    p.add_argument("--need", type=float)
    p = sub.add_parser("record")
    p.add_argument("job")
    p.add_argument("--cost", type=float)
    p.add_argument("--from-run")
    p.add_argument("--note", default="")
    p.add_argument("--event", help="event stamp for event-triggered jobs (from tick's `event`)")
    p.add_argument("--key", help="dedupe key acted on (enforces the job's cooldown)")
    p.add_argument("--failed", action="store_true", help="the action on --key failed")
    p.add_argument("--mix", help="work_session slots used, e.g. focus,standing")
    p.add_argument("--force", action="store_true", help="record despite a cooldown")
    p = sub.add_parser("may")
    p.add_argument("job")
    p.add_argument("key")
    p = sub.add_parser("metric")
    p.add_argument("action", choices=["add", "get"])
    p.add_argument("name")
    p.add_argument("value", type=float, nargs="?")
    p.add_argument("--source", default="")
    p.add_argument("--track", default="")
    p.add_argument("--date")
    p.add_argument("--cost", type=float)
    p.add_argument("--note", default="")
    p.add_argument("--days", type=int, default=90)
    p = sub.add_parser("bet")
    p.add_argument("action", choices=["open", "close", "list"])
    p.add_argument("id_pos", nargs="?")
    p.add_argument("--id")
    p.add_argument("--track", choices=TRACKS)
    p.add_argument("--channel", choices=list(channel_fit_ref()["channels"]))
    p.add_argument("--tactic")
    p.add_argument("--hypothesis", default="")
    p.add_argument("--metric")
    p.add_argument("--baseline", type=float)
    p.add_argument("--expected", type=float)
    p.add_argument("--method", choices=METHODS, default="before_after")
    p.add_argument("--control-metric")
    p.add_argument("--control-baseline", type=float)
    p.add_argument("--check")
    p.add_argument("--cost-usd", type=float, default=0.0)
    p.add_argument("--effort", default="")
    p.add_argument("--observed", type=float)
    p.add_argument("--control-observed", type=float)
    p.add_argument("--p-value", type=float)
    p.add_argument("--n", type=int, help="sample size behind the observed value")
    p.add_argument("--min-n", type=int, default=100)
    p.add_argument("--cost-per-customer", type=float)
    p.add_argument("--decision", default="")
    p.add_argument("--status")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("learnings")
    p.add_argument("--accept")
    p.add_argument("--reject")
    p = sub.add_parser("digest")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("store")
    p.add_argument("use", choices=["use"])
    p.add_argument("spec", help="a directory, a git URL, or 'repo'")
    p = sub.add_parser("sync")
    p.add_argument("direction", choices=["pull", "push"])
    p.add_argument("--message")
    p = sub.add_parser("migrate")
    p.add_argument("--to", required=True, help="a directory or git URL for the new store")
    p.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "bet" and a.id_pos and not a.id:
        a.id = a.id_pos
    return {"where": cmd_where, "init": cmd_init, "tick": cmd_tick, "status": cmd_status, "ladder": cmd_ladder,
            "focus": cmd_focus, "fit": cmd_fit, "tracks": cmd_tracks, "next": cmd_next, "budget": cmd_budget,
            "record": cmd_record, "may": cmd_may, "metric": cmd_metric, "bet": cmd_bet, "learnings": cmd_learnings,
            "pause": cmd_pause, "resume": cmd_resume, "profile": cmd_profile, "digest": cmd_digest, "store": cmd_store, "sync": cmd_sync,
            "migrate": cmd_migrate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
