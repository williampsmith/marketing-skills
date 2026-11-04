"""Tests for the daily report's data layer and the approval provenance it relies on. Offline: no PostHog,
no Slack. The D3 renderer has its own tests (skills/daily-report/scripts/render/test, run with node).
Run: python3 -m unittest discover tests"""
import datetime as dt
import json
import os
import unittest
from pathlib import Path

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
rd = load("skills/daily-report/scripts/report_data.py", "report_data")


def daily(values, end=dt.date(2026, 11, 2)):
    return [{"date": (end - dt.timedelta(days=len(values) - 1 - i)).isoformat(), "value": v}
            for i, v in enumerate(values)]


class StatsTest(unittest.TestCase):
    def test_wilson_matches_known_interval(self):
        lo, hi = rd.wilson(31, 168)
        self.assertAlmostEqual(lo, 0.1332, places=3)
        self.assertAlmostEqual(hi, 0.2502, places=3)
        self.assertIsNone(rd.wilson(5, 0))
        self.assertIsNone(rd.wilson(6, 5))

    def test_poisson_two_sided(self):
        self.assertGreater(rd.poisson_two_sided(26, 26), 0.8)
        self.assertLess(rd.poisson_two_sided(51, 26), 0.001)
        self.assertLess(rd.poisson_two_sided(8, 26), 0.001)
        self.assertEqual(rd.poisson_two_sided(0, 0), 1.0)

    def test_weekly_drops_the_partial_week(self):
        w = rd.weekly(daily([1] * 17), dt.date(2026, 11, 2))
        self.assertEqual([x["value"] for x in w], [7.0, 7.0])
        self.assertEqual(w[-1]["end"], "2026-11-02")

    def test_spike_is_unusual_only_when_both_tests_agree(self):
        base = [4, 3, 4, 4, 3, 4, 4] * 7
        weeks = rd.weekly(daily(base + [7, 8, 7, 8, 7, 7, 7]), dt.date(2026, 11, 2))
        self.assertEqual(rd.read_week(weeks)["verdict"], "unusually_high")
        weeks = rd.weekly(daily(base + [4, 4, 4, 5, 4, 3, 4]), dt.date(2026, 11, 2))
        self.assertEqual(rd.read_week(weeks)["verdict"], "normal")

    def test_small_counts_never_become_a_trend(self):
        weeks = rd.weekly(daily([0, 1, 0, 0, 0, 1, 0] * 7 + [1, 1, 1, 1, 1, 1, 1]), dt.date(2026, 11, 2))
        r = rd.read_week(weeks)
        self.assertEqual(r["verdict"], "too_little_data")
        self.assertIn("noise", r["why"])

    def test_too_few_weeks(self):
        weeks = rd.weekly(daily([9] * 21), dt.date(2026, 11, 2))
        self.assertEqual(rd.read_week(weeks)["verdict"], "too_little_data")


class BuildTest(StoreCase):
    module = rd

    def setUp(self):
        super().setUp()
        self.run_cli("init", module=gtm)

    def test_build_offline_collects_the_store(self):
        d = gtm.today().isoformat()
        gtm.metric_add("stage:visit", 2400, source="posthog", track="demand")
        gtm.metric_add("stage:signup", 168, source="posthog", track="conversion")
        self.run_cli("record", "work_session", "--cost", "0.4", module=gtm)
        sends = gtm.R() / "sends" / "acme-1"
        sends.mkdir(parents=True)
        gtm.write_jsonl(sends / "drafts.jsonl", [{"to": "a@b.co", "subject": "Hi", "body": "x", "key": "b.co"}])
        out = self.json_cli("build", "--offline")
        data = json.loads(Path(out["data"]).read_text())
        self.assertIn("stage:signup", data["metrics"])
        self.assertEqual(data["needs_human"][0]["batch"], "acme-1")
        self.assertEqual(out["needs_human"], 1)
        self.assertTrue(any(a["kind"] == "work" and a["date"] == d for a in data["actions"]))
        self.assertEqual(data["series"], {})
        self.assertIn("focus", data)
        signup = next(s for s in data["funnel"]["steps"] if s["id"] == "signup")
        self.assertEqual(len(signup["interval"]), 2)
        self.assertIn(signup["vs_floor"], ("below", "above", "unclear"))
        code, text = self.run_cli("show")
        self.assertEqual(code, 0)

    def test_posthog_not_connected_is_a_note_not_a_failure(self):
        out = self.json_cli("build")
        self.assertTrue(any("PostHog isn't connected" in n for n in out["notes"]))

    def test_build_refuses_a_tiny_window(self):
        code, _ = self.run_cli("build", "--offline", "--days", "7")
        self.assertEqual(code, 1)


