"""Tests for the news watch: normalisation, dedupe, scoring, budget, shelf lives, the sensitive-story gate
and gtm's news jobs. No network: run_treg and http_get_json are replaced. Run: python3 -m unittest discover tests"""
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
nw = load("skills/news/scripts/news_watch.py", "news_watch")

TODAY = dt.date.today()


def d(days_ago):
    return (TODAY - dt.timedelta(days=days_ago)).isoformat()


NEWS = {"results": [
    {"title": "Court filing improperly redacted: names readable after copy and paste", "url": "https://a.com/story?utm_source=x",
     "publisher": "Outlet A", "date": d(1), "snippet": "The PDF kept the text under black boxes."},
    {"title": "Court filing improperly redacted: names readable after copy and paste", "url": "https://b.com/s",
     "publisher": "Outlet B", "date": d(1)},
    {"title": "Agency releases redacted version of report", "url": "https://c.com/r", "publisher": "C",
     "date": d(2), "snippet": "redacted version released"},
    {"title": "Old unredacted documents story", "url": "https://d.com/old", "publisher": "D", "date": d(40)},
    {"title": "Weather tomorrow", "url": "https://e.com/w", "publisher": "E", "date": d(0)},
    {"title": "Victims named after unredacted court records leak", "url": "https://f.com/v", "publisher": "F", "date": d(0)},
]}
GNEWS = {"results": [
    {"title": "Court filing improperly redacted: names readable after copy and paste", "link": "https://www.a.com/story",
     "source": {"name": "Outlet A"}, "published_at": f"{d(1)} 07:00:00 UTC"},
]}
HN = {"rows": [{"title": "Unredacted: how hidden text survives in PDFs", "url": None, "hn_url": "https://news.ycombinator.com/item?id=1",
                "created": f"{d(3)}T10:00:00Z", "points": 300, "comments": 120}]}
X = {"posts": [{"id": "999", "text": "Lawyers keep filing improperly redacted PDFs", "authorUsername": "someone",
                "authorName": "Some One", "createdUtc": 0, "likeCount": 5}]}


class FakeTreg:
    def __init__(self, outputs, charge_micro=1000, fail=()):
        self.outputs, self.charge, self.fail, self.calls = outputs, charge_micro, set(fail), []

    def __call__(self, argv):
        endpoint = argv[3]
        body = json.loads(Path(argv[argv.index("--data") + 1][1:]).read_text())
        self.calls.append((endpoint, body, argv[-1]))
        if endpoint in self.fail:
            return subprocess.CompletedProcess(argv, 1, "", "boom")
        out = self.outputs[endpoint]
        routed = endpoint.startswith("treg.")
        res = {"output": out, "_treg": {"charged_micro": self.charge}} if routed else out
        return subprocess.CompletedProcess(argv, 0, json.dumps({"result": res, "_treg": {"charged_micro": self.charge}}), "")


OUTPUTS = {"treg.web.search.news": NEWS, "treg.google.serp.news": GNEWS,
           "crawl4ai.hackernews.search.stories": HN, "treg.x.search.posts": X}


class NewsCase(StoreCase):
    module = nw

    def setUp(self):
        super().setUp()
        self.run_cli("init", module=gtm)
        self.orig = (nw.run_treg, nw.http_get_json)
        self.fake = FakeTreg(OUTPUTS)
        nw.run_treg = self.fake

        def no_network(url, headers):
            raise AssertionError("tests must not reach the network")
        nw.http_get_json = no_network
        os.environ.pop("MARKETING_UNATTENDED", None)
        os.environ.pop("COURTLISTENER_TOKEN", None)

    def tearDown(self):
        nw.run_treg, nw.http_get_json = self.orig
        os.environ.pop("MARKETING_UNATTENDED", None)
        os.environ.pop("COURTLISTENER_TOKEN", None)
        super().tearDown()

    def setup_config(self, *sources):
        argv = ["init", "--query", "improperly redacted", "--term", "redacted", "--term", "redaction",
                "--signal", "unredacted", "--signal", "improperly redacted", "--signal", "copy and paste",
                "--exclude", "redacted version released"]
        for s in sources or ("news", "google_news", "hackernews"):
            argv += ["--source", s]
        self.json_cli(*argv)

    def queue(self):
        return {c["id"]: c for c in gtm.read_jsonl(gtm.R() / "news" / "candidates.jsonl")}


