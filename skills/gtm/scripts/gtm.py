#!/usr/bin/env python3
"""gtm state engine: what's due, where we are on the ladder, what we've spent.

The deterministic half of the gtm skill. The agent supplies the judgment; this
script makes sure every run, on any host and any model, agrees on the facts.

    python3 gtm.py init [--stage prelaunch|launched] [--budget 20]   # write .marketing/gtm.json
    python3 gtm.py tick                      # JSON: due jobs (+ why), ladder, budget, alerts
    python3 gtm.py status                    # human summary, read-only
    python3 gtm.py ladder                    # rung diagnosis with the numbers behind it
    python3 gtm.py budget [--need 1.50]      # month-to-date spend; exit 2 if --need would exceed the cap
    python3 gtm.py record JOB [--cost 0.62 | --from-run DIR] [--note "..."]
    python3 gtm.py digest                    # write the data half of .marketing/digests/<date>.md

State: .marketing/gtm.json (config + last runs), .marketing/spend.jsonl (ledger).
Reads, never writes, what the other skills produce. Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

M = Path(".marketing")
STATE = M / "gtm.json"
SPEND = M / "spend.jsonl"

# Jobs: cadence in days, est. cost, which stages run them, and which skill does the work.
DEFAULT_JOBS = {
    "access_check":      {"every_days": 1,  "usd": 0.0,  "stages": ["launched"], "skill": "ai-search-optimization"},
    "watch":             {"every_days": 7,  "usd": 0.0,  "stages": ["prelaunch", "launched"], "skill": "comparison-pages"},
    "audit":             {"every_days": 7,  "usd": 1.0,  "stages": ["launched"], "skill": "ai-visibility-audit"},
    "outreach_refresh":  {"every_days": 7,  "usd": 0.5,  "stages": ["launched"], "skill": "citation-outreach", "after": "audit"},
    "work_session":      {"every_days": 7,  "usd": 1.5,  "stages": ["prelaunch", "launched"], "skill": "gtm"},
    "launch_scan":       {"every_days": 7,  "usd": 0.0,  "stages": ["prelaunch", "launched"], "skill": "gtm"},
    "strategy_review":   {"every_days": 30, "usd": 0.0,  "stages": ["prelaunch", "launched"], "skill": "gtm"},
    "entity_probe":      {"every_days": 90, "usd": 0.2,  "stages": ["prelaunch", "launched"], "skill": "entity-presence"},
    "comparison_reverify": {"every_days": 90, "usd": 0.1, "stages": ["launched"], "skill": "comparison-pages"},
    "panel_review":      {"every_days": 90, "usd": 0.0,  "stages": ["launched"], "skill": "ai-visibility-audit"},
}

# Ladder thresholds on audit metrics (mention rate per bucket group). Editable in gtm.json.
DEFAULT_LADDER = {
    "known":      {"buckets": ["brand"], "min_mention": 0.8},
    "associated": {"buckets": ["category", "problem", "jobs"], "min_mention": 0.3},
    "preferred":  {"buckets": ["comparison", "alternatives"], "min_mention": 0.5, "max_avg_rank": 2.0},
}
RUNGS = ["reachable", "known", "associated", "preferred", "converting"]
RUNG_SKILLS = {
    "reachable": ["ai-search-optimization"],
    "known": ["entity-presence", "ai-search-optimization"],
    "associated": ["one-pager", "citation-outreach"],
    "preferred": ["comparison-pages", "citation-outreach"],
    "converting": ["ai-referral tracking (ai-search-optimization step 5)"],
}


def today() -> dt.date:
    return dt.date.today()


def load_state() -> dict:
    if not STATE.exists():
        sys.exit("no .marketing/gtm.json: run `gtm.py init` (gtm init mode) first")
    s = json.loads(STATE.read_text())
    s.setdefault("jobs", {})
    for k, v in DEFAULT_JOBS.items():
        s["jobs"].setdefault(k, dict(v))
    s.setdefault("ladder", DEFAULT_LADDER)
    s.setdefault("last_run", {})
    s.setdefault("accepted_problems", [])
    return s


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2) + "\n")


def spend_rows() -> list[dict]:
    if not SPEND.exists():
        return []
    return [json.loads(x) for x in SPEND.read_text().splitlines() if x.strip()]


def month_spend(rows: list[dict], on: dt.date | None = None) -> float:
    on = on or today()
    key = on.strftime("%Y-%m")
    return round(sum(r.get("usd", 0) for r in rows if r.get("date", "").startswith(key)), 4)


def latest_run_dir() -> Path | None:
    runs = sorted(p for p in (M / "runs").glob("20*") if (p / "score.json").exists()) if (M / "runs").exists() else []
    return runs[-1] if runs else None


def latest_access() -> dict | None:
    p = M / "access" / "latest.json"
    return json.loads(p.read_text()) if p.exists() else None


# --------------------------------------------------------------------------- ladder
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
    out["rungs"]["converting"] = {"met": s.get("converting_met"), "why": "set converting_met in gtm.json from analytics"}

    for r in RUNGS:
        if out["rungs"][r]["met"] is not True:
            out["current"] = r
            break
    out["work_on"] = RUNG_SKILLS.get(out["current"], [])
    return out


# --------------------------------------------------------------------------- due
def due(s: dict) -> tuple[list[dict], list[str]]:
    stage = s.get("stage", "launched")
    jobs, alerts = [], []
    t = today()
    for name, j in s["jobs"].items():
        if j.get("enabled", True) is False or stage not in j.get("stages", ["launched"]):
            continue
        last = s["last_run"].get(name)
        age = (t - dt.date.fromisoformat(last)).days if last else None
        why = None
        if age is None:
            why = "never run"
        elif age >= j["every_days"]:
            why = f"last run {age}d ago (every {j['every_days']}d)"
        dep = j.get("after")
        if dep and why:
            dep_last = s["last_run"].get(dep)
            if not dep_last or (last and dep_last <= last):
                why = None  # wait until its upstream job has produced something new
        if why:
            jobs.append({"job": name, "why": why, "skill": j["skill"], "usd": j["usd"]})

    # Event triggers from other skills' outputs.
    wr = M / "watch" / "report.md"
    if wr.exists():
        txt = wr.read_text()
        seen = s["last_run"].get("comparison_refresh")
        stamp = txt.splitlines()[0].rsplit("— ", 1)[-1] if txt else ""
        if "## Changed:" in txt and stamp and stamp != seen:
            jobs.append({"job": "comparison_refresh", "why": f"watched pages changed ({stamp})",
                         "skill": "comparison-pages", "usd": 0.05, "event": stamp})
    acc = latest_access()
    prev = M / "access" / "previous.json"
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
    return jobs, alerts


def budget_info(s: dict) -> dict:
    cap = float(s.get("budget_usd_month", 20))
    spent = month_spend(spend_rows())
    return {"cap": cap, "spent_month": spent, "remaining": round(cap - spent, 4)}


# --------------------------------------------------------------------------- commands
def cmd_init(a) -> int:
    M.mkdir(exist_ok=True)
    if STATE.exists() and not a.force:
        print(f"{STATE} exists; pass --force to reset config (last_run is kept)")
        return 1
    old = json.loads(STATE.read_text()) if STATE.exists() else {}
    s = {
        "stage": a.stage,
        "goal": old.get("goal", ""),
        "site_url": a.site_url or old.get("site_url", ""),
        "key_paths": old.get("key_paths", ["/"]),
        "repo_default_branch": old.get("repo_default_branch", "main"),
        "budget_usd_month": a.budget,
        "per_run_cap_usd": a.per_run_cap,
        "notify": old.get("notify", {"channel": "none"}),
        "state_commit": old.get("state_commit", "direct"),
        "accepted_problems": old.get("accepted_problems", []),
        "known_issues": old.get("known_issues", []),
        "converting_met": old.get("converting_met"),
        "ladder": old.get("ladder", DEFAULT_LADDER),
        "jobs": old.get("jobs", DEFAULT_JOBS),
        "last_run": old.get("last_run") or {
            # reviews start their clock at init; launch_scan scans only changes after init
            k: today().isoformat() for k in ("launch_scan", "strategy_review", "panel_review", "comparison_reverify")},
    }
    save_state(s)
    print(f"wrote {STATE} (stage={a.stage}, budget=${a.budget}/month)")
    return 0


def cmd_tick(a) -> int:
    s = load_state()
    jobs, alerts = due(s)
    b = budget_info(s)
    affordable, deferred = [], []
    left = min(b["remaining"], float(s.get("per_run_cap_usd", 5)))
    for j in sorted(jobs, key=lambda j: (j["usd"] > 0, j["usd"])):  # free first
        if j["usd"] <= left:
            affordable.append(j)
            left -= j["usd"]
        else:
            deferred.append({**j, "deferred": "budget"})
    out = {"date": today().isoformat(), "stage": s.get("stage"), "due": affordable, "deferred": deferred,
           "alerts": alerts, "budget": b, "ladder": ladder(s)}
    print(json.dumps(out, indent=2))
    return 0


def cmd_ladder(a) -> int:
    print(json.dumps(ladder(load_state()), indent=2))
    return 0


def cmd_budget(a) -> int:
    b = budget_info(load_state())
    print(json.dumps(b))
    if a.need is not None and a.need > b["remaining"]:
        print(f"need ${a.need:.2f} > remaining ${b['remaining']:.2f}", file=sys.stderr)
        return 2
    return 0


def cmd_record(a) -> int:
    s = load_state()
    cost = a.cost or 0.0
    if a.from_run:
        rows = [json.loads(x) for x in (Path(a.from_run) / "answers.jsonl").read_text().splitlines() if x.strip()]
        # record a run once: its answers.jsonl holds every call it paid for, resumes included
        cost = round(sum(r.get("cost_usd") or 0 for r in rows), 4)
    s["last_run"][a.job] = a.event or today().isoformat()
    save_state(s)
    if cost or a.note:
        with SPEND.open("a") as f:
            f.write(json.dumps({"date": today().isoformat(), "job": a.job, "usd": cost, "note": a.note}) + "\n")
    print(f"recorded {a.job} on {s['last_run'][a.job]}" + (f", ${cost:.4f}" if cost else ""))
    return 0


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def cmd_status(a) -> int:
    s = load_state()
    lad = ladder(s)
    jobs, alerts = due(s)
    b = budget_info(s)
    print(f"stage: {s.get('stage')}   goal: {s.get('goal') or '(unset)'}")
    print(f"budget: ${b['spent_month']:.2f} of ${b['cap']:.2f} this month")
    print(f"ladder: working on **{lad['current']}** → {', '.join(lad['work_on'])}")
    for r in RUNGS:
        x = lad["rungs"][r]
        mark = {True: "✔", False: "✘", None: "?"}[x["met"]]
        detail = f"mention {_pct(x.get('mention'))}" if "mention" in x else (x.get("why") if isinstance(x.get("why"), str) else "; ".join(x.get("why") or []))
        print(f"  {mark} {r:11} {detail}")
    print("due:", ", ".join(f"{j['job']} ({j['why']})" for j in jobs) or "nothing")
    for al in alerts:
        print("ALERT:", al)
    return 0


def cmd_digest(a) -> int:
    s = load_state()
    lad = ladder(s)
    b = budget_info(s)
    jobs, alerts = due(s)
    run = latest_run_dir()
    L = [f"# GTM digest — {today().isoformat()}", "",
         "<!-- the agent fills: Needs you / Done / Learned / Next week. Everything below the line is generated. -->",
         "", "## Needs you", "", "_(agent: PRs to review, drafts to send, logins to use, decisions)_", "",
         "## Done since last digest", "", "## Learned", "", "## Next week", "", "---", "",
         f"**Stage** {s.get('stage')} · **ladder** working on `{lad['current']}` → {', '.join(lad['work_on'])} · "
         f"**spend** ${b['spent_month']:.2f} / ${b['cap']:.0f} this month", ""]
    for al in alerts:
        L.append(f"> ⚠ {al}")
    if run:
        sc = json.loads((run / "score.json").read_text())
        o = sc["overall"]
        L += [f"**Audit {run.name}**: named {_pct(o['mention_rate'])}, cited {_pct(o['citation_rate'])}, "
              f"share of voice {_pct(o['share_of_voice'])}."]
        d = sc.get("diff")
        if d:
            L.append(f"Since {sc.get('diff_vs')}: mention {d['overall']['mention_rate']:+.1%}, "
                     f"won {len(d['won'])}, lost {len(d['lost'])}.")
        L.append(f"Full report: `{run / 'report.md'}`")
    tp = M / "outreach" / "targets.json"
    if tp.exists():
        t = json.loads(tp.read_text())
        counts: dict = {}
        for x in t:
            counts[x.get("status", "new")] = counts.get(x.get("status", "new"), 0) + 1
        L.append("**Outreach**: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if (M / "watch" / "report.md").exists() and "## Changed:" in (M / "watch" / "report.md").read_text():
        L.append("**Watch**: pages changed. See `.marketing/watch/report.md`")
    L += ["", "**Due next tick**: " + (", ".join(j["job"] for j in jobs) or "nothing")]
    out = M / "digests" / f"{today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not a.force:
        print(f"{out} exists (agent may have filled it); pass --force to regenerate")
        return 1
    out.write_text("\n".join(L) + "\n")
    print(out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--stage", choices=["prelaunch", "launched"], default="launched")
    p.add_argument("--budget", type=float, default=20.0)
    p.add_argument("--per-run-cap", type=float, default=5.0)
    p.add_argument("--site-url", default="")
    p.add_argument("--force", action="store_true")
    sub.add_parser("tick")
    sub.add_parser("status")
    sub.add_parser("ladder")
    p = sub.add_parser("budget")
    p.add_argument("--need", type=float)
    p = sub.add_parser("record")
    p.add_argument("job")
    p.add_argument("--cost", type=float)
    p.add_argument("--from-run")
    p.add_argument("--note", default="")
    p.add_argument("--event", help="event stamp for event-triggered jobs (from tick's `event`)")
    p = sub.add_parser("digest")
    p.add_argument("--force", action="store_true")
    a = ap.parse_args()
    return {"init": cmd_init, "tick": cmd_tick, "status": cmd_status, "ladder": cmd_ladder,
            "budget": cmd_budget, "record": cmd_record, "digest": cmd_digest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
