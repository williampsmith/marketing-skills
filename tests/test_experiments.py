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
