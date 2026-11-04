#!/usr/bin/env python3
"""The daily report's data layer: one dataset of numbers for the agent to read and chart.

    python3 report_data.py build [--days 84] [--offline] [--out DIR]   # → <state>/reports/daily/<date>/data.json
    python3 report_data.py show [DIR]                                   # the headline reading of a built dataset

`build` collects, from the state store, every recorded metric, the funnel against its floors, open and
recently closed bets, spend by track, the operator's own actions (to annotate charts with) and the
batches waiting on a human. With PostHog connected (and not --offline) it adds one daily series per
funnel stage event. It then computes the derived numbers the analysis rests on, so they are the same
however the agent words them:

- each daily series in weeks: this week, the median of the weeks before, the change, a robust normal
  band (median ± 3 × 1.4826 × MAD) and an exact Poisson test of this week against the earlier mean.
  A week is only `unusual` when both say so; with fewer than 4 earlier weeks or an expected count
  under 5 the verdict is `too_little_data`, never a trend.
- each funnel step's rate with a 95% Wilson interval and its floor.
- each open bet's latest value against its baseline and expected value.

Charts take their numbers from this file only. Stdlib only; Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

DAYS = 84            # twelve weeks: enough earlier weeks to know what normal looks like
MIN_WEEKS = 4        # earlier weeks needed before a week can be called unusual
MIN_EXPECTED = 5     # an expected weekly count below this is too small to test
P_UNUSUAL = 0.01     # Poisson tail, two-sided


# --------------------------------------------------------------------------- statistics
def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson interval for k successes in n trials (rates that can't be computed give None)."""
    if not n or n <= 0 or k is None or k < 0 or k > n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def _log_pmf(k: int, lam: float) -> float:
    return k * math.log(lam) - lam - math.lgamma(k + 1)