class SweepTest(NewsCase):
    def test_groups_syndicated_copies_drops_noise_and_queues_once(self):
        self.setup_config()
        out = self.json_cli("sweep")
        q = self.queue()
        titles = [c["title"] for c in q.values()]
        self.assertEqual(titles.count("Court filing improperly redacted: names readable after copy and paste"), 1)
        lead = next(c for c in q.values() if c["title"].startswith("Court filing"))
        self.assertEqual(lead["outlets"], ["Outlet A", "Outlet B"])          # two outlets, one story
        self.assertTrue(any(w.startswith("signals:") and "copy and paste" in w for w in lead["why"]), lead["why"])
        self.assertNotIn("Agency releases redacted version of report", titles)   # excluded phrase
        self.assertNotIn("Weather tomorrow", titles)                             # no category term
        self.assertNotIn("Old unredacted documents story", titles)               # older than max_age_days
        self.assertIn("Unredacted: how hidden text survives in PDFs", titles)    # Hacker News, via hn_url
        self.assertEqual(out["cost_usd"], 0.003)                                 # three calls at 1000 micro-dollars
        self.assertTrue((gtm.R() / "news" / f"{TODAY.isoformat()}.md").exists())
        again = self.json_cli("sweep")
        self.assertEqual(again["new"], 0)                                        # seen stories aren't offered twice
        self.assertEqual(len(self.queue()), len(q))

    def test_sensitive_stories_are_flagged(self):
        self.setup_config()
        self.json_cli("sweep")
        v = next(c for c in self.queue().values() if c["title"].startswith("Victims"))
        self.assertTrue(v["sensitive"])

    def test_budget_stops_before_the_cap_and_sets_a_ceiling_per_call(self):
        self.setup_config()
        # a call runs only if what's been charged plus its ceiling fits, so the cap holds even at worst case
        out = self.json_cli("sweep", "--max-usd", "0.005")
        self.assertEqual([c[0] for c in self.fake.calls], ["treg.google.serp.news", "crawl4ai.hackernews.search.stories"])
        self.assertEqual(out["skipped_for_budget"], ["news: improperly redacted (budget)"])  # its 0.01 ceiling > cap
        self.assertEqual(self.fake.calls[0][2], "X-Treg-Route-Max-Cost: 0.0050")
        self.assertLessEqual(out["cost_usd"], 0.005)

    def test_every_search_failing_is_an_error_not_a_quiet_week(self):
        self.setup_config("news")
        nw.run_treg = FakeTreg(OUTPUTS, fail={"treg.web.search.news"})
        code, out = self.run_cli("sweep")
        self.assertEqual(code, 1)
        self.assertIn("treg exited 1", out)
        nw.run_treg = FakeTreg(OUTPUTS, fail={"treg.web.search.news"})
        self.json_cli("init", "--source", "news", "--source", "hackernews")
        self.assertEqual(self.run_cli("sweep")[0], 0)              # one source down, the other worked

    def test_courtlistener_needs_a_token_and_never_blocks_the_rest(self):
        self.json_cli("init", "--court-query", '"inadvertently filed" unredacted')
        self.setup_config("news", "courtlistener")
        out = self.json_cli("sweep")
        self.assertTrue(any("COURTLISTENER_TOKEN" in e for e in out["errors"]))
        self.assertGreater(out["new"], 0)

    def test_courtlistener_rows_map_to_candidates(self):
        os.environ["COURTLISTENER_TOKEN"] = "t"
        seen = {}

        def fake_http(url, headers):
            seen["url"], seen["headers"] = url, headers
            return {"results": [{"caseName": "Doe v. Roe", "short_description": "Notice of errata: improperly redacted exhibit",
                                 "absolute_url": "/docket/1/2/doe-v-roe/", "court": "D.D.C.", "entry_date_filed": d(2),
                                 "snippet": "the exhibit was inadvertently filed unredacted"}]}
        nw.http_get_json = fake_http
        self.json_cli("init", "--court-query", '"inadvertently filed" unredacted', "--source", "courtlistener",
                      "--term", "redacted", "--signal", "improperly redacted")
        self.json_cli("sweep")
        c = next(iter(self.queue().values()))
        self.assertEqual(c["url"], "https://www.courtlistener.com/docket/1/2/doe-v-roe/")
        self.assertEqual(seen["headers"], {"Authorization": "Token t"})
        self.assertIn("type=rd", seen["url"])

    def test_dry_run_spends_nothing(self):
        self.setup_config()
        out = self.json_cli("sweep", "--dry-run")
        self.assertEqual(len(out["calls"]), 3)
        self.assertEqual(self.fake.calls, [])

    def test_config_is_validated(self):
        self.assertEqual(self.run_cli("sweep")[0], 1)                         # no news.json
        self.assertEqual(self.run_cli("init", "--source", "myspace")[0], 1)


