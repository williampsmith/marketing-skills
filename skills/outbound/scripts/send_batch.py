#!/usr/bin/env python3
"""Send an approved batch of drafted emails from the dedicated sending inbox. Never sends a draft
a human hasn't approved, never past the channel's caps, never to a suppressed address.

    python3 send_batch.py BATCH_ID [--dry-run]

A batch is <state>/sends/<BATCH_ID>/drafts.jsonl, one draft per line:
    {"to": "name@company.com", "subject": "...", "body": "...", "key": "company.com",
     "channel": "outbound" | "citation_outreach" | "creators", "followup_of": null}
Approval comes from a human, applied with `gtm.py approve BATCH_ID --count N` (only the first N
drafts in file order are approved). Before each message this script asks gtm.py whether sending is
allowed (`send_allowed`: kill switch, authority level, approval, daily cap) and whether the key is
inside its cooldown; it checks <state>/suppression.csv (email or domain per line); it appends the
sender's postal address and an opt-out line (CAN-SPAM); then it logs every send with
`gtm.record_send` and the key's cooldown.

SMTP settings come only from the environment: SMTP_HOST, SMTP_PORT (465 = SSL, else STARTTLS),
SMTP_USER, SMTP_PASSWORD, SMTP_FROM (an address on the dedicated sending domain).
The postal address and opt-out text come from gtm.json "sender": {"address": "...", "opt_out": "..."}.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

COOLDOWN_JOB = "outbound_send"


def smtp_connect():
    """The only network call (tests replace it). Returns an object with send_message() and quit()."""
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    ctx = ssl.create_default_context()
    if port == 465:
        conn = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30)
    else:
        conn = smtplib.SMTP(host, port, timeout=30)
        conn.starttls(context=ctx)
    conn.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
    return conn


def suppressed() -> set[str]:
    p = gtm.R() / "suppression.csv"
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text().splitlines():
        v = line.split(",")[0].strip().lower()
        if v and not v.startswith("#") and v != "email":
            out.add(v)
    return out


def is_suppressed(addr: str, sup: set[str]) -> bool:
    a = addr.strip().lower()
    return a in sup or a.rsplit("@", 1)[-1] in sup


def footer(sender: dict) -> str:
    return (f"\n\n--\n{sender['opt_out']}\n{sender['address']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--dry-run", action="store_true", help="check everything, send nothing")
    a = ap.parse_args()
    with gtm.locked():  # two runs of one batch must not both send it
        return run(a)


def run(a) -> int:
    s = gtm.load_state()
    sender = s.get("sender") or {}
    if not sender.get("address") or not sender.get("opt_out"):
        print("gtm.json needs sender.address (a postal address) and sender.opt_out before anything is sent",
              file=sys.stderr)
        return 1
    batch_dir = gtm.R() / "sends" / a.batch
    drafts = gtm.read_jsonl(batch_dir / "drafts.jsonl")
    if not drafts:
        print(f"no drafts in {batch_dir}", file=sys.stderr)
        return 1
    channels = {d.get("channel", "outbound") for d in drafts}
    if len(channels) != 1:
        print(f"a batch is one channel; found {sorted(channels)}", file=sys.stderr)
        return 1
    channel = channels.pop()
    approved = gtm.approved_count(a.batch)
    already = {r["to"] for r in gtm.read_jsonl(batch_dir / "sent.jsonl")}
    sup = suppressed()
    plan, skipped = [], []
    for i, d in enumerate(drafts):
        why = None
        if i >= approved:
            why = "not approved"
        elif d["to"] in already:
            why = "already sent"
        elif is_suppressed(d["to"], sup):
            why = "suppressed"
        else:
            cd = gtm.in_cooldown(s, COOLDOWN_JOB, d.get("key") or d["to"],
                                 days=int(gtm.authority(s, channel)["cooldown_days"]))
            if cd and not d.get("followup_of"):
                why = cd
        if why:
            skipped.append({"to_domain": d["to"].rsplit("@", 1)[-1], "why": why})
        else:
            plan.append(d)
    allowed, reason = gtm.send_allowed(s, channel, len(plan), a.batch)
    if not allowed:
        print(json.dumps({"sent": 0, "refused": reason, "skipped": skipped}, indent=2))
        return 3
    if a.dry_run or not plan:
        print(json.dumps({"would_send": len(plan), "channel": channel, "skipped": skipped}, indent=2))
        return 0
    conn = smtp_connect()
    sent = 0
    try:
        for d in plan:
            msg = EmailMessage()
            msg["From"] = os.environ["SMTP_FROM"]
            msg["To"] = d["to"]
            msg["Subject"] = d["subject"]
            msg["Message-ID"] = make_msgid(domain=os.environ["SMTP_FROM"].rsplit("@", 1)[-1])
            msg["List-Unsubscribe"] = f"<mailto:{os.environ['SMTP_FROM']}?subject=unsubscribe>"
            msg.set_content(d["body"].rstrip() + footer(sender))
            conn.send_message(msg)
            sent += 1
            # log without the address in the shared logs: the batch folder keeps it, state does not
            gtm.append_jsonl(batch_dir / "sent.jsonl", {"to": d["to"], "date": gtm.today().isoformat()})
            gtm.record_send(channel, 1, a.batch, key=d.get("key") or d["to"], cooldown_job=COOLDOWN_JOB)
    finally:
        conn.quit()
    print(json.dumps({"sent": sent, "channel": channel, "skipped": skipped}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
