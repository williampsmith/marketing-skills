"""Tests for bounded authority: promotion criteria, template and segment allowlists, demotion on
complaint, capped ad spend and the paid track switch. No network. Run: python3 -m unittest discover tests"""
import datetime as dt
import json
import os

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
Q = ("--quote", "the human said so")


class BoundedTest(StoreCase):
    module = gtm

    def setUp(self):
        super().setUp()
        self.saved = os.environ.pop("MARKETING_UNATTENDED", None)
        self.run_cli("init")

    def tearDown(self):
        if self.saved is not None:
            os.environ["MARKETING_UNATTENDED"] = self.saved
        super().tearDown()

    def state(self):
        return json.loads((gtm.R() / "gtm.json").read_text())

    def put(self, s):
        (gtm.R() / "gtm.json").write_text(json.dumps(s))

    def days_ago(self, n):
        return (dt.date.today() - dt.timedelta(days=n)).isoformat()

    def at_approve_to_send(self, days=40, sent=60, replies=3, complaints=0):
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "approve_to_send", *Q)[0], 0)
        s = self.state()
        s["authority"]["outbound"]["granted"] = self.days_ago(days)
        self.put(s)
        gtm.append_jsonl(gtm.R() / "sends.jsonl", {"date": self.days_ago(5), "channel": "outbound", "batch": "b", "n": sent})
        gtm.append_jsonl(gtm.R() / "outcomes.jsonl", {"date": self.days_ago(2), "channel": "outbound",
                                                      "replies": replies, "complaints": complaints})

    def grant_bounded(self):
        return self.run_cli("authority", "grant", "outbound", "--level", "bounded",
                            "--template", "t1", "--segment", "s1", *Q)[0]

    def test_bounded_requires_promotion_and_allowlists(self):
        self.assertEqual(self.grant_bounded(), 1)                      # still drafts only
        self.at_approve_to_send(days=10)
        self.assertEqual(self.grant_bounded(), 1)
        self.assertIn("days", self.last_err)
        s = self.state()
        s["authority"]["outbound"]["granted"] = self.days_ago(40)
        self.put(s)
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "bounded", *Q)[0], 1)  # no allowlist
        self.assertEqual(self.grant_bounded(), 0, self.last_err)
        st = gtm.load_state()
        self.assertIsNone(gtm.bounded_draft_ok(st, "outbound", {"template": "t1", "segment": "s1"}))
        self.assertIn("template", gtm.bounded_draft_ok(st, "outbound", {"template": "t9", "segment": "s1"}))
        self.assertGreater(gtm.send_capacity(st, "outbound")[0], 0)

    def test_low_replies_block_promotion_and_show_says_why(self):
        self.at_approve_to_send(replies=0)
        ok, why = gtm.promotion_check(gtm.load_state(), "outbound")
        self.assertFalse(ok)
        self.assertTrue(any("reply rate" in w for w in why))
        self.assertIsInstance(self.json_cli("authority", "show")["outbound"]["bounded_eligible"], list)

    def test_a_complaint_demotes_bounded(self):
        self.at_approve_to_send()
        self.assertEqual(self.grant_bounded(), 0)
        self.run_cli("outcome", "outbound", "--complaints", "1")
        self.assertEqual(self.state()["authority"]["outbound"]["level"], "approve_to_send")
        self.assertEqual(self.run_cli("outcome", "outbound", "--replies", "-3")[0], 1)

    def test_unattended_runs_cannot_grant_or_turn_paid_on(self):
        os.environ["MARKETING_UNATTENDED"] = "1"
        try:
            self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "approve_to_send", *Q)[0], 1)
            self.assertEqual(self.run_cli("track", "paid", "on", *Q)[0], 1)
            self.assertEqual(self.run_cli("track", "paid", "off")[0], 0)  # turning things off is always allowed
        finally:
            os.environ.pop("MARKETING_UNATTENDED")

    def test_spend_gate(self):
        self.assertEqual(self.run_cli("authority", "grant", "paid_search", "--level", "approve_to_send", *Q)[0], 1)
        self.assertEqual(self.run_cli("authority", "grant", "paid_search", "--level", "bounded", *Q)[0], 1)  # cap
        self.run_cli("authority", "grant", "paid_search", "--level", "bounded", "--daily-spend-cap", "50",
                     "--max-change-pct", "20", *Q)
        self.assertEqual(self.run_cli("spend", "check", "paid_search", "--usd", "30")[0], 3)     # track off
        self.assertEqual(self.run_cli("track", "paid", "on")[0], 1)                              # needs a quote
        self.run_cli("track", "paid", "on", *Q)
        self.assertEqual(self.run_cli("spend", "check", "paid_search", "--usd", "30", "--change-pct", "15")[0], 0)
        self.run_cli("spend", "log", "paid_search", "--usd", "30")
        self.assertEqual(self.run_cli("spend", "check", "paid_search", "--usd", "30")[0], 3)     # over the cap
        self.assertEqual(self.run_cli("spend", "check", "paid_search", "--usd", "5", "--change-pct", "40")[0], 3)
        self.assertEqual(self.run_cli("spend", "check", "paid_search", "--usd", "-5")[0], 3)
        self.run_cli("pause")
        self.assertEqual(self.run_cli("spend", "check", "paid_search", "--usd", "1")[0], 3)


class BoundedSendTest(StoreCase):
    def test_bounded_batch_sends_only_allowlisted_drafts_without_approval(self):
        sender = load("skills/outbound/scripts/send_batch.py", "send_batch_bounded")
        self.module = sender
        msgs = []

        class SMTP:
            def send_message(self, m):
                msgs.append(m)

            def quit(self):
                pass
        real = sender.smtp_connect
        sender.smtp_connect = lambda: SMTP()
        old = os.environ.get("SMTP_FROM")
        os.environ["SMTP_FROM"] = "hello@tryacme.com"
        try:
            self.run_cli("init", module=gtm)
            s = json.loads((gtm.R() / "gtm.json").read_text())
            s["sender"] = {"address": "1 Main St", "opt_out": "Reply stop."}
            s["authority"] = {"outbound": {"level": "bounded", "daily_cap": 10, "cooldown_days": 30,
                                           "templates": ["t1"], "segments": ["s1"]}}
            (gtm.R() / "gtm.json").write_text(json.dumps(s))
            d = gtm.R() / "sends" / "auto"
            d.mkdir(parents=True)
            gtm.write_jsonl(d / "drafts.jsonl", [
                {"to": "a@x.com", "subject": "s", "body": "b", "channel": "outbound", "template": "t1", "segment": "s1"},
                {"to": "b@y.com", "subject": "s", "body": "b", "channel": "outbound", "template": "t2", "segment": "s1"}])
            code, out = self.run_cli("auto")
            self.assertEqual(code, 0, out + self.last_err)
            self.assertEqual(len(msgs), 1)
            self.assertIn("template", json.loads(out)["skipped"][0]["why"])
        finally:
            sender.smtp_connect = real
            os.environ.pop("SMTP_FROM", None) if old is None else os.environ.__setitem__("SMTP_FROM", old)
