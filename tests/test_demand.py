"""Tests for the demand-phase scripts: SEO crawl, attention weights. No network. Run: python3 -m unittest discover tests"""
import json

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
crawl = load("skills/seo/scripts/crawl_check.py", "crawl_check")
attention = load("skills/customer-research/scripts/attention.py", "attention")

WORDS = " ".join(["word"] * 200)


def page(title, desc="A page.", extra="", body=WORDS, links=()):
    a = "".join(f'<a href="{h}">x</a>' for h in links)
    return (f"<html><head><title>{title}</title><meta name='description' content='{desc}'>{extra}</head>"
            f"<body>{body}{a}</body></html>")


SITE = {
    "https://acme.com/robots.txt": (200, {}, "User-agent: *\nDisallow: /private\n"),
    "https://acme.com/sitemap.xml": (200, {}, "<sitemapindex><sitemap><loc>https://acme.com/s1.xml</loc></sitemap></sitemapindex>"),
    "https://acme.com/s1.xml": (200, {}, "<urlset>" + "".join(f"<url><loc>https://acme.com{p}</loc></url>" for p in
                                ("/", "/a", "/b", "/old", "/private/x", "/thin", "/dupe1", "/dupe2")) + "</urlset>"),
    "https://acme.com/": (200, {}, page("Home", links=("/a", "/b", "/thin", "/dupe1", "/dupe2", "/missing"))),
    "https://acme.com/a": (200, {}, page("A", extra="<meta name='robots' content='noindex'>")),
    "https://acme.com/b": (200, {}, page("B", extra="<link rel='canonical' href='https://acme.com/a'>")),
    "https://acme.com/old": (301, {"location": "/older"}, ""),
    "https://acme.com/older": (301, {"location": "/a"}, ""),
    "https://acme.com/private/x": (200, {}, page("Private")),
    "https://acme.com/thin": (200, {}, page("Thin", body="<div id=root></div>")),
    "https://acme.com/dupe1": (200, {}, page("Same title", desc="Same")),
    "https://acme.com/dupe2": (200, {"x-robots-tag": "noindex"}, page("Same title", desc="Same")),
    "https://acme.com/missing": (404, {}, ""),
}


def fake(url):
    return SITE.get(url, (404, {}, ""))


class CrawlTest(StoreCase):
    module = crawl

    def test_finds_the_problems_that_block_indexing(self):
        out = crawl.crawl("https://acme.com", fetcher=fake, delay=0)
        kinds = {(p["url"].replace("https://acme.com", "") or "/", p["kind"]) for p in out["problems"]}
        self.assertEqual(out["pages"], 8)
        for expected in [("/a", "noindex"), ("/b", "canonical"), ("/old", "redirect_chain"),
                         ("/private/x", "robots"), ("/thin", "thin_html"), ("/dupe1", "duplicate_title"),
                         ("/dupe2", "noindex"), ("/missing", "broken_link"), ("/private/x", "orphan")]:
            self.assertIn(expected, kinds)
        self.assertNotIn(("/", "orphan"), kinds)
        self.assertNotIn(("/a", "orphan"), kinds)


class AttentionTest(StoreCase):
    module = attention

    def test_weights_relative_to_the_best_channel_with_floor_and_minimum_sample(self):
        ev = {"sources": {"linkedin": {"sampled": 40, "relevant": 20}, "reddit": {"sampled": 40, "relevant": 10},
                          "g2": {"sampled": 20, "relevant": 15}, "tiktok": {"sampled": 30, "relevant": 0},
                          "youtube": {"sampled": 5, "relevant": 4}, "myspace": {"sampled": 50, "relevant": 9}}}
        res = attention.weights(ev)
        w = {k: v["weight"] for k, v in res["weights"].items()}
        self.assertEqual(w["review_communities"], 1.0)        # g2 75% is the best share
        self.assertEqual(w["linkedin_organic"], 0.67)
        self.assertEqual(w["short_video"], 0.05)
        self.assertIn("long_video", res["unmeasured"])
        self.assertIn("myspace", res["unmeasured"])

    def test_apply_writes_profile_and_unconfirms(self):
        self.run_cli("init", module=gtm)
        self.json_cli("profile", "--confirm", module=gtm)
        f = self.base / "ev.json"
        f.write_text(json.dumps({"date": "2026-11-12", "sources": {"linkedin": {"sampled": 40, "relevant": 20},
                                                                   "tiktok": {"sampled": 40, "relevant": 1}}}))
        out = self.json_cli(str(f), "--apply")
        self.assertTrue(out["applied"])
        prof = json.loads((gtm.R() / "gtm.json").read_text())["profile"]
        self.assertEqual(prof["attention"]["short_video"], 0.05)
        self.assertFalse(prof["confirmed"])
