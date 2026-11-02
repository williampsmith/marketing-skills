"""Tests for bounded authority and capped spend: promotion, pinned templates and segments, demotion,
the daily-budget gate, and who may change what. No network. Run: python3 -m unittest discover tests"""
import datetime as dt
import json
import os

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
Q = ("--quote", "the human said so")
TEMPLATE = "Subject: A note for {{company}}\n---\nHi {{first_name}},\n\nOne line about the problem.\n"


class Base(StoreCase):
    module = gtm

    def setUp(self):
        super().setUp()
        self.saved = os.environ.pop("MARKETING_UNATTENDED", None)
        self.run_cli("init")
        (gtm.R() / "templates").mkdir()
        (gtm.R() / "templates" / "t1.txt").write_text(TEMPLATE)
        (gtm.R() / "segments").mkdir()
        (gtm.R() / "segments" / "s1.txt").write_text("x.com\nlead@y.com\n")

    def tearDown(self):
        os.environ.pop("MARKETING_UNATTENDED", None)
        if self.saved is not None:
            os.environ["MARKETING_UNATTENDED"] = self.saved
        super().tearDown()

    def state(self):
        return json.loads((gtm.R() / "gtm.json").read_text())

    def put(self, s):
        (gtm.R() / "gtm.json").write_text(json.dumps(s))

    def days_ago(self, n):
        return (dt.date.today() - dt.timedelta(days=n)).isoformat()

    def at_approve_to_send(self, days=40, sent=60, replies=3):
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "approve_to_send", *Q)[0], 0)
        s = self.state()
        s["authority"]["outbound"]["ats_since"] = self.days_ago(days)
        self.put(s)
        gtm.append_jsonl(gtm.R() / "sends.jsonl", {"date": self.days_ago(5), "channel": "outbound", "batch": "b", "n": sent})
        self.run_cli("outcome", "outbound", "--replies", str(replies))

    def grant_bounded(self, channel="outbound"):
        return self.run_cli("authority", "grant", channel, "--level", "bounded", "--template", "t1",
                            "--segment", "s1", *Q)[0]

    def draft(self, **kw):
        d = {"to": "ana@x.com", "subject": "A note for Acme", "body": "Hi Ana,\n\nOne line about the problem.",
             "channel": "outbound", "template": "t1", "segment": "s1", "slots": {"company": "Acme", "first_name": "Ana"}}
        d.update(kw)
        return d


class PromotionTest(Base):
    def test_bounded_requires_promotion(self):
        self.assertEqual(self.grant_bounded(), 1)                      # still drafts only
        self.at_approve_to_send(days=10)
        self.assertEqual(self.grant_bounded(), 1)
        self.assertIn("days", self.last_err)
        s = self.state()
        s["authority"]["outbound"]["ats_since"] = self.days_ago(40)
        self.put(s)
        self.assertIs(self.json_cli("authority", "show")["outbound"]["bounded_eligible"], True)
        self.assertEqual(self.grant_bounded(), 0, self.last_err)
        self.assertGreater(gtm.send_capacity(gtm.load_state(), "outbound")[0], 0)

    def test_editors_and_creators_are_never_bounded(self):
        self.assertEqual(self.grant_bounded("citation_outreach"), 1)
        self.assertIn("never bounded", self.last_err)

    def test_outcomes_cannot_be_inflated(self):
        self.at_approve_to_send(replies=500)
        self.assertEqual(gtm.outcomes("outbound", self.days_ago(40))["replies"], 60)   # clamped to sends
        self.assertEqual(self.run_cli("outcome", "outbound", "--replies", "1", "--date", "9999-12-31")[0], 1)
        self.assertEqual(self.run_cli("outcome", "outbound", "--replies", "1", "--date", "zzz")[0], 1)

    def test_a_backdated_complaint_still_blocks_and_demotion_restarts_the_clock(self):
        self.at_approve_to_send()
        self.assertEqual(self.grant_bounded(), 0)
        self.run_cli("outcome", "outbound", "--complaints", "1", "--date", "2000-01-01")
        a = self.state()["authority"]["outbound"]
        self.assertEqual(a["level"], "approve_to_send")
        self.assertEqual(a["ats_since"], dt.date.today().isoformat())
        ok, why = gtm.promotion_check(gtm.load_state(), "outbound")
        self.assertFalse(ok)


