#!/usr/bin/env python3
"""Send an approved batch of drafted emails from the dedicated sending inbox. Never sends a draft
a human hasn't approved (or that changed since), never past the channel's daily cap, never to a
suppressed address, never twice.

    python3 send_batch.py BATCH_ID [--dry-run]

A batch is <state>/sends/<BATCH_ID>/drafts.jsonl, one draft per line:
    {"to": "name@company.com", "subject": "...", "body": "...", "key": "company.com",
     "channel": "outbound" | "citation_outreach" | "creators" | "lifecycle_email", "followup_of": null}
`to` is one bare address. `key` (default: the address's domain) is what the cooldown counts.

Under bounded authority (granted by a human after the promotion criteria are met), drafts that carry
an approved `template` and `segment` go out without per-batch approval; others are skipped.
Otherwise approval comes from a human, applied with `gtm.py approve BATCH_ID --count N --quote "<their reply>"`:
it pins the first N drafts by content hash, so editing, reordering or adding drafts afterwards
unapproves them. Before each message this script checks the kill switch; for the batch it checks
the channel's authority and daily cap (sending as many as the cap allows today and leaving the rest
for tomorrow), <state>/suppression.csv (an email or a domain per row; subdomains match), the
key's cooldown on the channel, duplicates within the batch, and earlier sends. A follow-up
(`followup_of` set) skips the cooldown only when the same address got an earlier message, it has
had fewer than 2 follow-ups, and it isn't in <state>/replied.csv.

Every message gets a Date, a Message-ID, List-Unsubscribe, the sender's postal address and an opt-out
line (CAN-SPAM). A permanent rejection (5xx) is logged as a bounce and suppressed; anything else stops
the run. Each send is logged as "attempt" before and "sent" after, so a crash mid-send leaves an
attempt that is held for a human instead of being resent.

Refuses on the repo backend (contacts must not land in the product repo). On the git backend it
pulls first and pushes right after sending, so an ephemeral host can't forget what it sent.

SMTP settings come only from the environment: SMTP_HOST, SMTP_PORT (465 = SSL, else STARTTLS),
SMTP_USER, SMTP_PASSWORD, SMTP_FROM (an address on the dedicated sending domain).
The postal address and opt-out text come from gtm.json "sender": {"address": "...", "opt_out": "..."}.
Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid, parseaddr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402
import marketing_state as ms  # noqa: E402

MAX_FOLLOWUPS = 2


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


def one_address(to: str) -> str | None:
    """The single bare address in `to`, lower-cased, or None if it isn't exactly one."""
    if not isinstance(to, str) or "\n" in to or "\r" in to:
        return None
    addrs = [a for _, a in getaddresses([to]) if a]
    if len(addrs) != 1 or addrs[0].count("@") != 1:
        return None
    _, addr = parseaddr(to)
    return addr.strip().lower() if addr.strip() == to.strip() else None  # no display names


def _rows(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="") as f:
        return {row[0].strip().lower() for row in csv.reader(f)
                if row and row[0].strip() and not row[0].startswith("#") and row[0].strip().lower() != "email"}


def suppressed() -> set[str]:
    return _rows(gtm.R() / "suppression.csv")


def is_suppressed(addr: str, sup: set[str]) -> bool:
    if addr in sup:
        return True
    parts = addr.rsplit("@", 1)[-1].split(".")
    return any(".".join(parts[i:]) in sup for i in range(len(parts) - 1))


def all_sent() -> list[dict]:
    out = []
    for f in (gtm.R() / "sends").glob("*/sent.jsonl"):
        out += gtm.read_jsonl(f)
    return out


def footer(sender: dict) -> str:
    return f"\n\n--\n{sender['opt_out']}\n{sender['address']}"


def build(d: dict, addr: str, sender: dict) -> EmailMessage:
    from_addr = parseaddr(os.environ["SMTP_FROM"])[1]
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = addr
    msg["Subject"] = d["subject"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_addr.rsplit("@", 1)[-1])
    msg["List-Unsubscribe"] = f"<mailto:{from_addr}?subject=unsubscribe>"
    msg.set_content(d["body"].rstrip() + footer(sender))
    return msg


