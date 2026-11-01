#!/usr/bin/env python3
"""Run a prompt panel across AI answer engines through the treg CLI.

Reads .marketing/prompt-panel.json, calls every enabled engine for every prompt
(`treg --json call <endpoint> ...`), stores each raw response and appends one
normalized line per answer to .marketing/runs/<date>/answers.jsonl.

Stdlib only. Resumable: a (engine, prompt, sample) already in answers.jsonl is
never called again, because every call bills.

    python3 run_panel.py --dry-run                 # plan + cost estimate, no calls
    python3 run_panel.py --limit 2                 # smoke: first 2 prompts only
    python3 run_panel.py --max-usd 2.50            # full run with a spend ceiling
    python3 run_panel.py --engines chatgpt,perplexity --prompts cat-01,cmp-02
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

TEXT_KEYS = ("markdown", "text", "answer", "content", "response", "message")
URL_KEYS = ("url", "link", "source_url", "uri", "href")
FANOUT_KEYS = ("searchQueries", "search_queries", "fanout_queries", "queries")
URL_RE = re.compile(r"https?://[^\s)\]>\"'`]+")


# --------------------------------------------------------------------------- normalize
def _walk(node, fn, path=()):
    fn(node, path)
    if isinstance(node, dict):
        for k, v in node.items():
            _walk(v, fn, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, fn, path + (i,))


def _longest_text(body) -> str:
    """The answer text: the longest string held under a text-like key."""
    best = ""

    def fn(node, path):
        nonlocal best
        if isinstance(node, str) and path and isinstance(path[-1], str):
            if path[-1].lower() in TEXT_KEYS and len(node) > len(best) and not node.startswith("http"):
                best = node

    _walk(body, fn)
    return best


def _sources(body, text: str) -> list[str]:
    seen: dict[str, None] = {}

    def fn(node, path):
        if isinstance(node, str) and path and isinstance(path[-1], str):
            if path[-1].lower() in URL_KEYS and node.startswith("http"):
                seen.setdefault(node, None)

    _walk(body, fn)
    for m in URL_RE.findall(text or ""):
        seen.setdefault(m.rstrip(".,;"), None)
    # cdn copies of the scraped page are not citations
    return [u for u in seen if "cdn.cloro.dev/results" not in u]


def _fanout(body) -> list[str]:
    out: list[str] = []

    def fn(node, path):
        if isinstance(node, list) and path and isinstance(path[-1], str) and path[-1] in FANOUT_KEYS:
            out.extend(q for q in node if isinstance(q, str))

    _walk(body, fn)
    return list(dict.fromkeys(out))


def normalize(result) -> dict:
    text = _longest_text(result)
    return {"text": text, "sources": _sources(result, text), "fanout": _fanout(result)}


# --------------------------------------------------------------------------- run
def _fill(template, values: dict):
    if isinstance(template, str):
        for k, v in values.items():
            template = template.replace("{" + k + "}", v)
        return template
    if isinstance(template, list):
        return [_fill(t, values) for t in template]
    if isinstance(template, dict):
        return {k: _fill(v, values) for k, v in template.items()}
    return template


def _call(endpoint: str, body, headers: list[str], timeout: int) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(body, f)
        path = f.name
    try:
        cmd = ["treg", "--json", "call", endpoint, "--method", "POST", "--data", "@" + path]
        for h in headers:
            cmd += ["--header", h]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = p.stdout.strip().splitlines()
        if not out:
            return {"error": (p.stderr or "no output").strip()[:500]}
        return json.loads(out[-1])
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"error": f"{type(e).__name__}: {e}"[:500]}
    finally:
        os.unlink(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--panel", default=".marketing/prompt-panel.json")
    ap.add_argument("--out", default=None, help="run dir (default .marketing/runs/<today>)")
    ap.add_argument("--engines", default="", help="comma list; default every enabled engine")
    ap.add_argument("--prompts", default="", help="comma list of prompt ids; default all")
    ap.add_argument("--limit", type=int, default=0, help="only the first N prompts")
    ap.add_argument("--samples", type=int, default=0, help="override samples per prompt")
    ap.add_argument("--max-usd", type=float, default=0.0, help="stop scheduling once spend reaches this")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    panel = json.loads(Path(a.panel).read_text())
    country = panel.get("country", "US")
    engines = {k: v for k, v in panel["engines"].items() if v.get("enabled", True)}
    if a.engines:
        want = set(a.engines.split(","))
        engines = {k: v for k, v in panel["engines"].items() if k in want}
    prompts = panel["prompts"]
    if a.prompts:
        want = set(a.prompts.split(","))
        prompts = [p for p in prompts if p["id"] in want]
    if a.limit:
        prompts = prompts[: a.limit]

    out = Path(a.out or Path(a.panel).parent / "runs" / dt.date.today().isoformat())
    (out / "raw").mkdir(parents=True, exist_ok=True)
    answers = out / "answers.jsonl"
    done = set()
    if answers.exists():
        for line in answers.read_text().splitlines():
            r = json.loads(line)
            if not r.get("error"):
                done.add((r["engine"], r["prompt_id"], r["sample"]))

    jobs = []
    for p in prompts:
        k = a.samples or p.get("samples", panel.get("samples", 1))
        for name, eng in engines.items():
            for s in range(k):
                if (name, p["id"], s) not in done:
                    jobs.append((name, eng, p, s))

    est = sum(float(e.get("usd_estimate", 0)) for _, e, _, _ in jobs)
    print(f"{len(jobs)} calls planned ({len(done)} already done) across {len(engines)} engines; "
          f"estimated ${est:.2f} (from usd_estimate in the panel; confirm with catalog_get)")
    if a.dry_run:
        for name, eng, p, s in jobs[:10]:
            print(f"  {name:16} {eng['endpoint']:60} {p['id']}#{s}")
        if len(jobs) > 10:
            print(f"  ... {len(jobs) - 10} more")
        return 0

    lock = threading.Lock()
    spent = [0.0]
    stop = threading.Event()

    def work(job):
        name, eng, p, s = job
        if stop.is_set():
            return None
        body = _fill(eng["body"], {"prompt": p["text"], "country": country, "country_lower": country.lower()})
        resp = _call(eng["endpoint"], body, eng.get("headers", []), a.timeout)
        meta = resp.get("_treg", {}) if isinstance(resp, dict) else {}
        cost = (meta.get("charged_micro") or 0) / 1e6
        status = meta.get("http_status")
        err = resp.get("error") if "result" not in resp else None
        if status and int(status) >= 400:
            err = f"http {status}: {json.dumps(resp.get('result'))[:300]}"
        rec = {
            "run_date": out.name, "engine": name, "endpoint": eng["endpoint"],
            "prompt_id": p["id"], "bucket": p.get("bucket"), "prompt": p["text"], "sample": s,
            "call_id": meta.get("call_id"), "cost_usd": round(cost, 6), "error": err,
        }
        if not err:
            rec.update(normalize(resp.get("result")))
        raw = out / "raw" / f"{name}__{p['id']}__{s}.json"
        raw.write_text(json.dumps(resp, ensure_ascii=False))
        with lock:
            spent[0] += cost
            with answers.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            flag = "ERR " + err[:80] if err else f"{len(rec.get('sources', []))} sources"
            print(f"[{spent[0]:7.3f}$] {name:16} {p['id']}#{s}  {flag}", flush=True)
            if a.max_usd and spent[0] >= a.max_usd:
                stop.set()
        return rec

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = [r for r in ex.map(work, jobs) if r]

    errs = [r for r in results if r["error"]]
    print(f"\ndone: {len(results) - len(errs)} answers, {len(errs)} errors, spent ${spent[0]:.4f} -> {answers}")
    if stop.is_set():
        print(f"stopped early at the --max-usd ceiling (${a.max_usd}); rerun to resume")
    if errs:
        print("errors by engine:", {e: sum(1 for r in errs if r['engine'] == e) for e in {r['engine'] for r in errs}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
