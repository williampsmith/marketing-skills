"""Tests for approve-to-send: authority levels, approvals, caps, suppression, cooldowns, the kill switch.
SMTP is replaced; nothing is sent. Run: python3 -m unittest discover tests"""
import json
import os

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
sender = load("skills/outbound/scripts/send_batch.py", "send_batch")


class FakeSMTP:
    def __init__(self):
        self.messages = []

    def send_message(self, msg):
        self.messages.append(msg)

    def quit(self):
        pass


class SendTest(StoreCase):
    module = sender

    def setUp(self):
        super().setUp()
        self.saved = {k: os.environ.get(k) for k in ("SMTP_FROM",)}
        os.environ["SMTP_FROM"] = "hello@tryacme.com"
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

    def batch(self, n=3, channel="outbound", name="b1"):
        d = gtm.R() / "sends" / name
        d.mkdir(parents=True, exist_ok=True)
        rows = [{"to": f"p{i}@co{i}.com", "subject": f"Hi {i}", "body": "Short note.", "key": f"co{i}.com",
                 "channel": channel} for i in range(n)]
        gtm.write_jsonl(d / "drafts.jsonl", rows)
        return name

    def grant(self, channel="outbound", level="approve_to_send", cap="20"):
        self.assertEqual(self.run_cli("authority", "grant", channel, "--level", level, "--daily-cap", cap,
                                      module=gtm)[0], 0, self.last_err)

    def test_drafts_only_by_default(self):
        b = self.batch()
        self.run_cli("approve", b, "--count", "3", module=gtm)
        code, out = self.run_cli(b)
        self.assertEqual(code, 3)
        self.assertIn("draft", json.loads(out)["refused"])
        self.assertEqual(self.smtp.messages, [])

    def test_sends_only_the_approved_drafts_with_footer(self):
        self.grant()
        b = self.batch(3)
        self.run_cli("approve", b, "--count", "2", module=gtm)
        code, out = self.run_cli(b)
        self.assertEqual(code, 0, out + self.last_err)
        self.assertEqual(len(self.smtp.messages), 2)
        body = self.smtp.messages[0].get_content()
        self.assertIn("1 Main St", body)
        self.assertIn("stop", body)
        self.assertEqual(self.smtp.messages[0]["From"], "hello@tryacme.com")
        self.assertEqual(json.loads(out)["skipped"][0]["why"], "not approved")
        code, out = self.run_cli(b)                     # nothing left: already sent / not approved
        self.assertEqual(len(self.smtp.messages), 2)

    def test_suppression_cooldown_and_daily_cap(self):
        self.grant(cap="2")
        (gtm.R() / "suppression.csv").write_text("email,reason\nco0.com,asked to stop\n")
        b = self.batch(4)
        self.run_cli("approve", b, "--count", "4", module=gtm)
        code, out = self.run_cli(b)
        self.assertEqual(code, 3)                       # 3 sendable > cap 2: refuse the batch, send nothing
        self.assertIn("cap", json.loads(out)["refused"])
        self.grant(cap="10")
        code, out = self.run_cli(b)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.smtp.messages), 3)
        self.assertIn("suppressed", [x["why"] for x in json.loads(out)["skipped"]])
        b2 = self.batch(2, name="b2")                   # same companies again: cooldown
        self.run_cli("approve", b2, "--count", "2", module=gtm)
        out = json.loads(self.run_cli(b2)[1])
        self.assertEqual(len(self.smtp.messages), 3)
        self.assertTrue(all("cools down" in x["why"] or x["why"] == "suppressed" for x in out["skipped"]))

    def test_kill_switch_and_missing_sender_details(self):
        self.grant()
        b = self.batch(1)
        self.run_cli("approve", b, "--count", "1", module=gtm)
        self.run_cli("pause", module=gtm)
        self.assertEqual(self.run_cli(b)[0], 3)
        self.run_cli("resume", module=gtm)
        s = json.loads((gtm.R() / "gtm.json").read_text())
        s.pop("sender")
        (gtm.R() / "gtm.json").write_text(json.dumps(s))
        self.assertEqual(self.run_cli(b)[0], 1)
        self.assertEqual(self.smtp.messages, [])

    def test_mixed_channel_batch_is_refused_and_dry_run_sends_nothing(self):
        self.grant()
        d = gtm.R() / "sends" / "mix"
        d.mkdir(parents=True)
        gtm.write_jsonl(d / "drafts.jsonl", [{"to": "a@x.com", "subject": "s", "body": "b", "channel": "outbound"},
                                             {"to": "b@y.com", "subject": "s", "body": "b", "channel": "creators"}])
        self.assertEqual(self.run_cli("mix")[0], 1)
        b = self.batch(2)
        self.run_cli("approve", b, "--count", "2", module=gtm)
        self.assertEqual(json.loads(self.run_cli(b, "--dry-run")[1])["would_send"], 2)
        self.assertEqual(self.smtp.messages, [])
