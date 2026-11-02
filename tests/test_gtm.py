"""Tests for gtm.py: scheduling, budget, fit, tracks, focus, bets, cooldowns. Run: python3 -m unittest discover tests"""
import datetime as dt
import json
from pathlib import Path

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")


def score(by_bucket, diff=None):
    s = {"overall": {"mention_rate": 0.2, "citation_rate": 0.1, "share_of_voice": 0.1, "answers": 10},
         "by_bucket": by_bucket}
    if diff:
        s["diff"], s["diff_vs"] = diff, "2026-10-24"
    return s


def b(answers, mention, rank=None):
    return {"answers": answers, "mention_rate": mention, "citation_rate": 0, "share_of_voice": 0,
            "avg_rank_when_named": rank}


class Base(StoreCase):
    module = gtm
    installed = None  # None = every skill counts as installed (the full plugin); or a set of names

    def setUp(self):
        super().setUp()
        self.today = dt.date.today()
        self.real_installed = gtm.skill_installed
        gtm.skill_installed = (lambda n: True) if self.installed is None else (lambda n: n in self.installed)

    def tearDown(self):
        gtm.skill_installed = self.real_installed
        super().tearDown()

    @property
    def root(self) -> Path:
        return gtm.R()

    def iso(self, days_ago):
        return (self.today - dt.timedelta(days=days_ago)).isoformat()

    def state(self):
        return json.loads((self.root / "gtm.json").read_text())

    def put_state(self, s):
        (self.root / "gtm.json").write_text(json.dumps(s))

    def edit(self, **kv):
        s = self.state()
        for k, v in kv.items():
            cur = s
            *path, last = k.split("__")
            for p in path:
                cur = cur.setdefault(p, {})
            cur[last] = v
        self.put_state(s)

    def tick(self):
        return self.json_cli("tick")

    def write_run(self, name, sc):
        d = self.root / "runs" / name
        d.mkdir(parents=True)
        (d / "score.json").write_text(json.dumps(sc))
        return d

    def access(self, problems, previous=None):
        a = self.root / "access"
        a.mkdir(parents=True, exist_ok=True)
        (a / "latest.json").write_text(json.dumps({"problems": problems}))
        if previous is not None:
            (a / "previous.json").write_text(json.dumps({"problems": previous}))

    def measured(self, visits=5000, signups=100, activated=40, paid=5, retained=5):
        """A launched self-serve product whose measurement track is complete."""
        for name, v in (("tracking_ok", 1), ("source_capture_rate", 0.9), ("stage:visit", visits),
                        ("stage:signup", signups), ("stage:activated", activated), ("stage:paid", paid),
                        ("stage:retained", retained)):
            gtm.metric_add(name, v, source="test")

    def discoverable(self):
        """Discoverability met up to `preferred`."""
        self.access([])
        self.write_run("2026-10-01", score({"brand": b(5, 1.0), "category": b(10, 0.5),
                                            "comparison": b(4, 0.8, 1.5)}))


