"""Tests for the measurement scripts: PostHog flush/pull/tracking check, Search Console, the report.
No network: every HTTP and treg call is replaced. Run: python3 -m unittest discover tests"""
import datetime as dt
import json
import os
from pathlib import Path

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
ph = load("skills/measurement/scripts/posthog.py", "posthog_script")
sc = load("skills/measurement/scripts/search_console.py", "search_console")
report = load("skills/measurement/scripts/report.py", "report_script")


class FakeHTTP:
    def __init__(self, answers=None, fail_on=None):
        self.calls = []
        self.answers = answers or {}
        self.fail_on = fail_on

    def __call__(self, method, url, body=None, headers=None, timeout=60):
        self.calls.append({"method": method, "url": url, "body": body, "headers": headers})
        if self.fail_on and self.fail_on(len(self.calls), url, body):
            raise ph.PostHogError("boom")
        if url.endswith("/batch/"):
            return {"status": 1}
        q = body["query"]["query"]
        for needle, value in self.answers.items():
            if needle in q:
                return {"results": [[value]]}
        return {"results": [[None]]}


class PostHogTest(StoreCase):
    module = ph

    def setUp(self):
        super().setUp()
        self.saved = {k: os.environ.get(k) for k in ("POSTHOG_PROJECT_API_KEY", "POSTHOG_PERSONAL_API_KEY",
                                                     "POSTHOG_PROJECT_ID", "POSTHOG_HOST")}
        os.environ.update({"POSTHOG_PROJECT_API_KEY": "phc_test", "POSTHOG_PERSONAL_API_KEY": "phx_test",
                           "POSTHOG_PROJECT_ID": "42"})
        os.environ.pop("POSTHOG_HOST", None)
        self.real_http, self.real_fetch = ph.http, ph.fetch_page
        self.run_cli("init", module=gtm)

    def tearDown(self):
        ph.http, ph.fetch_page = self.real_http, self.real_fetch
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def stage_events(self):
        s = json.loads((gtm.R() / "gtm.json").read_text())
        s["measurement"] = {"stage_events": {"visit": "$pageview", "signup": "signed_up", "activated": "first_redaction"}}
        (gtm.R() / "gtm.json").write_text(json.dumps(s))

    def test_flush_sends_batches_without_personal_data_and_empties_the_outbox(self):
        for i in range(150):
            gtm.outbox("marketing_metric", {"metric": "x", "value": i, "contact_email": "a@b.c"})
        fake = FakeHTTP()
        ph.http = fake
        out = self.json_cli("flush")
        self.assertEqual(out["sent"], 150)
        self.assertEqual(len(fake.calls), 2)
        first = fake.calls[0]["body"]
        self.assertEqual(first["api_key"], "phc_test")
        self.assertTrue(fake.calls[0]["url"].startswith("https://us.i.posthog.com/batch/"))
        props = first["batch"][0]["properties"]
        self.assertNotIn("contact_email", props)
        self.assertTrue(props["distinct_id"].startswith("marketing-operator:"))
        self.assertEqual(gtm.read_jsonl(gtm.R() / "posthog-outbox.jsonl"), [])

    def test_failed_batch_keeps_the_unsent_rest(self):
        for i in range(150):
            gtm.outbox("marketing_metric", {"value": i})
        ph.http = FakeHTTP(fail_on=lambda n, url, body: n == 2)
        self.assertEqual(self.run_cli("flush")[0], 1)
        left = gtm.read_jsonl(gtm.R() / "posthog-outbox.jsonl")
        self.assertEqual(len(left), 50)
        self.assertEqual(left[0]["properties"]["value"], 100)

    def test_pull_writes_stage_counts_and_source_capture(self):
        self.stage_events()
        fake = FakeHTTP({"'$pageview'": 5000, "countIf": 0.84, "'signed_up'": 120, "'first_redaction'": 30})
        ph.http = fake
        out = self.json_cli("pull")
        got = {w["metric"]: w["value"] for w in out["written"]}
        self.assertEqual(got["stage:visit"], 5000)
        self.assertEqual(got["source_capture_rate"], 0.84)
        self.assertEqual(gtm.metric_latest("stage:signup")["value"], 120)
        self.assertEqual(fake.calls[0]["headers"]["Authorization"], "Bearer phx_test")
        self.assertIn("/api/projects/42/query/", fake.calls[0]["url"])

    def test_pull_needs_config_and_escapes_names(self):
        self.assertEqual(self.run_cli("pull")[0], 1)
        s = json.loads((gtm.R() / "gtm.json").read_text())
        s["measurement"] = {"stage_events": {"visit": "x' OR 1=1 --", "signup": "signed up"},
                            "source_properties": ["heard-from"]}
        (gtm.R() / "gtm.json").write_text(json.dumps(s))
        plan = self.json_cli("pull", "--dry-run")["would_query"]
        q = {p["metric"]: p["hogql"] for p in plan}
        self.assertIn("event = 'x\\' OR 1=1 --'", q["stage:visit"])
        self.assertIn("event = 'signed up'", q["stage:signup"])
        self.assertIn("person.properties['heard-from']", q["source_capture_rate"])

    def test_eu_host_and_missing_keys(self):
        os.environ["POSTHOG_HOST"] = "eu"
        self.assertEqual(ph.hosts()[1], "https://eu.posthog.com")
        os.environ["POSTHOG_HOST"] = "http://insecure"
        self.assertEqual(self.run_cli("query", "SELECT 1")[0], 1)
        os.environ.pop("POSTHOG_HOST")
        os.environ.pop("POSTHOG_PERSONAL_API_KEY")
        self.assertEqual(self.run_cli("query", "SELECT 1")[0], 1)
        self.assertIn("POSTHOG_PERSONAL_API_KEY", self.last_err)

    def test_tracking_check_is_decided_by_events_not_html(self):
        self.stage_events()
        ph.fetch_page = lambda url: "<html>bundled app, no inline snippet</html>"
        ph.http = FakeHTTP({"INTERVAL 2 DAY": 500})                     # events arriving: alive
        code, out = self.run_cli("tracking-check", "--url", "https://example.com")
        self.assertEqual(code, 0, self.last_err)
        self.assertEqual(gtm.metric_latest("tracking_ok")["value"], 1)
        self.assertIsNone(json.loads(out)["snippet_in_html"])          # not even fetched
        ph.http = FakeHTTP({"INTERVAL 2 DAY": 0})                       # silence: explain with the HTML
        code, out = self.run_cli("tracking-check", "--url", "https://example.com")
        self.assertEqual(code, 1)
        notes = json.loads(out)["notes"]
        self.assertTrue(any("no PostHog snippet" in n for n in notes))
        self.assertEqual(gtm.metric_latest("tracking_ok")["value"], 0)

    def test_quiet_first_step_is_not_broken(self):
        self.stage_events()
        ph.http = FakeHTTP({"WHERE timestamp": 300, "'signed_up'": 0})
        code, out = self.run_cli("tracking-check")
        self.assertEqual(code, 0)
        self.assertTrue(any("quiet product" in n for n in json.loads(out)["notes"]))

    def test_sync_runs_pull_when_flush_fails_and_reports_errors(self):
        self.stage_events()
        gtm.outbox("marketing_metric", {"metric": "x", "value": 1})
        os.environ.pop("POSTHOG_PROJECT_API_KEY")                        # capture key missing
        fake = FakeHTTP({"'$pageview'": 10})
        ph.http = fake
        code, out = self.run_cli("sync")
        self.assertEqual(code, 1)
        self.assertTrue(any("flush" in e for e in json.loads(out)["errors"]))
        self.assertEqual(gtm.metric_latest("stage:visit")["value"], 10)   # the pull still ran
        os.environ["POSTHOG_PROJECT_API_KEY"] = "phc_test"
        ph.http = FakeHTTP(fail_on=lambda n, url, body: "/query/" in url)
        code, out = self.run_cli("sync")
        self.assertEqual(code, 1)                                         # every query failed
        self.assertTrue(any(e.startswith("pull:") for e in json.loads(out)["errors"]))

    def test_network_errors_become_clean_failures(self):
        def timeout(*a, **k):
            raise ph.PostHogError("POST x → TimeoutError: timed out")
        ph.http = timeout
        self.assertEqual(self.run_cli("query", "SELECT 1")[0], 1)
        self.assertIn("TimeoutError", self.last_err)
        self.assertEqual(self.run_cli("check")[0], 1)

    def test_only_allowlisted_properties_leave_and_text_is_redacted(self):
        props = ph.clean("marketing_bet", {"id": "b1", "hypothesis": "jane@x.com said so", "status": "won",
                                           "result": {"effect": 0.1, "note": "x"}, "contact": "y"})
        self.assertEqual(set(props), {"id", "status", "result_effect"})
        self.assertEqual(ph.clean("marketing_metric", {"metric": "m", "source": "mail jane@x.com"})["source"],
                         "mail [email]")

    def test_ingestion_host_maps_to_app_host(self):
        os.environ["POSTHOG_HOST"] = "https://eu.i.posthog.com/"
        self.assertEqual(ph.hosts(), ("https://eu.i.posthog.com", "https://eu.posthog.com"))
        os.environ["POSTHOG_HOST"] = "EU"
        self.assertEqual(ph.hosts()[1], "https://eu.posthog.com")


