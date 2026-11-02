#!/usr/bin/env python3
"""Flag claim-like sentences in marketing copy and check each against the claims ledger.

    python3 claims_guard.py page.md                       # human report; exit 1 if anything fails
    python3 claims_guard.py page.html --json              # machine-readable
    cat draft.txt | python3 claims_guard.py - --competitor "Adobe Acrobat"
    python3 claims_guard.py page.md --claims path/to/claims.md --context path/to/product-context.md

What it flags, per sentence:
  number      digits or percentages (years on their own are ignored)
  risky       superlatives and absolutes ("fastest", "only", "100%", "secure", "free", ...)
  comparison  a competitor named next to a comparative word ("than", "unlike", "vs", ...)
  banned      a phrase from the AI-tells ban list (fails regardless of the ledger)
Plus `overused`: capped phrases used more often than allowed (reported, does not fail).

Each number/risky/comparison sentence is matched against the OK rows of the claims ledger
(`## OK to claim` table). It counts as `covered` when the row shares most of its key words with
the sentence AND every number and risky term in the sentence also appears in that row. Otherwise
it is `unsupported`.

Limits: this is a deterministic net for review, not proof. It can't judge meaning, misses claims
phrased without numbers or risky words, and word overlap can match a row that says something
different. A human or the writing skill still reads every flagged sentence.

Defaults: --claims <state>/claims.md, --context <state>/product-context.md (competitors are read
from its "Alternatives" line). Exit 0 clean, 1 if any sentence is unsupported or banned, 2 on bad input.
Stdlib only; Python 3.9+.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
from marketing_state import state_root  # noqa: E402  (the plugin's shared state-store resolver)

LISTS = Path(__file__).resolve().parents[1] / "references" / "ai-tells.json"
STOP = set("""a an and are as at be been but by can do does for from has have how if in into is it its
of on or our so than that the their them then there these they this to us was we were what when which
who will with without you your yours not no yes all any each every more most less very just also""".split())
YEAR = re.compile(r"^(19|20)\d\d$")
NUM = re.compile(r"\d[\d,.]*\s*%?|%")


def load_lists() -> dict:
    return json.loads(LISTS.read_text())


def plain_text(raw: str) -> str:
    raw = re.sub(r"```.*?```", " ", raw, flags=re.S)                      # code blocks
    raw = re.sub(r"<(script|style)\b.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", "\n", raw)                                   # html tags
    raw = html.unescape(raw)
    raw = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", raw)                       # md images
    raw = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", raw)                    # md links → text
    raw = re.sub(r"^\s{0,3}(#{1,6}|[-*+]|\d+\.|>)\s+", "", raw, flags=re.M)  # headings, bullets, quotes
    raw = re.sub(r"[*_`|]", " ", raw)
    return raw


def sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        for s in re.split(r"(?<=[.!?])\s+", line):
            s = " ".join(s.split())
            if len(s) > 2:
                out.append(s)
    return out


def _has(phrase: str, text: str) -> bool:
    p = re.escape(phrase.lower())
    left = r"(?<![\w#])" if phrase[0].isalnum() or phrase[0] == "#" else ""
    right = r"(?!\w)" if phrase[-1].isalnum() else ""
    return re.search(left + p + right, text.lower()) is not None


def _count(phrase: str, text: str) -> int:
    p = re.escape(phrase.lower())
    return len(re.findall(r"(?<!\w)" + p + r"(?!\w)", text.lower()))


def stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def keywords(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z0-9#%]+", text.lower()) if len(w) > 2 and w not in STOP}


def numbers(text: str) -> list[str]:
    found = []
    for m in NUM.finditer(text):
        n = m.group(0).strip().rstrip(".,")
        bare = n.rstrip("%").strip()
        if not bare and n == "%":
            continue
        if YEAR.match(bare) and "%" not in n:
            continue
        found.append(n.replace(" ", ""))
    return found


def parse_ledger(path: Path) -> list[dict]:
    """OK rows of the claims ledger: [{claim, evidence, notes, text}]."""
    if not path.exists():
        return []
    rows, in_ok = [], False
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            in_ok = line.lower().startswith("## ok")
            continue
        if not in_ok or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= set("-: ") or cells[0].lower().startswith("claim"):
            continue
        cells += [""] * (3 - len(cells))
        rows.append({"claim": cells[0], "evidence": cells[1], "notes": cells[2],
                     "text": " ".join(cells[:3]).lower()})
    return rows


def competitors_from_context(path: Path) -> list[str]:
    if not path.exists():
        return []
    for line in path.read_text().splitlines():
        m = re.match(r"\s*[-*]?\s*\**alternatives:?\**:?\s*(.+)", line, flags=re.I)
        if m:
            names = [n.strip(" .*") for n in re.split(r",|;", m.group(1))]
            return [n for n in names if n and n.lower() not in ("do nothing", "nothing") and not n.startswith("<")]
    return []


def _in_row(term: str, text: str) -> bool:
    """Numbers must match as whole numbers ("10" is not in "100"); words as substrings."""
    t = term.lower()
    if t[:1].isdigit():
        return re.search(r"(?<![\d.,])" + re.escape(t) + r"(?![\d])", text) is not None
    return t in text


def match_row(sentence: str, rows: list[dict], must: list[str]) -> dict | None:
    sk = keywords(sentence)
    best, best_score = None, 0.0
    for r in rows:
        rk = keywords(r["claim"])
        if not rk:
            continue
        overlap = len(sk & rk) / min(len(rk), max(len(sk), 1))
        if overlap < 0.5:
            continue
        if not all(_in_row(term, r["text"]) for term in must):
            continue
        if overlap > best_score:
            best, best_score = r, overlap
    return best


def check(text: str, rows: list[dict], competitors: list[str], lists: dict) -> dict:
    plain = plain_text(text)
    findings = []
    for s in sentences(plain):
        kinds, must = [], []
        nums = numbers(s)
        if nums:
            kinds.append("number")
            must += nums
        risky = [t for t in lists["risky_terms"] if _has(t, s)]
        if risky:
            kinds.append("risky")
            must += risky
        named = [c for c in competitors if _has(c, s)]
        if named and any(_has(m, s) for m in lists["comparative_markers"]):
            kinds.append("comparison")
            must += named
        banned = [p for p in lists["ban"] if _has(p, s)]
        if not kinds and not banned:
            continue
        f = {"sentence": s, "kinds": kinds + (["banned"] if banned else []), "terms": sorted(set(must)),
             "banned": banned}
        if banned:
            f["status"] = "banned"
        if kinds:
            row = match_row(s, rows, must)
            if row:
                f.setdefault("status", "covered")
                f["row"] = row["claim"]
                f["qualifier"] = row["notes"]
            else:
                f["status"] = "unsupported" if not banned else "banned"
        findings.append(f)
    counts = {p: _count(p, plain) for p in lists["cap"]}
    overused = [{"phrase": p, "count": counts[p], "max": cap} for p, cap in lists["cap"].items() if counts[p] > cap]
    unsupported = sum(1 for f in findings if f["status"] == "unsupported")
    banned = sum(1 for f in findings if f["status"] == "banned")
    return {"findings": findings, "overused": overused, "ledger_rows": len(rows),
            "summary": {"flagged": len(findings), "covered": sum(1 for f in findings if f["status"] == "covered"),
                        "unsupported": unsupported, "banned": banned}, "ok": unsupported == 0 and banned == 0}


def report(res: dict, claims_path: Path) -> str:
    L = []
    if not res["ledger_rows"]:
        L.append(f"note: no OK rows found in {claims_path}; every claim-like sentence is unsupported")
    for f in res["findings"]:
        tag = f["status"].upper()
        L.append(f"[{tag}] {f['sentence']}")
        if f.get("row"):
            L.append(f"    ledger: {f['row']}" + (f"  (qualifier: {f['qualifier']})" if f.get("qualifier") else ""))
        if f["terms"]:
            L.append(f"    terms: {', '.join(f['terms'])}")
        if f["banned"]:
            L.append(f"    banned phrase: {', '.join(f['banned'])}")
    for o in res["overused"]:
        L.append(f"[OVERUSED] \"{o['phrase']}\" ×{o['count']} (max {o['max']})")
    s = res["summary"]
    L.append(f"{s['flagged']} flagged: {s['covered']} covered, {s['unsupported']} unsupported, {s['banned']} banned")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="Markdown, HTML or text file; - for stdin")
    ap.add_argument("--claims", help="claims ledger (default <state>/claims.md)")
    ap.add_argument("--context", help="product context for competitor names (default <state>/product-context.md)")
    ap.add_argument("--competitor", action="append", default=[], help="competitor name (repeatable)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.file == "-":
        text = sys.stdin.read()
    else:
        p = Path(a.file)
        if not p.exists():
            print(f"no such file: {p}", file=sys.stderr)
            return 2
        text = p.read_text()
    root = None
    if not a.claims or not a.context:
        root = state_root(create=False)
    claims = Path(a.claims) if a.claims else root / "claims.md"
    context = Path(a.context) if a.context else root / "product-context.md"
    comps = list(dict.fromkeys(a.competitor + competitors_from_context(context)))
    res = check(text, parse_ledger(claims), comps, load_lists())
    res["claims_path"] = str(claims)
    res["competitors"] = comps
    print(json.dumps(res, indent=2) if a.json else report(res, claims))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