class SchedulingTest(Base):
    def test_init_then_free_jobs_first(self):
        self.assertEqual(self.run_cli("init")[0], 0)
        t = self.tick()
        names = [j["job"] for j in t["due"]]
        self.assertIn("access_check", names)
        self.assertIn("audit", names)
        self.assertNotIn("outreach_refresh", names)  # waits for an audit
        self.assertNotIn("launch_scan", names)       # only changes after init
        self.assertNotIn("panel_review", names)
        self.assertEqual(names[0], "access_check")
        self.assertEqual(t["ladder"]["current"], "reachable")
        audit = next(j for j in t["due"] if j["job"] == "audit")
        self.assertIn("self_check", audit)            # job contract travels with the job

    def test_prelaunch_skips_measurement(self):
        self.run_cli("init", "--stage", "prelaunch")
        t = self.tick()
        names = [j["job"] for j in t["due"]]
        self.assertNotIn("audit", names)
        self.assertNotIn("access_check", names)
        self.assertIn("entity_probe", names)
        self.assertEqual(t["focus"]["track"], "discoverability")

    def test_cadence_and_dependency(self):
        self.run_cli("init")
        self.edit(last_run={"access_check": self.iso(0), "audit": self.iso(1), "outreach_refresh": self.iso(3)})
        names = [j["job"] for j in self.tick()["due"]]
        self.assertNotIn("access_check", names)
        self.assertNotIn("audit", names)
        self.assertNotIn("outreach_refresh", names)
        self.edit(last_run={"audit": self.iso(0), "outreach_refresh": self.iso(8)})
        self.assertIn("outreach_refresh", [j["job"] for j in self.tick()["due"]])

    def test_budget_defers_paid_jobs_and_need_gate(self):
        self.run_cli("init", "--budget", "1")
        (self.root / "spend.jsonl").write_text(json.dumps({"date": self.today.isoformat(), "job": "x", "usd": 0.9}) + "\n")
        t = self.tick()
        self.assertIn("audit", [j["job"] for j in t["deferred"]])
        self.assertIn("access_check", [j["job"] for j in t["due"]])
        self.assertEqual(self.run_cli("budget", "--need", "0.5")[0], 2)
        self.assertEqual(self.run_cli("budget", "--need", "0.05")[0], 0)

    def test_record_from_run_sums_cost(self):
        self.run_cli("init")
        d = self.root / "runs" / "2026-11-01"
        d.mkdir(parents=True)
        (d / "answers.jsonl").write_text("\n".join(json.dumps({"cost_usd": c}) for c in (0.01, 0.02, None)))
        self.run_cli("record", "audit", "--from-run", str(d))
        self.assertAlmostEqual(gtm.month_spend(gtm.spend_rows()), 0.03)
        self.assertEqual(self.state()["last_run"]["audit"], self.today.isoformat())

    def test_recording_an_audit_imports_its_scores_once(self):
        self.run_cli("init")
        d = self.write_run("2026-11-01", score({"comparison": b(4, 0.25)}))
        (d / "answers.jsonl").write_text("")
        self.run_cli("record", "audit", "--from-run", str(d))
        self.run_cli("record", "audit", "--from-run", str(d))
        rows = gtm.metric_rows("ai:mention:comparison")
        self.assertEqual([(r["date"], r["value"]) for r in rows], [("2026-11-01", 0.25)])
        self.assertEqual(gtm.metric_latest("ai:mention")["value"], 0.2)

    def test_requires_skips_with_reason(self):
        self.run_cli("init")
        s = self.state()
        s["jobs"]["audit"]["requires"] = ["connection:posthog"]
        self.put_state(s)
        t = self.tick()
        self.assertNotIn("audit", [j["job"] for j in t["due"]])
        sk = next(j for j in t["skipped"] if j["job"] == "audit")
        self.assertIn("posthog", sk["skipped"])
        self.edit(connections__posthog=True)
        self.assertIn("audit", [j["job"] for j in self.tick()["due"]])

    def test_jobs_of_disabled_tracks_do_not_run(self):
        self.run_cli("init")
        self.edit(tracks__discoverability__enabled=False)
        names = [j["job"] for j in self.tick()["due"]]
        self.assertNotIn("audit", names)
        self.assertIn("work_session", names)


class UpgradeTest(Base):
    def test_init_upgrades_a_03_state_in_place(self):
        old = {"stage": "launched", "budget_usd_month": 30, "site_url": "https://x.com",
               "jobs": {"audit": {"every_days": 7, "usd": 1.0, "stages": ["launched"], "skill": "ai-visibility-audit"}},
               "last_run": {"audit": "2026-10-20"}, "accepted_problems": ["a"], "state_commit": "direct"}
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "gtm.json").write_text(json.dumps(old))
        self.assertEqual(self.run_cli("init")[0], 0)
        s = self.state()
        self.assertEqual(s["schema"], 2)
        self.assertEqual(s["budget_usd_month"], 30)
        self.assertEqual(s["last_run"]["audit"], "2026-10-20")
        self.assertEqual(s["jobs"]["audit"]["track"], "discoverability")
        self.assertIn("fit_review", s["jobs"])
        self.assertEqual(s["profile"]["motion"], "self_serve")

    def test_upgrade_points_moved_jobs_at_their_new_skill(self):
        self.run_cli("init")
        s = self.state()
        s["jobs"]["watch"]["skill"] = "comparison-pages"
        s["jobs"]["work_session"]["skill"] = "one-pager"
        self.put_state(s)
        self.run_cli("init")
        s = self.state()
        self.assertEqual(s["jobs"]["watch"]["skill"], "competitive-intel")
        self.assertEqual(s["jobs"]["work_session"]["skill"], "gtm")

    def test_force_reset_keeps_history(self):
        self.run_cli("init", "--motion", "enterprise")
        self.run_cli("record", "audit")
        self.run_cli("init", "--force", "--budget", "40")
        s = self.state()
        self.assertEqual(s["budget_usd_month"], 40)
        self.assertIn("audit", s["last_run"])
        self.assertEqual(s["profile"]["motion"], "enterprise")