class SearchConsoleTest(StoreCase):
    module = sc

    def setUp(self):
        super().setUp()
        self.run_cli("init", module=gtm)

    def fake_call(self, site, body):
        dims = body.get("dimensions")
        if not dims:
            return {"result": {"output": {"rows": [{"clicks": 900, "impressions": 20000}]}}}
        if dims == ["query"]:
            return {"result": {"output": {"rows": [
                {"keys": ["acme pricing"], "clicks": 300, "impressions": 900, "position": 1.2},
                {"keys": ["redact pdf"], "clicks": 200, "impressions": 4000, "position": 6.0},
                {"keys": ["remove text from pdf"], "clicks": 20, "impressions": 3000, "position": 14.0},
                {"keys": ["tiny"], "clicks": 0, "impressions": 3, "position": 2.0}]}}}
        return {"result": {"output": {"rows": [{"keys": ["https://acme.com/a"], "impressions": 5},
                                               {"keys": ["https://acme.com/b/"], "impressions": 1}]}}}

    def test_measure_brand_split_top10_and_index_proxy(self):
        out = sc.measure("sc-domain:acme.com", "https://acme.com", ["acme"], 28, call=self.fake_call,
                         sitemap=lambda u: ["https://acme.com/a", "https://acme.com/b", "https://acme.com/c", "https://acme.com/d"])
        self.assertEqual(out["search_clicks_28d"], 900)
        self.assertEqual(out["nonbrand_clicks_28d"], 220)
        self.assertEqual(out["query_top10_share"], 0.5)        # redact pdf in, remove text out, tiny ignored
        self.assertEqual(out["indexed_ratio"], 0.5)
        end = dt.date.fromisoformat(out["window"][1])
        self.assertEqual((dt.date.today() - end).days, sc.LAG_DAYS)

    def test_query_map_from_seo_skill_wins(self):
        (gtm.R() / "seo").mkdir()
        (gtm.R() / "seo" / "queries.csv").write_text("query,intent,page\nredact pdf,how,/r\npdf redaction tool,best,\n")
        out = sc.measure("sc-domain:acme.com", "", ["acme"], 28, call=self.fake_call, sitemap=lambda u: [])
        self.assertEqual(out["query_top10_share"], 0.5)
        self.assertEqual(out["top10_basis"], "query map")

    def test_cli_needs_a_property_and_brand_terms(self):
        self.assertEqual(self.run_cli()[0], 1)
        self.assertIn("property", self.last_err)
        self.json_cli("connect", "search_console", "sc-domain:acme.com", module=gtm)
        self.assertEqual(self.run_cli()[0], 1)
        self.assertIn("brand", self.last_err)

    def test_treg_errors_raise_and_write_nothing(self):
        class P:
            def __init__(self, code, out):
                self.returncode, self.stdout, self.stderr = code, out, ""
        real = sc.run_treg
        try:
            sc.run_treg = lambda argv: P(1, json.dumps({"error": {"status": 403}}))
            with self.assertRaises(RuntimeError):
                sc.treg_call("sc-domain:acme.com", {})
            sc.run_treg = lambda argv: P(0, json.dumps({"result": {"output": {"error": "quota"}}}))
            with self.assertRaises(RuntimeError):
                sc.treg_call("sc-domain:acme.com", {})
            seen = {}

            def ok(argv):
                seen["argv"] = argv
                return P(0, json.dumps({"result": {"output": {"responseAggregationType": "byProperty"}}}))
            sc.run_treg = ok
            sc.treg_call("sc-domain:acme.com", {"startDate": "x"})
            self.assertEqual(seen["argv"][:8], ["treg", "--json", "call", sc.ENDPOINT, "--method", "POST",
                                                 "--query", "siteUrl=sc-domain:acme.com"])
        finally:
            sc.run_treg = real

    def test_no_rows_is_no_data_not_zero(self):
        out = sc.measure("sc-domain:acme.com", "", ["acme"], 28, call=lambda site, body: {"result": {}},
                         sitemap=lambda u: [])
        self.assertIsNone(out["search_clicks_28d"])
        self.assertIsNone(out["nonbrand_clicks_28d"])


