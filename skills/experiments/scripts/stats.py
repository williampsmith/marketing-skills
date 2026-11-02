#!/usr/bin/env python3
"""Experiment arithmetic the agent must not do in its head.

    python3 stats.py size --baseline 0.05 --mde 0.20 [--alpha 0.05 --power 0.8]
        visitors per arm to detect a relative lift of 20% on a 5% conversion rate
    python3 stats.py days --baseline 0.05 --mde 0.20 --daily 400 [--arms 2]
        how long that takes at 400 eligible visitors a day; "don't run it" when it's over 8 weeks
    python3 stats.py test --a 1000:50 --b 1000:68
        two-proportion z-test (two-sided): rates, absolute and relative lift, p-value, 95% interval
    python3 stats.py holdout --treated-before 0.10 --treated-after 0.25 --control-before 0.10 --control-after 0.12
        difference in differences for holdout bets

Output is JSON; `test` prints the --p-value to pass to `gtm.py bet close`. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from statistics import NormalDist

N = NormalDist()
MAX_WEEKS = 8


def size(baseline: float, mde: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Per-arm sample size for a two-sided two-proportion test (relative minimum detectable effect)."""
    if not 0 < baseline < 1:
        raise ValueError("baseline must be a rate between 0 and 1")
    if mde <= 0:
        raise ValueError("mde is a relative lift, e.g. 0.2 for +20%")
    p1, p2 = baseline, min(baseline * (1 + mde), 0.9999)
    za, zb = N.inv_cdf(1 - alpha / 2), N.inv_cdf(power)
    pbar = (p1 + p2) / 2
    n = ((za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / (p2 - p1) ** 2
    return math.ceil(n)


def days(baseline: float, mde: float, daily: float, arms: int = 2, alpha: float = 0.05, power: float = 0.8) -> dict:
    n = size(baseline, mde, alpha, power)
    d = math.ceil(n * arms / daily) if daily > 0 else None
    ok = d is not None and d <= MAX_WEEKS * 7
    return {"per_arm": n, "arms": arms, "days": d, "run_it": ok,
            "advice": "run it" if ok else
            f"over {MAX_WEEKS} weeks: test a bigger change, a higher-traffic page, or use a holdout or before/after bet"}


def ztest(a_n: int, a_x: int, b_n: int, b_x: int) -> dict:
    if min(a_n, b_n) <= 0 or not (0 <= a_x <= a_n and 0 <= b_x <= b_n):
        raise ValueError("counts must be n > 0 and 0 <= conversions <= n")
    pa, pb = a_x / a_n, b_x / b_n
    pool = (a_x + b_x) / (a_n + b_n)
    se0 = math.sqrt(pool * (1 - pool) * (1 / a_n + 1 / b_n))
    z = (pb - pa) / se0 if se0 else 0.0
    p = 2 * (1 - N.cdf(abs(z)))
    se = math.sqrt(pa * (1 - pa) / a_n + pb * (1 - pb) / b_n)
    lo, hi = (pb - pa) - 1.96 * se, (pb - pa) + 1.96 * se
    return {"a_rate": round(pa, 5), "b_rate": round(pb, 5), "abs_lift": round(pb - pa, 5),
            "rel_lift": round((pb - pa) / pa, 4) if pa else None, "z": round(z, 3), "p_value": round(p, 5),
            "ci95_abs": [round(lo, 5), round(hi, 5)], "significant": p < 0.05,
            "smallest_arm": min(a_n, b_n)}


def holdout(tb: float, ta: float, cb: float, ca: float) -> dict:
    return {"treated_change": round(ta - tb, 5), "control_change": round(ca - cb, 5),
            "effect": round((ta - tb) - (ca - cb), 5)}


def _arm(s: str) -> tuple[int, int]:
    n, _, x = s.partition(":")
    return int(n), int(x)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("size", "days"):
        p = sub.add_parser(name)
        p.add_argument("--baseline", type=float, required=True)
        p.add_argument("--mde", type=float, required=True, help="relative lift to detect, e.g. 0.2")
        p.add_argument("--alpha", type=float, default=0.05)
        p.add_argument("--power", type=float, default=0.8)
        if name == "days":
            p.add_argument("--daily", type=float, required=True, help="eligible visitors per day, all arms")
            p.add_argument("--arms", type=int, default=2)
    p = sub.add_parser("test")
    p.add_argument("--a", required=True, help="control as visitors:conversions")
    p.add_argument("--b", required=True, help="variant as visitors:conversions")
    p = sub.add_parser("holdout")
    for k in ("treated-before", "treated-after", "control-before", "control-after"):
        p.add_argument(f"--{k}", type=float, required=True)
    a = ap.parse_args()
    try:
        if a.cmd == "size":
            out = {"per_arm": size(a.baseline, a.mde, a.alpha, a.power)}
        elif a.cmd == "days":
            out = days(a.baseline, a.mde, a.daily, a.arms, a.alpha, a.power)
        elif a.cmd == "test":
            out = ztest(*_arm(a.a), *_arm(a.b))
        else:
            out = holdout(a.treated_before, a.treated_after, a.control_before, a.control_after)
    except ValueError as e:
        print(f"stats: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