class DiscoverabilityTest(Base):
    def test_ladder_progression(self):
        self.run_cli("init")
        self.access(["/: no JSON-LD"])
        self.write_run("2026-10-01", score({"brand": b(5, 1.0), "category": b(10, 0.1), "comparison": b(4, 0.0)}))
        lad = self.json_cli("ladder")
        self.assertTrue(lad["rungs"]["reachable"]["met"])
        self.assertTrue(lad["rungs"]["known"]["met"])
        self.assertEqual(lad["current"], "associated")
        self.assertIn("content", lad["work_on"])

    def test_known_issue_and_access_block_and_alerts(self):
        self.run_cli("init")
        self.edit(known_issues=["name collision with another product"])
        self.write_run("2026-10-01", score({"brand": b(5, 1.0)}))
        problem = "OAI-SearchBot (search) cannot read /: robots=disallow http=200 "
        self.access([problem])
        lad = self.json_cli("ladder")
        self.assertFalse(lad["rungs"]["reachable"]["met"])
        self.assertFalse(lad["rungs"]["known"]["met"])
        alerts = self.tick()["alerts"]
        self.assertTrue(any(a.startswith("DISCOVERABILITY reachable") for a in alerts))
        self.assertTrue(any(a.startswith("DISCOVERABILITY known") for a in alerts))
        self.edit(accepted_problems=[problem])
        self.assertEqual(self.json_cli("ladder")["current"], "known")

    def test_prelaunch_does_not_alert_on_a_deliberately_hidden_site(self):
        self.run_cli("init", "--stage", "prelaunch")
        self.access(["Googlebot (search) cannot read /: noindex"])
        self.assertFalse(any("reachable" in a for a in self.tick()["alerts"]))

    def test_events_watch_change_access_regression_and_losses(self):
        self.run_cli("init")
        (self.root / "watch").mkdir(parents=True)
        (self.root / "watch" / "report.md").write_text("# Watch report — 2026-11-01\n\n## Changed: https://x.com/pricing\n")
        self.access(["GPTBot (train) cannot read /"], previous=[])
        self.write_run("2026-11-01", score({}, diff={"overall": {"mention_rate": -0.1, "citation_rate": 0, "share_of_voice": 0},
                                                     "won": [], "lost": ["a on x", "b on x", "c on y"]}))
        t = self.tick()
        ev = [j for j in t["due"] if j["job"] == "comparison_refresh"]
        self.assertEqual(ev[0]["event"], "2026-11-01")
        self.assertTrue(any("ACCESS REGRESSION" in a for a in t["alerts"]))
        self.assertTrue(any("3 prompts lost" in a for a in t["alerts"]))
        self.run_cli("record", "comparison_refresh", "--event", "2026-11-01")
        self.assertNotIn("comparison_refresh", [j["job"] for j in self.tick()["due"]])