class TemplateTest(Base):
    def setUp(self):
        super().setUp()
        self.at_approve_to_send()
        self.assertEqual(self.grant_bounded(), 0, self.last_err)

    def test_only_the_rendered_template_to_the_segment_passes(self):
        s = gtm.load_state()
        self.assertIsNone(gtm.bounded_draft_ok(s, "outbound", self.draft(), "ana@x.com"))
        self.assertIsNone(gtm.bounded_draft_ok(s, "outbound", self.draft(to="lead@y.com"), "lead@y.com"))
        self.assertIn("exactly its template",
                      gtm.bounded_draft_ok(s, "outbound", self.draft(body="Anything at all"), "ana@x.com"))
        self.assertIn("segment", gtm.bounded_draft_ok(s, "outbound", self.draft(), "ceo@other.com"))
        long_slot = self.draft(slots={"company": "A" * 200, "first_name": "Ana"})
        self.assertIn("single lines", gtm.bounded_draft_ok(s, "outbound", long_slot, "ana@x.com"))
        self.assertIn("isn't approved", gtm.bounded_draft_ok(s, "outbound", self.draft(template="t9"), "ana@x.com"))

    def test_editing_a_pinned_file_breaks_it(self):
        (gtm.R() / "templates" / "t1.txt").write_text(TEMPLATE + "P.S. buy now\n")
        self.assertIn("changed since", gtm.bounded_draft_ok(gtm.load_state(), "outbound", self.draft(), "ana@x.com"))
        (gtm.R() / "templates" / "t1.txt").write_text(TEMPLATE)
        (gtm.R() / "segments" / "s1.txt").write_text("x.com\neveryone.com\n")
        self.assertIn("changed since", gtm.bounded_draft_ok(gtm.load_state(), "outbound", self.draft(), "ana@x.com"))

    def test_bounded_can_be_adjusted_and_lowered_unattended(self):
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "bounded", "--daily-cap", "5", *Q)[0], 0)
        os.environ["MARKETING_UNATTENDED"] = "1"
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "bounded", "--daily-cap", "50",
                                      *Q)[0], 1)                       # widening needs a human
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "draft")[0], 0)
        self.assertEqual(self.state()["authority"]["outbound"]["level"], "draft")
        self.run_cli("pause")
        self.assertEqual(self.run_cli("resume")[0], 1)                 # a human resumes


class SpendTest(Base):
    def grant(self):
        self.assertEqual(self.run_cli("authority", "grant", "paid_search", "--level", "bounded",
                                      "--daily-spend-cap", "100", "--max-change-pct", "20", *Q)[0], 0)
        self.assertEqual(self.run_cli("track", "paid", "on", *Q)[0], 0)

    def check(self, cur, new):
        return self.run_cli("spend", "check", "paid_search", "--current-daily-usd", str(cur), "--new-daily-usd", str(new))[0]

    def test_proposals_until_bounded_and_track_on(self):
        self.assertEqual(self.run_cli("authority", "grant", "paid_search", "--level", "approve_to_send", *Q)[0], 1)
        self.assertEqual(self.check(50, 55), 3)
        self.run_cli("authority", "grant", "paid_search", "--level", "bounded", "--daily-spend-cap", "100", *Q)
        self.assertEqual(self.check(50, 55), 3)                        # track off
        self.assertEqual(self.run_cli("track", "paid", "on")[0], 1)    # needs a quote

    def test_the_budget_level_is_capped_and_moves_once_a_day(self):
        self.grant()
        self.assertEqual(self.check(50, 60), 0)
        self.assertEqual(self.check(50, 70), 3)                        # 40% step
        self.assertEqual(self.check(95, 110), 3)                       # over the cap
        self.assertEqual(self.check(0, 10), 3)                         # new spend stays human
        self.assertEqual(self.run_cli("spend", "log", "paid_search", "--current-daily-usd", "50",
                                      "--new-daily-usd", "60")[0], 0)
        self.assertEqual(self.check(60, 70), 3)                        # one change a day

    def test_log_is_gated_and_nonfinite_numbers_are_refused(self):
        self.assertEqual(self.run_cli("spend", "log", "paid_search", "--current-daily-usd", "50",
                                      "--new-daily-usd", "999")[0], 3)
        self.grant()
        for bad in ("nan", "inf", "-inf"):
            self.assertNotEqual(self.check(50, bad), 0)
        self.assertNotEqual(self.run_cli("authority", "grant", "paid_search", "--level", "bounded",
                                         "--daily-spend-cap", "nan", *Q)[0], 0)
        self.assertEqual(self.check(-5, 5), 3)
        self.run_cli("pause")
        self.assertEqual(self.check(50, 55), 3)


class BoundedSendTest(Base):
    def test_bounded_batch_sends_only_templates_to_segments_and_skips_replied(self):
        sender = load("skills/outbound/scripts/send_batch.py", "send_batch_bounded")
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
            self.at_approve_to_send()
            self.assertEqual(self.grant_bounded(), 0)
            s = self.state()
            s["sender"] = {"address": "1 Main St", "opt_out": "Reply stop."}
            self.put(s)
            (gtm.R() / "replied.csv").write_text("y.com\n")
            d = gtm.R() / "sends" / "auto"
            d.mkdir(parents=True)
            gtm.write_jsonl(d / "drafts.jsonl", [
                self.draft(),
                self.draft(to="lead@y.com", slots={"company": "Y", "first_name": "Lee"},
                           subject="A note for Y", body="Hi Lee,\n\nOne line about the problem."),
                self.draft(to="bob@x.com", body="Something else entirely")])
            code, out = self.run_cli("auto", module=sender)
            self.assertEqual(code, 0, out + self.last_err)
            self.assertEqual(len(msgs), 1)
            whys = [x["why"] for x in json.loads(out)["skipped"]]
            self.assertTrue(any("replied before" in w for w in whys))
            self.assertTrue(any("exactly its template" in w for w in whys))
        finally:
            sender.smtp_connect = real
            os.environ.pop("SMTP_FROM", None) if old is None else os.environ.__setitem__("SMTP_FROM", old)
