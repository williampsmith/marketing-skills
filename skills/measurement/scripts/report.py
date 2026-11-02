#!/usr/bin/env python3
"""Growth scorecard: one self-contained HTML page from the state store, for teams without PostHog
or for the monthly review.

    python3 report.py [--out <state>/reports/<date>.html] [--days 90]

Shows the focus and why, each track's rungs, the funnel against its floors, AI visibility over
time, open and recent bets, and spend. Funnel counts show their age; rungs name their metric and date. No network calls,
no external assets. Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

CSS = """
:root{--bg:#f7f8f6;--fg:#1c2226;--muted:#5d6870;--rule:#d8dcd9;--card:#fff;--ok:#2f7d4a;--bad:#a24636;--na:#7a7f84;--line:#0f6b63}
@media (prefers-color-scheme:dark){:root{--bg:#14191c;--fg:#e3e7e5;--muted:#9aa5a9;--rule:#2c3438;--card:#1b2125;--ok:#7cc995;--bad:#e5917f;--na:#9aa0a4;--line:#5cc2b5}}
body{background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;padding:32px max(16px,env(safe-area-inset-left))}
main{max-width:980px;margin:0 auto;display:flex;flex-direction:column;gap:28px}
h1{margin:0;font-size:1.7rem}h2{margin:0 0 8px;font-size:1.15rem}
.muted{color:var(--muted)}.focus{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:16px}
table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--rule);border-radius:10px}
.ok{color:var(--ok)}.bad{color:var(--bad)}.na{color:var(--na)}td.num{font-variant-numeric:tabular-nums;text-align:right}
svg text{fill:var(--muted);font-size:10px}
"""


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def mark(met) -> str:
    return {True: '<span class="ok">✔ met</span>', False: '<span class="bad">✘ not met</span>'}.get(
        met, '<span class="na">? unknown</span>')


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def sparkline(rows: list[dict], w: int = 260, h: int = 48) -> str:
    pts = []
    for r in rows:
        try:
            pts.append((r["date"], float(r["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    if len(pts) < 2:
        return '<span class="muted">not enough runs yet</span>'
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    step = (w - 8) / (len(pts) - 1)
    xy = [(4 + i * step, h - 14 - (v - lo) / span * (h - 22)) for i, (_, v) in enumerate(pts)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(xy))
    lx, ly = xy[-1]
    return (f'<svg width="{w}" height="{h}" role="img" aria-label="trend">'
            f'<path d="{path}" fill="none" stroke="var(--line)" stroke-width="2"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="var(--line)"/>'
            f'<text x="4" y="{h - 2}">{esc(pts[0][0])}</text>'
            f'<text x="{w - 4}" y="{h - 2}" text-anchor="end">{esc(pts[-1][0])}: {pts[-1][1]:.0%}</text></svg>')


def build(days: int = 90) -> str:
    s = gtm.load_state()
    f = gtm.compute_focus(s)
    b = gtm.budget_info(s)
    since = (gtm.today() - dt.timedelta(days=days)).isoformat()
    parts = [f"<title>Growth scorecard {gtm.today().isoformat()}</title><meta name='viewport' content='width=device-width,initial-scale=1'>",
             f"<style>{CSS}</style><main>",
             f"<header><h1>Growth scorecard</h1><p class='muted'>{esc(gtm.today().isoformat())} · stage {esc(s.get('stage'))} · "
             f"motion {esc(s['profile'].get('motion'))} · spend ${b['spent_month']:.2f} of ${b['cap']:.0f} this month</p></header>",
             f"<section class='focus'><h2>Focus</h2><p>{esc(gtm.focus_line(f))}</p>"]
    if f.get("alerts"):
        parts.append("<ul>" + "".join(f"<li class='bad'>{esc(x)}</li>" for x in f["alerts"]) + "</ul>")
    parts.append("</section>")

    rows = []
    for st in f["funnel"]["stages"]:
        rate = f"{pct(st.get('rate'))} <span class='muted'>(floor {pct(st.get('floor'))})</span>" if "floor" in st else ""
        score = st.get("score")
        cls = "" if score is None else ("ok" if score >= 1 else "bad")
        rows.append(f"<tr><td>{esc(st['label'])}</td><td class='num'>{esc(st['count'] if st['count'] is not None else '—')}"
                    f"{'' if st['age_days'] is None else f' <span class=muted>({st[chr(97)+chr(103)+chr(101)+chr(95)+chr(100)+chr(97)+chr(121)+chr(115)]}d old)</span>'}</td>"
                    f"<td>{rate}</td><td class='num {cls}'>{esc('—' if score is None else f'{score:.2f}')}</td>"
                    f"<td class='muted'>{esc(st['track'])}</td></tr>")
    parts.append("<section><h2>Funnel (28-day counts)</h2><div class='wrap'><table><tr><th>stage</th><th>count</th>"
                 "<th>conversion</th><th>vs floor</th><th>track</th></tr>" + "".join(rows) + "</table></div></section>")

    rows = []
    for t in gtm.TRACKS:
        x = f["tracks"][t]
        if not x["enabled"]:
            rows.append(f"<tr><td>{t}</td><td colspan='3' class='muted'>off</td></tr>")
            continue
        for r in x["rungs"]:
            why = r.get("why")
            why = why if isinstance(why, str) else "; ".join(why or [])
            rows.append(f"<tr><td>{t}</td><td>{esc(r['id'])}</td><td>{mark(r['met'])}</td><td class='muted'>{esc(why)}</td></tr>")
    parts.append("<section><h2>Tracks</h2><div class='wrap'><table><tr><th>track</th><th>rung</th><th>status</th>"
                 "<th>evidence</th></tr>" + "".join(rows) + "</table></div></section>")

    vis = []
    for name, label in (("ai:mention", "named in AI answers"), ("ai:citation", "cited in AI answers"),
                        ("ai:share_of_voice", "share of voice")):
        series = [r for r in gtm.metric_rows(name) if r["date"] >= since]
        vis.append(f"<tr><td>{label}</td><td>{sparkline(series)}</td></tr>")
    parts.append(f"<section><h2>AI visibility (last {days} days)</h2><div class='wrap'><table>" + "".join(vis) + "</table></div></section>")

    bet_rows = []
    for bt in gtm.bets():
        if bt["status"] != "open" and (bt.get("closed") or "") < since:
            continue
        r = bt.get("result") or {}
        res = "" if bt["status"] == "open" else \
            f"effect {r.get('effect', '—')} vs {r.get('expected_effect', '—')} {r.get('note') or ''}".strip()
        bet_rows.append(f"<tr><td>{esc(bt['id'])}</td><td>{esc(bt['tactic'])}</td><td>{esc(bt['method'])}</td>"
                        f"<td>{esc(bt['status'])}</td><td>{esc(bt['check'])}</td><td class='muted'>{esc(res)}</td></tr>")
    parts.append("<section><h2>Bets</h2><div class='wrap'><table><tr><th>id</th><th>tactic</th><th>method</th><th>status</th>"
                 "<th>check</th><th>result</th></tr>" + ("".join(bet_rows) or "<tr><td colspan='6' class='muted'>none</td></tr>")
                 + "</table></div></section>")
    if f.get("not_pursuing"):
        parts.append("<section><h2>Not pursuing</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in f["not_pursuing"]) + "</ul></section>")
    parts.append("<p class='muted'>Generated by the marketing plugin's measurement skill from the state store. "
                 "Numbers come from the metrics store; each rung names its source.</p></main>")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--days", type=int, default=90)
    a = ap.parse_args()
    out = Path(a.out) if a.out else gtm.R() / "reports" / f"{gtm.today().isoformat()}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("<!doctype html><meta charset='utf-8'>" + build(a.days))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