class FitTest(Base):
    def fits(self):
        return self.json_cli("fit")["channels"]

    def confirm(self):
        self.json_cli("profile", "--confirm")

    def test_unconfirmed_profile_uses_motion_defaults_only(self):
        self.run_cli("init", "--motion", "self_serve", "--acv", "120")
        out = self.json_cli("fit")
        self.assertIn("unconfirmed", out["note"])
        self.assertTrue(out["channels"]["paid_social"]["eligible"])     # economics ignored
        self.confirm()
        self.assertFalse(self.fits()["paid_social"]["eligible"])

    def test_enterprise_rules_out_ugc_and_keeps_outbound(self):
        self.run_cli("init", "--motion", "enterprise", "--acv", "60000")
        self.confirm()
        f = self.fits()
        self.assertFalse(f["short_video"]["eligible"])
        self.assertTrue(f["outbound"]["eligible"])
        self.assertEqual(f["outbound"]["economics"], 1.0)
        self.assertTrue(f["ai_search"]["eligible"])

    def test_cheap_self_serve_rules_out_outbound_and_paid_social_on_economics(self):
        self.run_cli("init", "--motion", "self_serve", "--acv", "120")
        self.confirm()
        f = self.fits()
        self.assertAlmostEqual(f["outbound"]["economics"], 0.096, places=3)
        self.assertFalse(f["outbound"]["eligible"])
        self.assertAlmostEqual(f["paid_social"]["fit"], 0.24, places=2)
        self.assertFalse(f["paid_social"]["eligible"])
        self.assertIn("economics", f["paid_social"]["why"])

    def test_attention_overrides_and_regulation(self):
        self.run_cli("init", "--motion", "consumer_app")
        self.edit(profile__attention={"short_video": 0.1}, profile__regulated="heavy", profile__confirmed=True,
                  fit__overrides={"pr": "exclude", "referral": 0.9})
        f = self.fits()
        self.assertFalse(f["short_video"]["eligible"])
        self.assertIn("buyers aren't there", f["short_video"]["why"])
        self.assertEqual(f["creators"]["compliance"], 0.4)
        self.assertFalse(f["pr"]["eligible"])
        self.assertEqual(f["referral"]["fit"], 0.9)

    def test_slow_cycle_discounts_fast_feedback_channels(self):
        self.run_cli("init", "--motion", "enterprise", "--acv", "60000")
        self.edit(profile__cycle_days=180, profile__confirmed=True)
        f = self.fits()
        self.assertEqual(f["outbound"]["cycle"], 0.5)
        self.assertEqual(f["ai_search"]["cycle"], 1.0)

    def test_closed_bets_move_fit_toward_results(self):
        self.run_cli("init", "--motion", "enterprise", "--acv", "60000")
        self.confirm()
        before = self.fits()["linkedin_organic"]["fit"]
        rows = [{"id": f"b{i}", "track": "demand", "channel": "linkedin_organic", "tactic": "founder_posts",
                 "method": "before_after", "status": "lost", "result": {}} for i in range(3)]
        gtm.save_bets(rows)
        after = self.fits()["linkedin_organic"]
        self.assertLess(after["fit"], before)
        self.assertEqual(after["bets"], 3)
        self.assertAlmostEqual(after["fit"], (3 * before + 0) / 6, places=3)


