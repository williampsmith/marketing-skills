"""Tests for gtm.py: scheduling, budget gating, ladder, events. Run: python3 -m unittest discover tests"""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gtm", ROOT / "skills/gtm/scripts/gtm.py")
gtm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gtm)


def run(*argv):
    out = io.StringIO()
    old = sys.argv
    sys.argv = ["gtm.py", *argv]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = gtm.main()
    finally:
        sys.argv = old
    return code, out.getvalue()


def score(by_bucket, diff=None):
    s = {"overall": {"mention_rate": 0.2, "citation_rate": 0.1, "share_of_voice": 0.1, "answers": 10},
         "by_bucket": by_bucket}
    if diff:
        s["diff"], s["diff_vs"] = diff, "2026-10-24"
    return s


def b(answers, mention, rank=None):
    return {"answers": answers, "mention_rate": mention, "citation_rate": 0, "share_of_voice": 0,
            "avg_rank_when_named": rank}


class GtmTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.today = dt.date.today()

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def iso(self, days_ago):
        return (self.today - dt.timedelta(days=days_ago)).isoformat()

    def tick(self):
        code, out = run("tick")
        self.assertEqual(code, 0)
        return json.loads(out)

    def write_run(self, name, sc):
        d = Path(".marketing/runs") / name
        d.mkdir(parents=True)
        (d / "score.json").write_text(json.dumps(sc))
        return d

    def test_init_then_everything_due_free_first(self):
        self.assertEqual(run("init")[0], 0)
        t = self.tick()
        names = [j["job"] for j in t["due"]]
        self.assertIn("access_check", names)
        self.assertIn("audit", names)
        self.assertNotIn("outreach_refresh", names)  # waits for an audit
        self.assertNotIn("launch_scan", names)       # only changes after init
        self.assertNotIn("panel_review", names)
        self.assertEqual(names[0], "access_check")    # free jobs scheduled before paid ones
        self.assertEqual(t["ladder"]["current"], "reachable")

    def test_prelaunch_skips_measurement(self):
        run("init", "--stage", "prelaunch")
        names = [j["job"] for j in self.tick()["due"]]
        self.assertNotIn("audit", names)
        self.assertNotIn("access_check", names)
        self.assertIn("entity_probe", names)

    def test_cadence_and_dependency(self):
        run("init")
        s = json.loads(Path(".marketing/gtm.json").read_text())
        s["last_run"] = {"access_check": self.iso(0), "audit": self.iso(1), "outreach_refresh": self.iso(3)}
        Path(".marketing/gtm.json").write_text(json.dumps(s))
        names = [j["job"] for j in self.tick()["due"]]
        self.assertNotIn("access_check", names)
        self.assertNotIn("audit", names)
        self.assertNotIn("outreach_refresh", names)  # newer than the last audit
        s["last_run"]["audit"] = self.iso(0)
        s["last_run"]["outreach_refresh"] = self.iso(8)
        Path(".marketing/gtm.json").write_text(json.dumps(s))
        self.assertIn("outreach_refresh", [j["job"] for j in self.tick()["due"]])

    def test_budget_defers_paid_jobs_and_need_gate(self):
        run("init", "--budget", "1")
        Path(".marketing/spend.jsonl").write_text(json.dumps({"date": self.today.isoformat(), "job": "x", "usd": 0.9}) + "\n")
        t = self.tick()
        self.assertIn("audit", [j["job"] for j in t["deferred"]])
        self.assertIn("access_check", [j["job"] for j in t["due"]])
        self.assertEqual(run("budget", "--need", "0.5")[0], 2)
        self.assertEqual(run("budget", "--need", "0.05")[0], 0)

    def test_record_from_run_sums_cost(self):
        run("init")
        d = Path(".marketing/runs/2026-11-01")
        d.mkdir(parents=True)
        (d / "answers.jsonl").write_text("\n".join(json.dumps({"cost_usd": c}) for c in (0.01, 0.02, None)))
        run("record", "audit", "--from-run", str(d))
        self.assertAlmostEqual(gtm.month_spend(gtm.spend_rows()), 0.03)
        self.assertEqual(json.loads(Path(".marketing/gtm.json").read_text())["last_run"]["audit"], self.today.isoformat())

    def test_ladder_progression(self):
        run("init")
        Path(".marketing/access").mkdir(parents=True)
        Path(".marketing/access/latest.json").write_text(json.dumps({"problems": ["/: no JSON-LD"]}))
        self.write_run("2026-10-01", score({"brand": b(5, 1.0), "category": b(10, 0.1), "comparison": b(4, 0.0)}))
        lad = json.loads(run("ladder")[1])
        self.assertTrue(lad["rungs"]["reachable"]["met"])  # JSON-LD missing doesn't block reachability
        self.assertTrue(lad["rungs"]["known"]["met"])
        self.assertEqual(lad["current"], "associated")
        self.assertIn("one-pager", lad["work_on"])

    def test_known_issue_blocks_known_and_access_blocks_reachable(self):
        run("init")
        s = json.loads(Path(".marketing/gtm.json").read_text())
        s["known_issues"] = ["name collision with another product"]
        Path(".marketing/gtm.json").write_text(json.dumps(s))
        self.write_run("2026-10-01", score({"brand": b(5, 1.0)}))
        Path(".marketing/access").mkdir(parents=True)
        Path(".marketing/access/latest.json").write_text(json.dumps(
            {"problems": ["OAI-SearchBot (search) cannot read /: robots=disallow http=200 "]}))
        lad = json.loads(run("ladder")[1])
        self.assertFalse(lad["rungs"]["reachable"]["met"])
        self.assertFalse(lad["rungs"]["known"]["met"])
        self.assertEqual(lad["current"], "reachable")
        s["accepted_problems"] = ["OAI-SearchBot (search) cannot read /: robots=disallow http=200 "]
        Path(".marketing/gtm.json").write_text(json.dumps(s))
        self.assertEqual(json.loads(run("ladder")[1])["current"], "known")

    def test_events_watch_change_access_regression_and_losses(self):
        run("init")
        Path(".marketing/watch").mkdir(parents=True)
        Path(".marketing/watch/report.md").write_text("# Watch report — 2026-11-01\n\n## Changed: https://x.com/pricing\n")
        Path(".marketing/access").mkdir(parents=True)
        Path(".marketing/access/previous.json").write_text(json.dumps({"problems": []}))
        Path(".marketing/access/latest.json").write_text(json.dumps({"problems": ["GPTBot (train) cannot read /"]}))
        self.write_run("2026-11-01", score({}, diff={"overall": {"mention_rate": -0.1, "citation_rate": 0, "share_of_voice": 0},
                                                     "won": [], "lost": ["a on x", "b on x", "c on y"]}))
        t = self.tick()
        ev = [j for j in t["due"] if j["job"] == "comparison_refresh"]
        self.assertEqual(ev[0]["event"], "2026-11-01")
        self.assertTrue(any("ACCESS REGRESSION" in a for a in t["alerts"]))
        self.assertTrue(any("3 prompts lost" in a for a in t["alerts"]))
        run("record", "comparison_refresh", "--event", "2026-11-01")
        self.assertNotIn("comparison_refresh", [j["job"] for j in self.tick()["due"]])

    def test_digest_and_status(self):
        run("init")
        self.write_run("2026-11-01", score({"brand": b(5, 0.2)}))
        code, out = run("digest")
        self.assertEqual(code, 0)
        text = Path(out.strip()).read_text()
        self.assertIn("## Needs you", text)
        self.assertIn("working on `reachable`", text)
        self.assertEqual(run("digest")[0], 1)  # never clobbers a filled digest
        self.assertIn("ladder: working on", run("status")[1])


if __name__ == "__main__":
    unittest.main()