class NormalizeTest(NewsCase):
    def test_x_keeps_no_handles(self):
        rows = nw.normalize("x", X, "q")
        self.assertEqual(rows[0]["url"], "https://x.com/i/status/999")
        self.assertNotIn("someone", json.dumps(rows))
        self.assertNotIn("Some One", json.dumps(rows))

    def test_dates(self):
        self.assertEqual(nw.parse_date("Sat, 01 Aug 2026 07:00:00 GMT"), dt.date(2026, 8, 1))
        self.assertEqual(nw.parse_date("2026-10-16 07:00:00 UTC"), dt.date(2026, 10, 16))
        self.assertEqual(nw.parse_date("2 weeks ago"), TODAY - dt.timedelta(days=14))
        noon = dt.datetime(2026, 8, 1, 12, tzinfo=dt.timezone.utc).timestamp()
        self.assertEqual(nw.parse_date(noon), dt.date(2026, 8, 1))
        self.assertIsNone(nw.parse_date("sometime"))

    def test_canonical_url_drops_tracking_and_www(self):
        self.assertEqual(nw.canonical_url("https://www.A.com/story/?utm_source=x&id=2#top"), "https://a.com/story?id=2")


class DecideTest(NewsCase):
    def put(self, **kw):
        c = {"id": "s1", "found": d(0), "status": "new", "score": 0.8, "why": [], "sensitive": False,
             "title": "t", "url": "https://a.com", "outlets": [], "sources": ["news"], "published": d(0),
             "snippet": "", "query": "q", "react_by": d(-3), "pitch_by": d(-7), "also": []}
        c.update(kw)
        (gtm.R() / "news").mkdir(parents=True, exist_ok=True)
        gtm.write_jsonl(gtm.R() / "news" / "candidates.jsonl", [c])

    def test_windows_close(self):
        self.put(react_by=d(1), pitch_by=d(-2))
        self.assertEqual(self.run_cli("decide", "s1", "--as", "react")[0], 1)
        self.assertIn("too late", self.last_err)
        self.assertEqual(self.json_cli("decide", "s1", "--as", "pitch")["status"], "pitch")

    def test_refresh_names_a_page_and_never_expires(self):
        self.put(react_by=d(30), pitch_by=d(30))
        self.assertEqual(self.run_cli("decide", "s1", "--as", "refresh")[0], 1)
        self.assertEqual(self.json_cli("decide", "s1", "--as", "refresh", "--page", "how-redaction-fails")["page"],
                         "how-redaction-fails")

    def test_sensitive_reaction_needs_a_quoted_human_and_never_runs_unattended(self):
        self.put(sensitive=True)
        self.assertEqual(self.run_cli("decide", "s1", "--as", "react")[0], 1)
        os.environ["MARKETING_UNATTENDED"] = "1"
        self.assertEqual(self.run_cli("decide", "s1", "--as", "react", "--quote", "ok go")[0], 1)
        self.assertIn("unattended", self.last_err)
        self.assertEqual(self.json_cli("decide", "s1", "--as", "refresh", "--page", "p")["status"], "refresh")
        os.environ.pop("MARKETING_UNATTENDED")
        self.put(sensitive=True)
        self.assertEqual(self.json_cli("decide", "s1", "--as", "react", "--quote", "yes, post it")["quote"], "yes, post it")