class FocusTest(Base):
    def focus(self):
        return self.json_cli("focus")

    def test_measurement_gates_a_launched_funnel(self):
        self.run_cli("init")
        f = self.focus()
        self.assertEqual(f["track"], "measurement")
        self.assertEqual(f["secondary"], "discoverability")
        self.assertTrue(f["standing_discoverability"])
        self.assertEqual(f["shares"], {"focus": 0.6, "secondary": 0.25, "explore": 0.15})

    def test_low_traffic_makes_reach_the_bottleneck(self):
        self.run_cli("init")
        self.measured(visits=40, signups=2, activated=1, paid=0, retained=0)
        f = self.focus()
        self.assertEqual(f["track"], "discoverability")
        self.assertIn("reach is the bottleneck", f["reason"])

    def test_worst_conversion_stage_wins_with_standing_discoverability(self):
        self.run_cli("init")
        self.measured(visits=5000, signups=100, activated=10, paid=1, retained=1)  # activation 10% vs 30%
        f = self.focus()
        self.assertEqual(f["track"], "conversion")
        self.assertEqual(f["rung"], "activating")   # 2% visit→signup meets its floor exactly
        self.assertIn("signup → activated", f["reason"])
        self.assertEqual(f["secondary"], "discoverability")

    def test_no_standing_share_once_discoverability_is_preferred(self):
        self.run_cli("init")
        self.measured(visits=5000, signups=100, activated=10, paid=1, retained=1)
        self.discoverable()
        f = self.focus()
        self.assertFalse(f["standing_discoverability"])
        self.assertNotEqual(f["secondary"], "discoverability")

    def test_focus_holds_for_30_days_unless_severe(self):
        self.run_cli("init")
        self.measured(visits=5000, signups=100, activated=25, paid=1, retained=1)  # activation 25% (score 0.83)
        self.edit(focus={"track": "demand", "since": self.iso(5), "basis": "earlier", "stage": "launched"})
        f = self.focus()
        self.assertEqual(f["track"], "demand")
        self.assertTrue(f["reason"].endswith("earlier"))
        self.edit(focus={"track": "demand", "since": self.iso(31), "basis": "earlier", "stage": "launched"})
        self.assertEqual(self.focus()["track"], "conversion")
        gtm.metric_add("stage:activated", 5)  # 5% vs 30%: severe, overrides the hold
        self.edit(focus={"track": "demand", "since": self.iso(5), "basis": "earlier", "stage": "launched"})
        self.assertEqual(self.focus()["track"], "conversion")

    def test_tick_persists_focus(self):
        self.run_cli("init")
        self.tick()
        self.assertEqual(self.state()["focus"]["track"], "measurement")

    def test_ineligible_tracks_cannot_be_focus(self):
        self.run_cli("init", "--motion", "enterprise", "--acv", "60000")
        self.edit(fit__overrides={c: "exclude" for c in ("lifecycle_email", "referral")})
        for name, v in (("tracking_ok", 1), ("source_capture_rate", 0.9), ("stage:engaged_account", 400),
                        ("stage:meeting", 40), ("stage:opportunity", 20), ("stage:won", 5), ("stage:expanded", 0)):
            gtm.metric_add(name, v)
        f = self.focus()
        self.assertNotEqual(f["track"], "retention")


class NextTest(Base):
    def test_slots_follow_shares_and_tactics_respect_fit(self):
        self.run_cli("init", "--motion", "enterprise", "--acv", "60000")
        n = self.json_cli("next")
        self.assertEqual([x["slot"] for x in n["slots"]], ["focus", "standing"])
        self.assertEqual(n["slots"][1]["track"], "discoverability")
        tactics = {t["tactic"] for x in n["slots"] for t in x["tactics"]}
        self.assertNotIn("ugc_hooks", tactics)
        first = n["slots"][0]["tactics"][0]
        self.assertEqual(first["tactic"], "tracking_fix")  # the only measurement tactic, and on the rung
        self.assertTrue(first["on_rung"])

    def test_mix_counts_steer_later_sessions_to_explore(self):
        self.run_cli("init")
        for _ in range(4):
            self.run_cli("record", "work_session", "--mix", "focus,standing")
        cats = [x["slot"] for x in self.json_cli("next")["slots"]]
        self.assertIn("explore", cats)
        self.assertEqual(self.run_cli("record", "work_session", "--mix", "bogus")[0], 1)


