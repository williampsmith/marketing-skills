#!/usr/bin/env python3
"""Turn customer-research evidence into attention weights for the GTM profile.

    python3 attention.py <state>/research/attention-<date>.json [--apply]

Evidence file (written by the agent while researching; one entry per place it searched):
    {"date": "2026-11-12", "icp": "compliance leads at mid-size banks",
     "sources": {
        "reddit":        {"sampled": 40, "relevant": 9, "examples": ["https://…"]},
        "linkedin":      {"sampled": 40, "relevant": 22, "examples": ["https://…"]},
        "tiktok":        {"sampled": 30, "relevant": 0, "examples": []},
        ...}}
`sampled` is how many recent results for the ICP's problem queries the agent read; `relevant` is how
many were the ICP discussing the problem, alternatives or a purchase (not vendors, not unrelated).

Each source maps to a channel in channel-fit.json. A channel's weight is its best source's relevant
share divided by the best share of any channel, floored at 0.05; channels with fewer than 15 sampled
results are reported as unmeasured and left alone. AI search and the product's own site aren't
measured here (they stay 1.0). Prints the proposal and the `gtm.py profile` command; --apply runs it,
which unconfirms the profile until the human confirms again. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

SOURCE_CHANNEL = {
    "reddit": "review_communities", "forums": "review_communities", "stackoverflow": "review_communities",
    "hackernews": "review_communities", "g2": "review_communities", "capterra": "review_communities",
    "linkedin": "linkedin_organic",
    "tiktok": "short_video", "instagram": "short_video", "youtube_shorts": "short_video",
    "youtube": "long_video",
    "creators": "creators", "newsletters": "creators", "podcasts": "creators",
    "press": "pr",
    "x": "linkedin_organic",  # founder-led social; the matrix has no separate X channel
    "search": "seo_content",
}
MIN_SAMPLED = 15
FLOOR = 0.05


def weights(evidence: dict) -> dict:
    best: dict = {}
    unmeasured: dict = {}
    for src, e in (evidence.get("sources") or {}).items():
        ch = SOURCE_CHANNEL.get(src)
        if ch is None:
            unmeasured[src] = "unknown source (not mapped to a channel)"
            continue
        try:
            n, r = int(e.get("sampled", 0)), int(e.get("relevant", 0))
        except (TypeError, ValueError, AttributeError):
            unmeasured[src] = "sampled and relevant must be whole numbers"
            continue
        if r < 0 or r > n:
            unmeasured[src] = f"relevant ({r}) must be between 0 and sampled ({n})"
            continue
        if n < MIN_SAMPLED:
            unmeasured.setdefault(ch, f"only {n} results sampled on {src}")
            continue
        share = r / n
        if share >= best.get(ch, (-1, ""))[0]:
            best[ch] = (share, src)
    top = max((v[0] for v in best.values()), default=0)
    out = {}
    for ch, (share, src) in best.items():
        w = max(FLOOR, round(share / top, 2)) if top > 0 else FLOOR
        out[ch] = {"weight": w, "relevant_share": round(share, 3), "from": src}
        unmeasured.pop(ch, None)
    return {"weights": out, "unmeasured": unmeasured}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("evidence")
    ap.add_argument("--apply", action="store_true", help="write the weights (unconfirms the profile)")
    a = ap.parse_args()
    ev = json.loads(Path(a.evidence).read_text())
    res = weights(ev)
    channels = gtm.channel_fit_ref()["channels"]
    res["command"] = "gtm.py profile " + " ".join(f"--attention {c}={v['weight']}" for c, v in sorted(res["weights"].items()))
    if a.apply and res["weights"]:
        with gtm.locked():
            s = gtm.load_state()
            for ch, v in res["weights"].items():
                if ch in channels:
                    s["profile"].setdefault("attention", {})[ch] = v["weight"]
            s["profile"]["confirmed"] = False
            s["profile"]["attention_source"] = {"file": str(a.evidence), "date": ev.get("date")}
            gtm.save_state(s)
        res["applied"] = True
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