class GtmJobsTest(NewsCase):
    def tick(self):
        return self.json_cli("tick", module=gtm)

    def test_news_watch_waits_for_config_and_news_act_follows_new_candidates(self):
        t = self.tick()
        self.assertIn("news_watch", [j["job"] for j in t["skipped"]])
        self.setup_config()
        self.assertIn("news_watch", [j["job"] for j in self.tick()["due"]])
        self.json_cli("sweep")
        act = [j for j in self.tick()["due"] if j["job"] == "news_act"]
        self.assertEqual(len(act), 1)
        self.assertEqual(act[0]["event"], TODAY.isoformat())
        self.run_cli("record", "news_act", "--event", act[0]["event"], module=gtm)
        self.assertNotIn("news_act", [j["job"] for j in self.tick()["due"]])

    def test_disabled_news_watch_silences_news_act(self):
        self.setup_config()
        self.json_cli("sweep")
        s = json.loads((gtm.R() / "gtm.json").read_text())
        s["jobs"]["news_watch"]["enabled"] = False
        (gtm.R() / "gtm.json").write_text(json.dumps(s))
        self.assertNotIn("news_act", [j["job"] for j in self.tick()["due"]])


class TuningTest(NewsCase):
    def test_terms_match_word_endings_and_sensitive_words_match_exactly(self):
        cfg = {**nw.DEFAULT_CONFIG, "terms": ["redact"], "signals": ["unredact"], "exclude": []}
        row = {"title": "Botched redactions expose data center figures", "snippet": "", "published": d(0),
               "engagement": 0, "source": "news"}
        sc, why, sens = nw.score(row, cfg, 1)
        self.assertGreater(sc, 0)
        self.assertFalse(sens)
        sc, why, sens = nw.score({**row, "title": "Hackers unredact files about minority hiring"}, cfg, 1)
        self.assertTrue(any(w.startswith("signals") for w in why))
        self.assertFalse(sens)                                    # "minority" isn't "minor"

    def test_x_replies_and_quiet_posts_are_dropped_and_posts_rank_below_reporting(self):
        posts = {"posts": [
            {"id": "1", "text": "@someone improperly redacted again", "likeCount": 500},
            {"id": "2", "text": "Court filing improperly redacted, names visible", "isReply": True, "likeCount": 500},
            {"id": "3", "text": "Another improperly redacted filing today", "likeCount": 2, "createdUtc": 0},
            {"id": "4", "text": "Court filing improperly redacted today, names visible", "likeCount": 40,
             "createdUtc": dt.datetime.now(dt.timezone.utc).timestamp()},
        ]}
        self.assertEqual([r["url"][-1] for r in nw.normalize("x", posts, "q")], ["3", "4"])
        nw.run_treg = FakeTreg({**OUTPUTS, "treg.x.search.posts": posts})
        self.setup_config("x")
        out = self.json_cli("sweep")
        self.assertEqual([c["title"][:10] for c in self.queue().values()], ["Court fili"])
        cfg = nw.load_config()
        row = {"title": "Court filing improperly redacted", "snippet": "", "published": d(0), "engagement": 0}
        self.assertLess(nw.score({**row, "source": "x"}, cfg, 1)[0], nw.score({**row, "source": "news"}, cfg, 1)[0])