class CooldownTest(Base):
    def test_may_gates_and_record_never_drops_spend(self):
        self.run_cli("init")
        self.assertEqual(self.run_cli("may", "outreach_refresh", "example.com")[0], 0)
        self.run_cli("record", "outreach_refresh", "--key", "example.com", "--key", "other.org", "--cost", "0.3")
        self.assertEqual(self.run_cli("may", "outreach_refresh", "example.com")[0], 3)
        self.assertEqual(self.run_cli("may", "outreach_refresh", "other.org")[0], 3)
        code, _ = self.run_cli("record", "outreach_refresh", "--key", "example.com", "--cost", "0.2")
        self.assertEqual(code, 0)                                   # recorded anyway, with a warning
        self.assertIn("cools down", self.last_err)
        self.assertAlmostEqual(gtm.month_spend(gtm.spend_rows()), 0.5)
        s = self.state()
        s["keys"]["outreach_refresh"]["example.com"] = self.iso(46)
        self.put_state(s)
        self.assertEqual(self.run_cli("may", "outreach_refresh", "example.com")[0], 0)

    def test_two_failures_stop_the_key_until_cleared(self):
        self.run_cli("init")
        self.run_cli("record", "work_session", "--failed", "--key", "pr-12")
        self.assertFalse(any("ESCALATE" in a for a in self.tick()["alerts"]))
        self.assertEqual(self.run_cli("may", "work_session", "pr-12")[0], 0)
        self.run_cli("record", "work_session", "--failed", "--key", "pr-12")
        self.assertTrue(any("ESCALATE" in a and "pr-12" in a for a in self.tick()["alerts"]))
        self.assertEqual(self.run_cli("may", "work_session", "pr-12")[0], 3)
        self.run_cli("record", "work_session", "--key", "pr-12")
        self.assertFalse(any("ESCALATE" in a for a in self.tick()["alerts"]))

    def test_events_and_cursors_do_not_touch_cadence(self):
        self.run_cli("init")
        self.run_cli("record", "launch_scan", "--event", "abc123", "--cursor", "abc123")
        t = self.tick()                                             # must not crash on a non-date
        self.assertEqual(self.state()["last_run"]["launch_scan"], self.today.isoformat())
        self.edit(last_run={"launch_scan": self.iso(2)})
        entry = next(j for j in self.tick()["due"] if j["job"] == "launch_scan")
        self.assertEqual(entry["cursor"], "abc123")
        self.assertTrue(t["due"] is not None)


class KillSwitchTest(Base):
    def test_pause_stops_everything(self):
        self.run_cli("init")
        self.run_cli("pause", "--reason", "bad outreach draft")
        t = self.tick()
        self.assertTrue(t["paused"])
        self.assertEqual(t["due"], [])
        self.assertIn("bad outreach draft", t["alerts"][0])
        self.assertEqual(self.run_cli("may", "outreach_refresh", "x.com")[0], 3)
        self.run_cli("resume")
        self.assertTrue(self.tick()["due"])