class ReportTest(StoreCase):
    module = report

    def test_report_renders_from_the_store(self):
        self.run_cli("init", module=gtm)
        for d, v in (("2026-10-01", 0.1), ("2026-10-08", 0.15), ("2026-10-15", 0.2)):
            gtm.metric_add("ai:mention", v, date=d)
        gtm.metric_add("stage:visit", 4000)
        code, out = self.run_cli("--days", "3650")
        self.assertEqual(code, 0)
        page = Path(out.strip()).read_text()
        self.assertIn("Growth scorecard", page)
        self.assertIn("Focus: ", page)
        self.assertIn("<svg", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)


class ConnectTest(StoreCase):
    module = gtm

    def test_measurement_jobs_wait_for_their_connections(self):
        self.run_cli("init")
        t = self.json_cli("tick")
        skipped = {j["job"]: j["skipped"] for j in t["skipped"]}
        self.assertIn("connect posthog", skipped["tracking_check"])
        self.assertIn("connect search_console", skipped["search_console"])
        self.json_cli("connect", "posthog")
        self.json_cli("connect", "search_console", "sc-domain:acme.com")
        due = [j["job"] for j in self.json_cli("tick")["due"]]
        self.assertIn("tracking_check", due)
        self.assertIn("metrics_sync", due)
        self.assertIn("search_console", due)
        self.assertNotIn("monthly_report", due)          # clock starts at init

    def test_revenue_source_is_validated(self):
        self.run_cli("init")
        self.assertEqual(self.json_cli("connect", "revenue", "events")["revenue_source"], "events")
        self.assertEqual(self.run_cli("connect", "revenue", "venmo")[0], 1)
        self.assertIsNone(self.json_cli("connect", "revenue", "none")["revenue_source"])
        self.assertFalse(self.json_cli("connect", "posthog", "off")["posthog"])
        self.assertEqual(self.run_cli("connect", "posthog", "false")[0], 1)
        self.assertEqual(self.run_cli("connect", "search_console", "acme.com")[0], 1)
