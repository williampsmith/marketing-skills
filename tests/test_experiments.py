"""Tests for the experiments stats script and its fit with gtm.py's A/B judging. Run: python3 -m unittest discover tests"""
import json

from helpers import StoreCase, load

stats = load("skills/experiments/scripts/stats.py", "stats")
gtm = load("skills/gtm/scripts/gtm.py", "gtm")


class StatsTest(StoreCase):
    module = stats

    def test_sample_size_matches_the_textbook(self):
        self.assertEqual(stats.size(0.05, 0.2), 8158)          # 5% baseline, +20% relative, 80% power
        self.assertLess(stats.size(0.05, 0.5), stats.size(0.05, 0.2))

    def test_days_says_when_not_to_run_it(self):
        d = stats.days(0.02, 0.1, daily=200)
        self.assertFalse(d["run_it"])
        self.assertIn("holdout", d["advice"])
        self.assertTrue(stats.days(0.05, 0.2, daily=2000)["run_it"])

    def test_ztest_agrees_with_gtm_and_flags_significance(self):
        t = stats.ztest(1000, 50, 1000, 68)
        self.assertAlmostEqual(t["p_value"], 0.0876, places=3)
        self.assertFalse(t["significant"])
        g = gtm.ztest(1000, 50, 1000, 68)
        self.assertAlmostEqual(g["p_value"], t["p_value"], places=4)
        self.assertTrue(stats.ztest(10000, 500, 10000, 600)["significant"])

    def test_cli_and_bad_input(self):
        out = self.json_cli("test", "--a", "1000:50", "--b", "1000:68")
        self.assertIn("ci95_abs", out)
        self.assertEqual(self.run_cli("test", "--a", "10:50", "--b", "10:1")[0], 1)
        self.assertEqual(self.run_cli("size", "--baseline", "2", "--mde", "0.1")[0], 1)
        h = self.json_cli("holdout", "--treated-before", "0.1", "--treated-after", "0.25",
                          "--control-before", "0.1", "--control-after", "0.12")
        self.assertAlmostEqual(h["effect"], 0.13)


class StatsEdgeTest(StoreCase):
    module = stats

    def test_impossible_lifts_and_bad_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            stats.size(0.6, 1.0)
        for kw in ({"daily": 0}, {"daily": 100, "arms": 1}):
            with self.assertRaises(ValueError):
                stats.days(0.05, 0.2, **kw)
        self.assertEqual(self.run_cli("test", "--a", "1000", "--b", "1000:5")[0], 1)
        self.assertIn("VISITORS:CONVERSIONS", self.last_err)
        self.assertEqual(self.run_cli("size", "--baseline", "0.05", "--mde", "0.2", "--power", "0.3")[0], 1)

    def test_whole_weeks_bonferroni_and_the_eight_week_line(self):
        d = stats.days(0.05, 0.2, daily=2000)
        self.assertEqual(d["days"] % 7, 0)
        self.assertGreater(stats.days(0.05, 0.2, daily=2000, arms=3)["per_arm"], d["per_arm"])

    def test_small_counts_are_not_significant(self):
        t = stats.ztest(100, 0, 100, 5)
        self.assertTrue(t["small_counts"])
        self.assertFalse(t["significant"])

    def test_srm(self):
        self.assertFalse(stats.srm(1020, 980)["mismatch"])
        self.assertTrue(stats.srm(4000, 4600)["mismatch"])

    def test_holdout_matches_gtm_judge(self):
        b = {"method": "holdout", "baseline": 0.1, "expected": 0.3, "control_metric": "c", "control_baseline": 0.1}
        r = gtm.judge(b, 0.25, 0.12, None, None, 100)
        self.assertAlmostEqual(r["effect"], stats.holdout(0.1, 0.25, 0.1, 0.12)["effect"])


class ABJudgingTest(StoreCase):
    module = gtm

    def setUp(self):
        super().setUp()
        self.run_cli("init")
        import datetime as dt
        past = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        gtm.save_bets([{"id": "ab", "track": "conversion", "channel": "on_site", "tactic": "page_cro",
                        "metric": "rate:signup", "baseline": 0.031, "expected": 0.037, "method": "ab",
                        "opened": "2026-01-01", "check": past, "status": "open", "hypothesis": "h", "result": None}])

    def test_a_worse_variant_loses_even_above_the_old_baseline(self):
        out = self.json_cli("bet", "close", "ab", "--a", "4000:200", "--b", "4000:150", "--source", "PostHog exp")
        self.assertEqual(out["status"], "lost")
        self.assertLess(out["result"]["effect"], 0)

    def test_planned_sample_and_small_counts(self):
        out = self.json_cli("bet", "close", "ab", "--a", "3000:150", "--b", "3000:200", "--source", "x",
                            "--min-n", "8158")
        self.assertEqual(out["status"], "inconclusive")
        self.assertIn("underpowered", out["result"]["note"])

    def test_void_closes_without_a_result(self):
        out = self.json_cli("bet", "close", "ab", "--void", "guardrail breached: refunds up")
        self.assertEqual(out["status"], "void")
        self.assertEqual(gtm.closed_bets(), [])                    # not counted in fit or learnings

    def test_stage_counts_cannot_take_rate_baselines(self):
        import datetime as dt
        check = (dt.date.today() + dt.timedelta(days=21)).isoformat()
        code, _ = self.run_cli("bet", "open", "--id", "c", "--track", "conversion", "--channel", "on_site",
                               "--tactic", "page_cro", "--metric", "stage:signup", "--baseline", "0.031",
                               "--expected", "0.037", "--check", check)
        self.assertEqual(code, 1)
        self.assertIn("rate:signup", self.last_err)