def poisson_two_sided(k: int, lam: float) -> float:
    """P(an observation at least this far out) under Poisson(lam): twice the smaller tail, capped at 1."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    k = int(round(k))
    lower = sum(math.exp(_log_pmf(i, lam)) for i in range(0, k + 1))
    upper = 1.0 - sum(math.exp(_log_pmf(i, lam)) for i in range(0, k))
    return round(min(1.0, 2 * min(lower, upper)), 6)


def weekly(days: list[dict], end: dt.date) -> list[dict]:
    """Daily rows {date, value} → whole weeks ending on `end`, oldest first. Partial weeks are dropped."""
    by_day = {r["date"]: float(r["value"]) for r in days}
    first = min((gtm._date(d) for d in by_day), default=end)
    weeks = []
    stop = end
    while (stop - dt.timedelta(days=6)) >= first:
        start = stop - dt.timedelta(days=6)
        total = sum(by_day.get((start + dt.timedelta(days=i)).isoformat(), 0.0) for i in range(7))
        weeks.append({"start": start.isoformat(), "end": stop.isoformat(), "value": total})
        stop = start - dt.timedelta(days=1)
    return list(reversed(weeks))


def read_week(weeks: list[dict], counts: bool = True) -> dict:
    """The reading of the latest week against the earlier ones. Deterministic; the agent words it."""
    if not weeks:
        return {"verdict": "no_data"}
    cur = weeks[-1]["value"]
    prior = [w["value"] for w in weeks[:-1]]
    out = {"this_week": cur, "weeks_before": len(prior)}
    if len(prior) < MIN_WEEKS:
        out["verdict"] = "too_little_data"
        out["why"] = f"{len(prior)} earlier weeks; {MIN_WEEKS} needed before a week can be unusual"
        return out
    med = statistics.median(prior)
    mad = statistics.median(abs(x - med) for x in prior) * 1.4826
    mean = statistics.fmean(prior)
    out.update({"median_before": round(med, 4), "mean_before": round(mean, 4),
                "change": round(cur - med, 4),
                "change_pct": None if not med else round((cur - med) / med, 4),
                "band": [round(med - 3 * mad, 4), round(med + 3 * mad, 4)]})
    outside = cur < out["band"][0] or cur > out["band"][1] if mad > 0 else cur != med
    if counts:
        if mean < MIN_EXPECTED:
            out["verdict"] = "too_little_data"
            out["why"] = f"about {mean:.1f} a week; under {MIN_EXPECTED} a week, changes are mostly noise"
            return out
        out["poisson_p"] = poisson_two_sided(int(round(cur)), mean)
        unusual = outside and out["poisson_p"] < P_UNUSUAL
    else:
        unusual = outside
    out["verdict"] = ("unusually_high" if cur > med else "unusually_low") if unusual else "normal"
    return out


# --------------------------------------------------------------------------- sources
def store_metrics(since: dt.date) -> dict:
    """Every metric file in the store, as rows since `since`."""
    out = {}
    d = gtm.R() / "metrics"
    if not d.exists():
        return out
    for f in sorted(d.glob("*.jsonl")):
        rows = [r for r in gtm.read_jsonl(f) if r.get("date", "") >= since.isoformat()]
        if not rows:
            continue
        name = rows[-1].get("metric") or f.stem
        out[name] = [{"date": r["date"], "value": r["value"], "source": r.get("source", "")}
                     for r in sorted(rows, key=lambda r: r["date"]) if isinstance(r.get("value"), (int, float))]
    return out


def posthog_daily(s: dict, days: int, end: dt.date) -> tuple[dict, list[str]]:
    """Distinct people per day for each stage event in gtm.json measurement.stage_events."""
    notes = []
    if not s["connections"].get("posthog"):
        return {}, ["PostHog isn't connected: daily series come from the store only"]
    try:
        sys.path.insert(0, str(HERE.parents[2] / "measurement" / "scripts"))
        import posthog  # noqa: E402
    except ImportError:
        return {}, ["the measurement skill isn't installed: no PostHog series"]
    stage_events = (s.get("measurement") or {}).get("stage_events") or {}
    out = {}
    for stage, event in stage_events.items():
        q = (f"SELECT toString(toDate(timestamp)) AS d, count(DISTINCT person_id) FROM events "
             f"WHERE event = {posthog.lit(event)} AND timestamp > now() - INTERVAL {int(days) + 1} DAY "
             f"GROUP BY d ORDER BY d")
        try:
            rows = posthog.query(q)
        except Exception as e:  # noqa: BLE001  one failed stage shouldn't lose the others
            notes.append(f"stage {stage}: {e}")
            continue
        got = {str(r[0])[:10]: float(r[1]) for r in rows if r and r[0] is not None}
        start = end - dt.timedelta(days=days - 1)
        out[f"daily:{stage}"] = [{"date": (start + dt.timedelta(days=i)).isoformat(),
                                  "value": got.get((start + dt.timedelta(days=i)).isoformat(), 0.0)}
                                 for i in range(days)]
    return out, notes


def posthog_links(s: dict) -> dict:
    links = dict((s.get("measurement") or {}).get("links") or {})
    try:
        sys.path.insert(0, str(HERE.parents[2] / "measurement" / "scripts"))
        import posthog  # noqa: E402
        import os
        pid = os.environ.get("POSTHOG_PROJECT_ID", "").strip()
        if pid and s["connections"].get("posthog"):
            links.setdefault("PostHog project", f"{posthog.hosts()[1]}/project/{pid}")
    except Exception:  # noqa: BLE001  links are a convenience
        pass
    return links


def actions(s: dict, since: dt.date) -> list[dict]:
    """What the operator did, dated, to annotate charts: work, launches, bets, news decisions, sends."""
    kinds = {name: j.get("kind") for name, j in s["jobs"].items()}
    out = []
    for r in gtm.spend_rows():
        if r.get("date", "") >= since.isoformat() and kinds.get(r.get("job")) == "improvement":
            out.append({"date": r["date"], "kind": "work", "label": r["job"], "note": r.get("note", "")})
    for b in gtm.bets():
        if b.get("opened", "") >= since.isoformat():
            out.append({"date": b["opened"], "kind": "bet_opened", "label": b["id"], "note": b.get("tactic", "")})
        if b.get("closed") and b["closed"] >= since.isoformat():
            out.append({"date": b["closed"], "kind": "bet_closed", "label": b["id"], "note": b.get("status", "")})
    launches = gtm.R() / "launches"
    if launches.exists():
        for f in sorted(launches.glob("*.md")):
            if f.name[:10] >= since.isoformat():
                out.append({"date": f.name[:10], "kind": "launch", "label": f.stem[11:] or f.stem, "note": ""})
    for c in gtm.read_jsonl(gtm.R() / "news" / "candidates.jsonl"):
        if c.get("status") in ("refresh", "react", "pitch") and (c.get("decided") or "") >= since.isoformat():
            out.append({"date": c["decided"], "kind": f"news_{c['status']}", "label": c.get("title", "")[:80],
                        "note": c.get("url", "")})
    for r in gtm.read_jsonl(gtm.R() / "sends.jsonl"):
        if r.get("date", "") >= since.isoformat():
            out.append({"date": r["date"], "kind": "send", "label": r.get("channel", ""), "note": r.get("batch", "")})
    return sorted(out, key=lambda x: x["date"])


def needs_human() -> list[dict]:
    """Drafted send batches nobody has approved yet: one Slack message each."""
    out = []
    sends = gtm.R() / "sends"
    if not sends.exists():
        return out
    for d in sorted(p for p in sends.iterdir() if p.is_dir()):
        drafts = gtm.read_jsonl(d / "drafts.jsonl")
        if drafts and not gtm.approved_hashes(d.name):
            out.append({"kind": "approve_batch", "batch": d.name, "drafts": len(drafts),
                        "path": str(d / "drafts.jsonl"),
                        "apply_with": f"gtm.py approve {d.name} --count N --quote … --approver … --source …"})
    return out


def spend_by_track(s: dict, month: str) -> dict:
    tracks = {name: j.get("track") or "other" for name, j in s["jobs"].items()}
    out: dict = {}
    for r in gtm.spend_rows():
        if r.get("date", "").startswith(month):
            t = tracks.get(r.get("job"), "other")
            out[t] = round(out.get(t, 0.0) + float(r.get("usd") or 0), 4)
    return out


# --------------------------------------------------------------------------- build
def build(days: int = DAYS, offline: bool = False, end: dt.date | None = None) -> dict:
    s = gtm.load_state()
    end = end or gtm.today() - dt.timedelta(days=1)   # yesterday: today is still filling up
    since = end - dt.timedelta(days=days - 1)
    notes: list[str] = []
    series: dict = {}
    if not offline:
        ph, n = posthog_daily(s, days, end)
        series.update(ph)
        notes += n
    readings = {}
    for name, rows in series.items():
        weeks = weekly(rows, end)
        readings[name] = {"weeks": weeks, **read_week(weeks, counts=True)}
    metrics = store_metrics(since)
    fun = gtm.funnel(s)
    steps = []
    by_id = {st["id"]: st for st in fun["stages"]}
    for st in fun["stages"]:
        row = {k: st.get(k) for k in ("id", "label", "track", "count", "age_days", "fresh", "from", "rate",
                                       "floor", "enough_data", "score")}
        base = by_id.get(st.get("from") or "")
        if st.get("rate") is not None and base and base.get("count"):
            row["interval"] = wilson(st["count"], base["count"])
            if row["interval"] and st.get("floor") is not None:
                lo, hi = row["interval"]
                row["vs_floor"] = "below" if hi < st["floor"] else "above" if lo > st["floor"] else "unclear"
        steps.append(row)
    bets_out = []
    for b in gtm.bets():
        if b["status"] == "open" or (b.get("closed") and gtm._date(b["closed"]) >= since):
            latest = gtm.metric_latest(b["metric"]) if b.get("metric") else None
            bets_out.append({k: b.get(k) for k in ("id", "track", "channel", "tactic", "metric", "baseline", "expected",
                                                    "method", "status", "opened", "check", "closed", "result")}
                            | {"latest": latest and {"date": latest["date"], "value": latest["value"]}})
    b = gtm.budget_info(s)
    month = gtm.today().strftime("%Y-%m")
    focus = gtm.compute_focus(s)
    return {
        "schema": 1,
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": since.isoformat(), "end": end.isoformat(), "days": days},
        "product": {"site_url": s.get("site_url"), "stage": s.get("stage"), "goal": s.get("goal"),
                    "motion": s["profile"].get("motion")},
        "focus": {"track": focus.get("track"), "rung": focus.get("rung"), "why": focus.get("reason"),
                  "line": gtm.focus_line(focus)},
        "series": series,
        "readings": readings,
        "metrics": metrics,
        "funnel": {"steps": steps, "min_sample": fun["min_sample"], "north_star": fun["north_star"]},
        "bets": bets_out,
        "actions": actions(s, since),
        "spend": {"month": month, "spent": b["spent_month"], "cap": b["cap"], "by_track": spend_by_track(s, month)},
        "needs_human": needs_human(),
        "links": posthog_links(s),
        "notes": notes,
    }


def headline(data: dict) -> list[str]:
    """One line per reading worth a sentence: unusual weeks first, then normal ones, then thin ones."""
    order = {"unusually_high": 0, "unusually_low": 0, "normal": 1, "too_little_data": 2, "no_data": 3}
    lines = []
    for name, r in sorted(data["readings"].items(), key=lambda kv: order.get(kv[1]["verdict"], 9)):
        v = r["verdict"]
        if v in ("unusually_high", "unusually_low", "normal"):
            pct = r.get("change_pct")
            lines.append(f"{name}: {v}, {r['this_week']:g} this week vs median {r['median_before']:g}"
                         + (f" ({pct:+.0%})" if pct is not None else "")
                         + (f", p={r['poisson_p']:.3g}" if "poisson_p" in r else ""))
        else:
            lines.append(f"{name}: {v}" + (f" ({r['why']})" if r.get("why") else ""))
    for st in data["funnel"]["steps"]:
        if st.get("vs_floor") in ("below", "above"):
            lo, hi = st["interval"]
            lines.append(f"funnel {st['id']}: {st['rate']:.1%} (95% {lo:.1%}-{hi:.1%}) is {st['vs_floor']} "
                         f"its floor {st['floor']:.1%}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--days", type=int, default=DAYS)
    p.add_argument("--offline", action="store_true", help="store only; no PostHog queries")
    p.add_argument("--out", help="directory (default <state>/reports/daily/<date>/)")
    p = sub.add_parser("show")
    p.add_argument("dir", nargs="?")
    a = ap.parse_args()
    if a.cmd == "build":
        if a.days < 14:
            print("--days must be at least 14", file=sys.stderr)
            return 1
        data = build(a.days, a.offline)
        out = Path(a.out) if a.out else gtm.R() / "reports" / "daily" / gtm.today().isoformat()
        out.mkdir(parents=True, exist_ok=True)
        gtm.atomic_write(out / "data.json", json.dumps(data, indent=1) + "\n")
        print(json.dumps({"data": str(out / "data.json"), "headline": headline(data), "notes": data["notes"],
                          "needs_human": len(data["needs_human"])}, indent=2))
        return 0
    d = Path(a.dir) if a.dir else gtm.R() / "reports" / "daily" / gtm.today().isoformat()
    if not (d / "data.json").exists():
        print(f"no data.json in {d}: run `report_data.py build` first", file=sys.stderr)
        return 1
    print("\n".join(headline(json.loads((d / "data.json").read_text()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
