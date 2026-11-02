"""Tests for approve-to-send: authority, hashed approvals, caps, suppression, cooldowns, follow-ups,
bounces and the kill switch. SMTP is replaced; nothing is sent. Run: python3 -m unittest discover tests"""
import json
import os
import smtplib

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
sender = load("skills/outbound/scripts/send_batch.py", "send_batch")


class FakeSMTP:
    def __init__(self, refuse=(), fail_at=None):
        self.messages, self.refuse, self.fail_at = [], set(refuse), fail_at

    def send_message(self, msg):
        if self.fail_at is not None and len(self.messages) == self.fail_at:
            raise smtplib.SMTPServerDisconnected("dropped")
        if msg["To"] in self.refuse:
            raise smtplib.SMTPRecipientsRefused({msg["To"]: (550, b"no such user")})
        self.messages.append(msg)

    def quit(self):
        raise smtplib.SMTPServerDisconnected("already gone")  # must not hide anything


class SendTest(StoreCase):
    module = sender

    def setUp(self):
        super().setUp()
        self.saved = {k: os.environ.get(k) for k in ("SMTP_FROM", "MARKETING_UNATTENDED")}
        os.environ["SMTP_FROM"] = "Acme <hello@tryacme.com>"
        os.environ.pop("MARKETING_UNATTENDED", None)
        self.smtp = FakeSMTP()
        self.real = sender.smtp_connect
        sender.smtp_connect = lambda: self.smtp
        self.run_cli("init", module=gtm)
        s = json.loads((gtm.R() / "gtm.json").read_text())
        s["sender"] = {"address": "Acme Inc, 1 Main St, Springfield", "opt_out": "Reply 'stop' and we won't write again."}
        (gtm.R() / "gtm.json").write_text(json.dumps(s))

    def tearDown(self):
        sender.smtp_connect = self.real
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        super().tearDown()

    def use(self, smtp):
        self.smtp = smtp
        sender.smtp_connect = lambda: self.smtp

    def batch(self, n=3, channel="outbound", name="b1", rows=None):
        d = gtm.R() / "sends" / name
        d.mkdir(parents=True, exist_ok=True)
        rows = rows or [{"to": f"p{i}@co{i}.com", "subject": f"Hi {i}", "body": "Short note.", "key": f"co{i}.com",
                         "channel": channel} for i in range(n)]
        gtm.write_jsonl(d / "drafts.jsonl", rows)
        return name

    def grant(self, channel="outbound", cap="20"):
        code = self.run_cli("authority", "grant", channel, "--level", "approve_to_send", "--daily-cap", cap,
                            "--quote", "yes, let it send approved outbound", module=gtm)[0]
        self.assertEqual(code, 0, self.last_err)

    def approve(self, b, n):
        self.assertEqual(self.run_cli("approve", b, "--count", str(n), "--quote", f"approve {b}", module=gtm)[0], 0,
                         self.last_err)

    def send(self, b, *extra):
        code, out = self.run_cli(b, *extra)
        return code, (json.loads(out) if out.strip().startswith("{") else {})

    def test_drafts_only_by_default(self):
        b = self.batch()
        self.approve(b, 3)
        code, out = self.send(b)
        self.assertEqual(code, 3)
        self.assertIn("draft", out["refused"])
        self.assertEqual(self.smtp.messages, [])

    def test_sends_only_approved_drafts_with_the_required_headers(self):
        self.grant()
        b = self.batch(3)
        self.approve(b, 2)
        code, out = self.send(b)
        self.assertEqual(code, 0, self.last_err)
        self.assertEqual(len(self.smtp.messages), 2)
        m = self.smtp.messages[0]
        self.assertIn("1 Main St", m.get_content())
        self.assertEqual(m["List-Unsubscribe"], "<mailto:hello@tryacme.com?subject=unsubscribe>")
        self.assertTrue(m["Date"] and m["Message-ID"].endswith("@tryacme.com>"))
        self.assertEqual(out["skipped"][0]["why"], "not approved (or changed since approval)")
        self.send(b)
        self.assertEqual(len(self.smtp.messages), 2)                  # nothing is sent twice

    def test_editing_a_draft_after_approval_unapproves_it(self):
        self.grant()
        b = self.batch(1)
        self.approve(b, 1)
        self.batch(rows=[{"to": "ceo@bigco.com", "subject": "NOT approved", "body": "x", "key": "bigco.com",
                          "channel": "outbound"}], name=b)
        code, out = self.send(b)
        self.assertEqual(self.smtp.messages, [])
        self.assertIn("changed since approval", out["skipped"][0]["why"])

    def test_recipients_must_be_one_bare_address(self):
        self.grant()
        (gtm.R() / "suppression.csv").write_text('email,reason\n"acme.com",asked\n')
        rows = [{"to": "Jane <jane@acme.com>", "subject": "s", "body": "b", "channel": "outbound"},
                {"to": "x@secret.com, y@other.com", "subject": "s", "body": "b", "channel": "outbound"},
                {"to": "JANE@mail.acme.com", "subject": "s", "body": "b", "channel": "outbound"}]
        b = self.batch(rows=rows)
        self.approve(b, 3)
        code, out = self.send(b)
        self.assertEqual(self.smtp.messages, [])
        whys = [x["why"] for x in out["skipped"]]
        self.assertEqual(whys[:2], ["`to` must be exactly one bare address"] * 2)
        self.assertEqual(whys[2], "suppressed")                        # subdomain, quoted csv, case

    def test_duplicates_in_a_batch_and_cooldown_across_batches(self):
        self.grant()
        rows = [{"to": "a@x.com", "subject": "s", "body": "b", "channel": "outbound"},
                {"to": "A@x.com", "subject": "s2", "body": "b", "channel": "outbound"},
                {"to": "b@x.com", "subject": "s3", "body": "b", "channel": "outbound"}]
        b = self.batch(rows=rows)
        self.approve(b, 3)
        self.send(b)
        self.assertEqual(len(self.smtp.messages), 1)
        b2 = self.batch(rows=[{"to": "c@x.com", "subject": "s", "body": "b", "channel": "outbound"}], name="b2")
        self.approve(b2, 1)
        out = self.send(b2)[1]
        self.assertEqual(len(self.smtp.messages), 1)
        self.assertIn("cools down", out["skipped"][0]["why"])
        state = (gtm.R() / "gtm.json").read_text() + (gtm.R() / "sends.jsonl").read_text()
        self.assertNotIn("a@x.com", state)                             # keys are domains, never addresses

    def test_followups_need_a_real_first_touch_and_stop_on_reply(self):
        self.grant()
        b = self.batch(rows=[{"to": "a@x.com", "subject": "s", "body": "b", "channel": "outbound"}])
        self.approve(b, 1)
        self.send(b)
        rows = [{"to": "a@x.com", "subject": "f1", "body": "b", "channel": "outbound", "followup_of": b},
                {"to": "z@y.com", "subject": "f1", "body": "b", "channel": "outbound", "followup_of": "anything"}]
        b2 = self.batch(rows=rows, name="f")
        self.approve(b2, 2)
        out = self.send(b2)[1]
        self.assertEqual(len(self.smtp.messages), 2)                   # the real follow-up went
        self.assertIn("without an earlier message", out["skipped"][0]["why"])
        (gtm.R() / "replied.csv").write_text("a@x.com\n")
        b3 = self.batch(rows=[{"to": "a@x.com", "subject": "f2", "body": "b", "channel": "outbound",
                               "followup_of": b}], name="f2")
        self.approve(b3, 1)
        self.assertIn("replied", self.send(b3)[1]["skipped"][0]["why"])

    def test_cap_sends_what_fits_and_leaves_the_rest(self):
        self.grant(cap="2")
        b = self.batch(3)
        self.approve(b, 3)
        code, out = self.send(b)
        self.assertEqual((code, out["sent"], out["left_for_later"]), (0, 2, 1))
        code, out = self.send(b)
        self.assertEqual(code, 3)                                      # today's cap is used up
        self.assertIn("daily cap", out["refused"])

    def test_bounce_is_suppressed_and_a_drop_holds_the_attempt(self):
        self.grant()
        self.use(FakeSMTP(refuse={"p1@co1.com"}))
        b = self.batch(3)
        self.approve(b, 3)
        code, out = self.send(b)
        self.assertEqual((code, out["sent"], out["bounced"]), (0, 2, 1))
        self.assertIn("p1@co1.com", (gtm.R() / "suppression.csv").read_text())
        self.use(FakeSMTP(fail_at=0))
        b2 = self.batch(rows=[{"to": "q@zz.com", "subject": "s", "body": "b", "channel": "outbound"}], name="b2")
        self.approve(b2, 1)
        code, out = self.send(b2)
        self.assertEqual(code, 1)
        self.assertIn("held for a human", out["stopped"])
        self.use(FakeSMTP())
        out = self.send(b2)[1]
        self.assertEqual(self.smtp.messages, [])                       # never resent blindly
        self.assertIn("earlier attempt", out["skipped"][0]["why"])

    def test_kill_switch_unattended_and_backend_guards(self):
        self.grant()
        b = self.batch(1)
        self.approve(b, 1)
        self.run_cli("pause", module=gtm)
        self.assertTrue((gtm.R() / "PAUSED").exists())
        self.assertEqual(self.send(b)[0], 3)
        self.run_cli("resume", module=gtm)
        os.environ["MARKETING_UNATTENDED"] = "1"
        self.assertEqual(self.run_cli("approve", "b1", "--count", "1", "--quote", "x", module=gtm)[0], 1)
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "approve_to_send",
                                      "--quote", "x", module=gtm)[0], 1)
        os.environ.pop("MARKETING_UNATTENDED")
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "approve_to_send",
                                      module=gtm)[0], 1)              # needs the human's words
        os.environ["MARKETING_STATE"] = "repo"
        self.assertEqual(self.send(b)[0], 1)
        self.assertIn("repo backend", self.last_err)
        os.environ.pop("MARKETING_STATE")

    def test_unknown_level_sends_nothing(self):
        s = json.loads((gtm.R() / "gtm.json").read_text())
        s["authority"] = {"outbound": {"level": "boundless"}}
        (gtm.R() / "gtm.json").write_text(json.dumps(s))
        n, why = gtm.send_capacity(gtm.load_state(), "outbound")
        self.assertEqual(n, 0)
        self.assertIn("unknown authority level", why)

    def test_mixed_channel_batch_is_refused_and_dry_run_sends_nothing(self):
        self.grant()
        d = gtm.R() / "sends" / "mix"
        d.mkdir(parents=True)
        gtm.write_jsonl(d / "drafts.jsonl", [{"to": "a@x.com", "subject": "s", "body": "b", "channel": "outbound"},
                                             {"to": "b@y.com", "subject": "s", "body": "b", "channel": "creators"}])
        self.assertEqual(self.run_cli("mix")[0], 1)
        b = self.batch(2)
        self.approve(b, 2)
        self.assertEqual(self.send(b, "--dry-run")[1]["would_send"], 2)
        self.assertEqual(self.smtp.messages, [])
