#!/usr/bin/env python3
"""Score a panel run: mentions, citations, share of voice, gaps, citation targets.

    python3 score_panel.py .marketing/runs/2026-10-31            # writes score.json + report.md there
    python3 score_panel.py RUN_DIR --previous .marketing/runs/2026-10-24

Brand and competitors come from the panel file (`brand`, `competitors`).
Deterministic and stdlib only, so two runs are comparable week to week.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


def _alias_re(aliases: list[str]) -> re.Pattern:
    alts = "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{alts})(?![\w-])", re.IGNORECASE)


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _owns(domain: str, owned: list[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in owned)


def load_answers(run_dir: Path) -> list[dict]:
    """Last successful answer per (engine, prompt, sample); errors dropped."""
    keep: dict[tuple, dict] = {}
    for line in (run_dir / "answers.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("error") or not r.get("text"):
            continue
        keep[(r["engine"], r["prompt_id"], r["sample"])] = r
    return list(keep.values())


def score(answers: list[dict], panel: dict) -> dict:
    brand = panel["brand"]
    entities = {brand["name"]: brand} | {c["name"]: c for c in panel.get("competitors", [])}
    pats = {n: _alias_re(e.get("aliases", []) + [n]) for n, e in entities.items()}
    doms = {n: [d.lower() for d in e.get("domains", [])] for n, e in entities.items()}
    me = brand["name"]

    per_answer = []
    for r in answers:
        text = r["text"]
        src_domains = [domain_of(u) for u in r.get("sources", [])]
        mentioned, first_pos = {}, {}
        for n, pat in pats.items():
            m = pat.search(text)
            mentioned[n] = bool(m)
            if m:
                first_pos[n] = m.start()
        cited = {n: any(_owns(d, doms[n]) for d in src_domains) for n in entities}
        order = sorted(first_pos, key=first_pos.get)
        per_answer.append({
            "engine": r["engine"], "prompt_id": r["prompt_id"], "bucket": r.get("bucket"),
            "prompt": r["prompt"], "sample": r["sample"],
            "mentioned": [n for n in entities if mentioned[n]],
            "cited": [n for n in entities if cited[n]],
            "rank": (order.index(me) + 1) if me in order else None,
            "brands_named": len(order),
            "source_domains": sorted(set(src_domains)),
            "fanout": r.get("fanout", []),
        })

    def summarize(rows):
        n = len(rows) or 1
        tot_mentions = sum(len(a["mentioned"]) for a in rows) or 1
        ranks = [a["rank"] for a in rows if a["rank"]]
        return {
            "answers": len(rows),
            "mention_rate": round(sum(me in a["mentioned"] for a in rows) / n, 3),
            "citation_rate": round(sum(me in a["cited"] for a in rows) / n, 3),
            "share_of_voice": round(sum(me in a["mentioned"] for a in rows) / tot_mentions, 3),
            "avg_rank_when_named": round(sum(ranks) / len(ranks), 2) if ranks else None,
            "competitors": {
                c: {"mention_rate": round(sum(c in a["mentioned"] for a in rows) / n, 3),
                    "citation_rate": round(sum(c in a["cited"] for a in rows) / n, 3)}
                for c in entities if c != me
            },
        }

    by_engine = collections.defaultdict(list)
    by_bucket = collections.defaultdict(list)
    for a in per_answer:
        by_engine[a["engine"]].append(a)
        by_bucket[a["bucket"] or "unbucketed"].append(a)

    # A prompt is "won" on an engine when any sample names the brand.
    status = collections.defaultdict(dict)
    for a in per_answer:
        prev = status[a["prompt_id"]].get(a["engine"], False)
        status[a["prompt_id"]][a["engine"]] = prev or (me in a["mentioned"])

    gaps = [a for a in per_answer if me not in a["mentioned"] and len(a["mentioned"]) > 0]
    absent = [a for a in per_answer if not a["mentioned"]]
    owned_all = [d for ds in doms.values() for d in ds]
    target_counts = collections.Counter(
        d for a in gaps for d in a["source_domains"] if not _owns(d, owned_all))
    all_counts = collections.Counter(d for a in per_answer for d in a["source_domains"])
    fanout = collections.Counter(q.lower() for a in per_answer for q in a["fanout"])

    return {
        "brand": me,
        "overall": summarize(per_answer),
        "by_engine": {e: summarize(rows) for e, rows in sorted(by_engine.items())},
        "by_bucket": {b: summarize(rows) for b, rows in sorted(by_bucket.items())},
        "prompt_status": status,
        "gaps": [{"engine": a["engine"], "prompt_id": a["prompt_id"], "prompt": a["prompt"],
                  "named_instead": a["mentioned"], "sources": a["source_domains"]} for a in gaps],
        "no_tracked_brand": [{"engine": a["engine"], "prompt_id": a["prompt_id"], "prompt": a["prompt"]}
                             for a in absent],
        "citation_targets": target_counts.most_common(25),
        "top_cited_domains": all_counts.most_common(25),
        "fanout_queries": fanout.most_common(40),
    }


def diff(cur: dict, prev: dict) -> dict:
    out = {"overall": {}, "by_engine": {}, "won": [], "lost": []}
    for k in ("mention_rate", "citation_rate", "share_of_voice"):
        out["overall"][k] = round(cur["overall"][k] - prev["overall"].get(k, 0), 3)
    for e, s in cur["by_engine"].items():
        p = prev["by_engine"].get(e)
        if p:
            out["by_engine"][e] = {k: round(s[k] - p[k], 3) for k in ("mention_rate", "citation_rate")}
    for pid, engines in cur["prompt_status"].items():
        for e, won in engines.items():
            was = prev.get("prompt_status", {}).get(pid, {}).get(e)
            if was is None:
                continue
            if won and not was:
                out["won"].append(f"{pid} on {e}")
            if was and not won:
                out["lost"].append(f"{pid} on {e}")
    return out


def pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def report(s: dict, d: dict | None, run: str) -> str:
    o = s["overall"]
    L = [f"# AI visibility — {s['brand']} — {run}", "",
         f"{o['answers']} answers. Named in **{pct(o['mention_rate'])}**, cited in **{pct(o['citation_rate'])}**, "
         f"share of voice **{pct(o['share_of_voice'])}**, average position when named {o['avg_rank_when_named'] or '—'}.", ""]
    if d:
        L += [f"Change since previous run: mention {d['overall']['mention_rate']:+.1%}, "
              f"citation {d['overall']['citation_rate']:+.1%}, share of voice {d['overall']['share_of_voice']:+.1%}. "
              f"Won {len(d['won'])}, lost {len(d['lost'])}.", ""]
        if d["lost"]:
            L += ["Lost: " + ", ".join(d["lost"]), ""]
        if d["won"]:
            L += ["Won: " + ", ".join(d["won"]), ""]
    comps = list(o["competitors"])
    L += ["## By engine", "", "| engine | answers | named | cited | SoV | " + " | ".join(comps) + " |",
          "|---|---|---|---|---|" + "---|" * len(comps)]
    for e, x in s["by_engine"].items():
        L.append(f"| {e} | {x['answers']} | {pct(x['mention_rate'])} | {pct(x['citation_rate'])} | "
                 f"{pct(x['share_of_voice'])} | " + " | ".join(pct(x["competitors"][c]["mention_rate"]) for c in comps) + " |")
    L += ["", "## By prompt bucket", "", "| bucket | answers | named | cited |", "|---|---|---|---|"]
    for b, x in s["by_bucket"].items():
        L.append(f"| {b} | {x['answers']} | {pct(x['mention_rate'])} | {pct(x['citation_rate'])} |")
    L += ["", "## Gaps — a competitor was named, you were not", ""]
    seen = set()
    for g in s["gaps"]:
        key = g["prompt_id"]
        if key in seen:
            continue
        seen.add(key)
        engines = sorted({x["engine"] for x in s["gaps"] if x["prompt_id"] == key})
        named = sorted({n for x in s["gaps"] if x["prompt_id"] == key for n in x["named_instead"]})
        L.append(f"- `{key}` {g['prompt']} — {', '.join(engines)}; named: {', '.join(named)}")
    L += ["", "## Citation targets — domains the engines cite on your gap prompts", "",
          "Get mentioned (accurately) on these and the engines have a source that names you.", ""]
    L += [f"- {dom} ({n})" for dom, n in s["citation_targets"]]
    L += ["", "## Fan-out queries the engines searched", "",
          "Each is an intent a page can answer directly.", ""]
    L += [f"- {q} ({n})" for q, n in s["fanout_queries"][:25]]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--panel", default=".marketing/prompt-panel.json")
    ap.add_argument("--previous", default=None, help="earlier run dir to diff against")
    a = ap.parse_args()
    run = Path(a.run_dir)
    panel = json.loads(Path(a.panel).read_text())
    s = score(load_answers(run), panel)
    d = None
    if a.previous:
        prev_score = Path(a.previous) / "score.json"
        if prev_score.exists():
            d = diff(s, json.loads(prev_score.read_text()))
            s["diff_vs"] = Path(a.previous).name
            s["diff"] = d
    (run / "score.json").write_text(json.dumps(s, indent=2, ensure_ascii=False))
    (run / "report.md").write_text(report(s, d, run.name))
    print((run / "report.md").read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