class ProvenanceTest(StoreCase):
    module = gtm

    def setUp(self):
        super().setUp()
        self.saved = os.environ.pop("MARKETING_UNATTENDED", None)
        self.run_cli("init")
        d = gtm.R() / "sends" / "b1"
        d.mkdir(parents=True)
        gtm.write_jsonl(d / "drafts.jsonl", [{"to": f"p{i}@c{i}.com", "subject": "s", "body": "b", "key": f"c{i}.com"}
                                             for i in range(3)])

    def tearDown(self):
        if self.saved is not None:
            os.environ["MARKETING_UNATTENDED"] = self.saved
        super().tearDown()

    def test_without_an_approver_list_approval_works_as_before_and_keeps_provenance(self):
        code, _ = self.run_cli("approve", "b1", "--count", "2", "--quote", "approve 2",
                               "--approver", "slack:U1", "--source", "https://x.slack.com/archives/C1/p1")
        self.assertEqual(code, 0, self.last_err)
        row = gtm.read_jsonl(gtm.R() / "approvals.jsonl")[0]
        self.assertEqual((row["approver"], row["source"]), ("slack:U1", "https://x.slack.com/archives/C1/p1"))

    def test_with_an_approver_list_only_a_listed_approver_counts(self):
        self.assertEqual(self.run_cli("approvers", "add", "slack:U1", "--quote", "I approve things")[0], 0, self.last_err)
        code, _ = self.run_cli("approve", "b1", "--count", "1", "--quote", "approve")
        self.assertEqual(code, 1)
        self.assertIn("--approver", self.last_err)
        self.assertEqual(self.run_cli("approve", "b1", "--count", "1", "--quote", "approve",
                                      "--approver", "slack:U2")[0], 1)
        self.assertEqual(self.run_cli("approve", "b1", "--count", "1", "--quote", "approve",
                                      "--approver", "slack:U1")[0], 0, self.last_err)

    def test_only_an_existing_approver_adds_another(self):
        self.run_cli("approvers", "add", "slack:U1", "--quote", "me")
        self.assertEqual(self.run_cli("approvers", "add", "slack:U9", "--quote", "add me")[0], 1)
        self.assertEqual(self.run_cli("approvers", "add", "slack:U9", "--quote", "add U9", "--approver", "slack:U1")[0], 0)
        self.assertEqual(json.loads(self.run_cli("approvers", "show")[1]), ["slack:U1", "slack:U9"])
        self.assertEqual(self.run_cli("approvers", "remove", "slack:U9")[0], 0)  # narrowing needs no one
        self.assertEqual(self.run_cli("approvers", "add", "nope", "--quote", "x", "--approver", "slack:U1")[0], 1)

    def test_adding_an_approver_is_refused_unattended(self):
        os.environ["MARKETING_UNATTENDED"] = "1"
        try:
            self.assertEqual(self.run_cli("approvers", "add", "slack:U1", "--quote", "me")[0], 1)
            self.assertIn("unattended", self.last_err)
        finally:
            os.environ.pop("MARKETING_UNATTENDED")

    def test_grants_and_paid_need_a_listed_approver_too(self):
        self.run_cli("approvers", "add", "slack:U1", "--quote", "me")
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "approve_to_send",
                                      "--quote", "go")[0], 1)
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "approve_to_send",
                                      "--quote", "go", "--approver", "slack:U1")[0], 0, self.last_err)
        s = gtm.load_state()
        self.assertEqual(s["authority"]["outbound"]["approver"], "slack:U1")
        self.assertEqual(self.run_cli("authority", "grant", "outbound", "--level", "draft")[0], 0)  # lowering: anyone
        self.assertNotIn("approver", gtm.load_state()["authority"]["outbound"])
        self.assertEqual(self.run_cli("track", "paid", "on", "--quote", "go")[0], 1)
        self.assertEqual(self.run_cli("track", "paid", "on", "--quote", "go", "--approver", "slack:U1")[0], 0)

    def test_a_scheduled_run_marker_refuses_approvals_until_it_ends_or_expires(self):
        self.assertEqual(self.run_cli("unattended", "start", "--by", "hermes-cron:test")[0], 0)
        code, _ = self.run_cli("approve", "b1", "--count", "1", "--quote", "ok")
        self.assertEqual(code, 1)
        self.assertIn("scheduled run is in progress", self.last_err)
        self.assertTrue(json.loads(self.run_cli("unattended", "status")[1])["scheduled_run"])
        self.assertEqual(self.run_cli("unattended", "end", "--by", "test")[0], 0)
        self.assertEqual(self.run_cli("approve", "b1", "--count", "1", "--quote", "ok")[0], 0, self.last_err)
        log = gtm.read_jsonl(gtm.R() / "unattended.log")
        self.assertEqual([r["event"] for r in log], ["start", "end"])
        # an expired marker doesn't count; an unreadable one does
        (gtm.R() / "UNATTENDED").write_text(json.dumps({"expires": "2000-01-01T00:00:00+00:00"}))
        self.assertIsNone(gtm.unattended_refusal("x"))
        (gtm.R() / "UNATTENDED").write_text("garbage")
        self.assertIsNotNone(gtm.unattended_refusal("x"))

    def test_daily_report_is_off_until_turned_on(self):
        jobs, _, _ = gtm.due(gtm.load_state())
        self.assertNotIn("daily_report", [j["job"] for j in jobs])
        self.assertEqual(self.run_cli("job", "daily_report", "on")[0], 0)
        jobs, _, _ = gtm.due(gtm.load_state())
        self.assertIn("daily_report", [j["job"] for j in jobs])
        self.assertEqual(self.run_cli("job", "nope", "on")[0], 1)


if __name__ == "__main__":
    unittest.main()