class BetTest(Base):
    def open(self, *extra, id="b1", check=None):
        return self.run_cli("bet", "open", "--id", id, "--track", "discoverability", "--channel", "ai_search",
                            "--tactic", "comparison_page", "--metric", "ai:mention:comparison", "--baseline", "0.1",
                            "--expected", "0.3", "--check", check or (self.today + dt.timedelta(days=28)).isoformat(),
                            *extra)

    def past_bet(self, id="old", method="before_after", **kw):
        b = {"id": id, "track": "discoverability", "channel": "ai_search", "tactic": "comparison_page",
             "metric": "ai:mention:comparison", "baseline": 0.1, "expected": 0.3, "method": method,
             "control_metric": None, "control_baseline": None, "opened": self.iso(30), "check": self.iso(1),
             "status": "open", "hypothesis": "h", "result": None, **kw}
        gtm.save_bets(gtm.bets() + [b])

    def test_open_validates(self):
        self.run_cli("init")
        self.assertEqual(self.open("--method", "holdout")[0], 1)                       # no control
        self.assertEqual(self.open("--method", "holdout", "--control-metric", "ai:mention:category")[0], 1)
        self.assertEqual(self.open(check=self.iso(1))[0], 1)
        self.assertEqual(self.open()[0], 0)
        self.assertEqual(self.open()[0], 1)
        self.assertTrue((self.root / "posthog-outbox.jsonl").exists())

    def test_close_needs_a_value_dated_after_the_check(self):
        self.run_cli("init")
        self.past_bet()
        gtm.metric_add("ai:mention:comparison", 0.25, date=self.iso(10))              # before the check date
        self.assertEqual(self.run_cli("bet", "close", "old")[0], 1)
        self.assertIn("stays open", self.last_err)
        gtm.metric_add("ai:mention:comparison", 0.25)
        out = self.json_cli("bet", "close", "old")
        self.assertEqual(out["status"], "won")
        self.assertEqual(out["result"]["observed_by"], "metrics store")
        self.assertIn("directional", out["result"]["note"])

    def test_early_close_ignores_the_opening_day_value(self):
        self.run_cli("init")
        self.open()
        self.assertEqual(self.run_cli("bet", "close", "b1")[0], 1)                     # before the check date
        gtm.metric_add("ai:mention:comparison", 0.1)                                   # same day as opening
        self.assertEqual(self.run_cli("bet", "close", "b1", "--force")[0], 1)

    def test_hand_values_need_a_source(self):
        self.run_cli("init")
        self.past_bet()
        self.assertEqual(self.run_cli("bet", "close", "old", "--observed", "0.4")[0], 1)
        out = self.json_cli("bet", "close", "old", "--observed", "0.4", "--source", "posthog insight 123")
        self.assertEqual(out["result"]["observed_by"], "agent: posthog insight 123")

    def test_holdout_subtracts_a_control_measured_after_the_check(self):
        self.run_cli("init")
        self.past_bet(id="h", method="holdout", control_metric="ai:mention:category", control_baseline=0.1)
        gtm.metric_add("ai:mention:comparison", 0.25)
        self.assertEqual(self.run_cli("bet", "close", "h")[0], 1)                      # control not measured
        gtm.metric_add("ai:mention:category", 0.22)                                    # the tide rose too
        self.assertEqual(self.json_cli("bet", "close", "h")["status"], "inconclusive")  # 0.15 - 0.12 = 0.03

    def test_ab_from_counts_and_underpowered(self):
        self.run_cli("init")
        self.past_bet(id="ab", method="ab", baseline=0.05, expected=0.06)
        self.assertEqual(self.run_cli("bet", "close", "ab")[0], 1)                      # needs counts
        out = self.json_cli("bet", "close", "ab", "--a", "10000:500", "--b", "10000:600", "--source", "posthog exp 7")
        self.assertEqual(out["status"], "won")
        self.assertLess(out["result"]["observed"], 0.07)
        self.past_bet(id="ab2", method="ab", baseline=0.05, expected=0.06)
        out = self.json_cli("bet", "close", "ab2", "--a", "50:2", "--b", "50:9", "--source", "x")
        self.assertEqual(out["status"], "inconclusive")
        self.assertIn("underpowered", out["result"]["note"])

    def test_due_bets_appear_in_tick_and_learnings(self):
        self.run_cli("init")
        self.past_bet(method="holdout", control_metric="ai:mention:category", control_baseline=0.1)
        due = [j for j in self.tick()["due"] if j["job"] == "bet_close"]
        self.assertEqual(due[0]["event"], "old")
        gtm.metric_add("ai:mention:comparison", 0.4)
        gtm.metric_add("ai:mention:category", 0.1)
        self.assertEqual(self.json_cli("bet", "close", "old")["status"], "won")
        cands = self.json_cli("learnings")
        self.assertEqual(cands[0]["id"], "old")
        self.run_cli("learnings", "--accept", "old")
        self.assertEqual(self.json_cli("learnings"), [])


class MetricsAndDigestTest(Base):
    def test_metric_add_get_and_outbox(self):
        self.run_cli("init")
        self.run_cli("metric", "add", "stage:visit", "1200", "--source", "posthog")
        rows = self.json_cli("metric", "get", "stage:visit")
        self.assertEqual(rows[0]["value"], 1200)
        events = [json.loads(x) for x in (self.root / "posthog-outbox.jsonl").read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "marketing_metric")

    def test_digest_has_focus_tracks_and_monthly_fit_report(self):
        self.run_cli("init", "--motion", "enterprise", "--acv", "60000")
        self.write_run("2026-11-01", score({"brand": b(5, 0.2)}))
        code, out = self.run_cli("digest")
        self.assertEqual(code, 0)
        text = Path(out.strip()).read_text()
        self.assertIn("## Needs you", text)
        self.assertIn("Focus: measurement", text)
        self.assertIn("Not pursuing this month", text)
        self.assertIn("Short-form video", text)
        self.assertEqual(self.run_cli("digest")[0], 1)
        text2 = Path(self.run_cli("digest", "--force")[1].strip()).read_text()
        self.assertNotIn("Not pursuing this month", text2)              # once a month
        self.assertIn("Focus: measurement", self.run_cli("status")[1])