def plan_batch(s: dict, drafts: list[dict], batch: str, channel: str) -> tuple[list, list]:
    level = gtm.authority(s, channel)["level"]
    approved = gtm.approved_hashes(batch)
    cooldown = int(gtm.authority(s, channel)["cooldown_days"])
    history = all_sent()
    done = {r["to"] for r in history if r.get("status") in ("sent", "bounced")}
    unresolved = {r["to"] for r in history if r.get("status") == "attempt"} - done
    first_touched = {r["to"] for r in history if r.get("status") == "sent" and not r.get("followup")}
    followups: dict = {}
    for r in history:
        if r.get("status") == "sent" and r.get("followup"):
            followups[r["to"]] = followups.get(r["to"], 0) + 1
    replied = _rows(gtm.R() / "replied.csv")
    sup = suppressed()
    plan, skipped, planned_addrs, planned_keys = [], [], set(), set()
    for i, d in enumerate(drafts):
        addr = one_address(d.get("to", ""))
        key = (d.get("key") or (addr.rsplit("@", 1)[-1] if addr else "")).lower()
        follow = bool(d.get("followup_of"))
        why = None
        if addr is None:
            why = "`to` must be exactly one bare address"
        elif level == "approve_to_send" and gtm.draft_hash(d) not in approved:
            why = "not approved (or changed since approval)"
        elif level == "bounded" and gtm.bounded_draft_ok(s, channel, d):
            why = gtm.bounded_draft_ok(s, channel, d)
        elif addr in unresolved:
            why = "an earlier attempt didn't finish; a human must check whether it went out"
        elif is_suppressed(addr, sup):
            why = "suppressed"
        elif addr in planned_addrs or key in planned_keys:
            why = "duplicate in this batch"
        elif follow:
            if addr not in first_touched:
                why = "follow-up without an earlier message to this address"
            elif followups.get(addr, 0) >= MAX_FOLLOWUPS:
                why = f"already had {MAX_FOLLOWUPS} follow-ups"
            elif addr in replied or addr.rsplit("@", 1)[-1] in replied:
                why = "replied: a human takes it from here"
        elif addr in done:
            why = "already sent"
        else:
            why = gtm.in_cooldown(s, f"send:{channel}", key, days=cooldown)
        if why:
            skipped.append({"draft": i + 1, "to_domain": (addr or "?").rsplit("@", 1)[-1], "why": why})
        else:
            plan.append((d, addr, key))
            planned_addrs.add(addr)
            planned_keys.add(key)
    return plan, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch")
    ap.add_argument("--dry-run", action="store_true", help="check everything, send nothing")
    a = ap.parse_args()
    st = ms.resolve()
    if st.backend == "repo":
        print("refusing to send from the repo backend: contacts would be committed to the product repo. "
              "Migrate the store first (`gtm.py migrate --to <dir>`).", file=sys.stderr)
        return 1
    if st.backend == "git" and not a.dry_run:
        try:
            ms.pull(st)
        except RuntimeError as e:
            print(f"refusing to send: the state repo didn't pull cleanly ({e})", file=sys.stderr)
            return 1
    with gtm.locked():  # two runs of one batch on this host must not both send it
        code = run(a)
    if st.backend == "git" and not a.dry_run:
        try:
            ms.push(st, f"marketing: sent batch {a.batch}")
        except RuntimeError as e:
            print(f"WARNING: sent, but the state repo push failed ({e}); push it before any other run",
                  file=sys.stderr)
            return 1
    return code


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
    plan, skipped = plan_batch(s, drafts, a.batch, channel)
    capacity, why = gtm.send_capacity(s, channel)
    if capacity <= 0:
        print(json.dumps({"sent": 0, "refused": why, "skipped": skipped}, indent=2))
        return 3
    later = plan[capacity:]
    plan = plan[:capacity]
    if a.dry_run or not plan:
        print(json.dumps({"would_send": len(plan), "left_for_later": len(later), "channel": channel,
                          "skipped": skipped}, indent=2))
        return 0
    log = batch_dir / "sent.jsonl"
    conn = smtp_connect()
    sent, bounced, stopped = 0, 0, None
    try:
        for d, addr, key in plan:
            if gtm.paused():
                stopped = "paused mid-batch"
                break
            msg = build(d, addr, sender)
            follow = bool(d.get("followup_of"))
            today = gtm.today().isoformat()
            gtm.append_jsonl(log, {"to": addr, "date": today, "status": "attempt", "followup": follow})
            try:
                conn.send_message(msg)
            except smtplib.SMTPRecipientsRefused as e:
                code = next(iter(e.recipients.values()))[0] if e.recipients else 550
                gtm.append_jsonl(log, {"to": addr, "date": today, "status": "bounced", "code": code})
                with (gtm.R() / "suppression.csv").open("a") as f:
                    f.write(f"{addr},bounced {code}\n")
                bounced += 1
                continue
            except smtplib.SMTPResponseException as e:
                if 500 <= e.smtp_code < 600:
                    gtm.append_jsonl(log, {"to": addr, "date": today, "status": "bounced", "code": e.smtp_code})
                    with (gtm.R() / "suppression.csv").open("a") as f:
                        f.write(f"{addr},bounced {e.smtp_code}\n")
                    bounced += 1
                    continue
                stopped = f"SMTP {e.smtp_code}; stopped, the attempt is held for a human"
                break
            except (smtplib.SMTPException, OSError) as e:
                stopped = f"{type(e).__name__}; stopped, the attempt is held for a human"
                break
            gtm.append_jsonl(log, {"to": addr, "date": today, "status": "sent", "followup": follow})
            gtm.record_send(channel, 1, a.batch, key=key)
            sent += 1
    finally:
        try:
            conn.quit()
        except Exception:  # noqa: BLE001 - a dropped connection on quit doesn't change what was sent
            pass
    print(json.dumps({"sent": sent, "bounced": bounced, "left_for_later": len(later), "channel": channel,
                      "stopped": stopped, "skipped": skipped}, indent=2))
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