class ProfileTest(Base):
    def test_profile_changes_unconfirm_and_attention_is_validated(self):
        self.run_cli("init")
        self.json_cli("profile", "--confirm")
        self.assertTrue(self.state()["profile"]["confirmed"])
        p = self.json_cli("profile", "--motion", "enterprise", "--acv", "60000", "--attention", "short_video=0.1")
        self.assertFalse(p["confirmed"])
        self.assertEqual(p["attention"]["short_video"], 0.1)
        self.assertEqual(self.run_cli("profile", "--attention", "tiktok=0.1")[0], 1)
        self.assertEqual(self.run_cli("profile", "--attention", "outbound=2")[0], 1)
        self.assertTrue(self.json_cli("profile", "--confirm")["confirmed"])


class InitAndStageTest(Base):
    def test_force_keeps_kill_switch_budget_and_failures(self):
        self.run_cli("init", "--budget", "5")
        self.run_cli("record", "work_session", "--failed", "--key", "k")
        self.run_cli("pause")
        self.assertEqual(self.run_cli("init", "--force")[0], 1)          # paused: refuse
        self.run_cli("resume")
        self.run_cli("init", "--force")
        s = self.state()
        self.assertEqual(s["budget_usd_month"], 5)
        self.assertEqual(s["failures"]["work_session"]["k"], 1)

    def test_init_applies_explicit_flags_and_stage_moves_to_launch(self):
        self.run_cli("init", "--stage", "prelaunch")
        self.run_cli("init", "--budget", "40", "--site-url", "https://acme.com")
        s = self.state()
        self.assertEqual((s["budget_usd_month"], s["site_url"], s["stage"]), (40, "https://acme.com", "prelaunch"))
        self.assertEqual(self.tick()["focus"]["track"], "discoverability")
        self.run_cli("stage", "launched")
        self.assertEqual(self.state()["stage"], "launched")
        self.assertEqual(self.tick()["focus"]["track"], "measurement")


class RobustnessTest(Base):
    def test_disabled_measurement_is_never_the_focus(self):
        self.run_cli("init")
        self.edit(tracks__measurement__enabled=False)
        self.assertNotEqual(self.json_cli("focus")["track"], "measurement")

    def test_focus_reason_does_not_grow(self):
        self.run_cli("init")
        self.measured(visits=5000, signups=100, activated=25, paid=1, retained=1)
        self.edit(focus={"track": "demand", "since": self.iso(5), "basis": "earlier", "stage": "launched"})
        for _ in range(3):
            self.tick()
        self.assertEqual(self.state()["focus"]["basis"], "earlier")
        self.assertEqual(self.json_cli("focus")["reason"].count("holding"), 1)

    def test_digest_while_paused(self):
        self.run_cli("init")
        self.run_cli("pause", "--reason", "bad draft")
        code, out = self.run_cli("digest")
        self.assertEqual(code, 0, self.last_err)
        self.assertIn("PAUSED: bad draft", Path(out.strip()).read_text())


class MissingSkillsTest(Base):
    installed = {"ai-search-optimization", "entity-presence", "content", "citation-outreach", "comparison-pages",
                 "ai-visibility-audit", "gtm", "product-context", "writing"}

    def test_without_measurement_the_funnel_is_not_gated_and_tactics_skip_missing_skills(self):
        self.run_cli("init")
        f = self.json_cli("focus")
        self.assertEqual(f["track"], "discoverability")
        self.assertTrue(any("measurement" in n for n in f["notes"]))
        n = self.json_cli("next")
        skills = {t["skill"] for x in n["slots"] for t in x["tactics"]}
        self.assertTrue(skills <= self.installed)
        self.assertIn("measurement", n["skills_not_installed"])

    def test_metrics_recorded_by_hand_turn_the_gate_on(self):
        self.run_cli("init")
        gtm.metric_add("tracking_ok", 0)
        f = self.json_cli("focus")
        self.assertEqual(f["track"], "measurement")      # broken tracking is the truth, even with no skill for it
        self.assertEqual(f["skills"], [])                # so the work goes to a human via the digest
