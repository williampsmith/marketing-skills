"""Tests for creative/scripts/review_page.py. Run: python3 -m unittest discover tests"""
import json
from pathlib import Path

from helpers import StoreCase, load

review = load("skills/creative/scripts/review_page.py", "review_page")


class ReviewPageTest(StoreCase):
    module = review

    def batch(self, assets):
        d = self.base / "home" / "product" / "creative" / "2026-11-12-hooks"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps(assets))
        return d

    def asset(self, **kw):
        a = {"id": "hook-01", "file": "hook-01.mp4", "channel": "short_video", "format": "ugc_hook",
             "claim_row": "Checks every export", "script": "Line one.", "disclosure": "AI-generated presenter",
             "cost_usd": 0.86}
        a.update(kw)
        return a

    def test_page_is_written_escaped_and_self_contained(self):
        d = self.batch([self.asset(script="<script>alert(1)</script> & more"),
                        self.asset(id="still-02", file="still-02.png", ai_generated=False, disclosure="")])
        code, out = self.run_cli(str(d))
        self.assertEqual(code, 0, self.last_err)
        page = Path(out.strip()).read_text()
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; more", page)
        self.assertNotIn("<script>alert", page)
        self.assertIn('<video src="hook-01.mp4"', page)
        self.assertIn('<img src="still-02.png"', page)
        self.assertIn("approve creative 2026-11-12-hooks: &lt;ids&gt;", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)

    def test_missing_claim_or_disclosure_is_refused(self):
        d = self.batch([self.asset(claim_row=""), self.asset(id="hook-02", disclosure=None)])
        code, _ = self.run_cli(str(d))
        self.assertEqual(code, 1)
        self.assertIn("hook-01: no claim_row", self.last_err)
        self.assertIn("hook-02: AI-generated media needs a disclosure", self.last_err)
        self.assertFalse((d / "review.html").exists())

    def test_bad_manifest(self):
        d = self.batch([])
        self.assertEqual(self.run_cli(str(d))[0], 1)


class ReviewPageRefusalTest(StoreCase):
    module = review

    def test_remote_files_duplicate_ids_and_bad_costs_are_refused(self):
        d = self.base / "batch"
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps([
            {"id": "a", "file": "https://evil.example/x.png", "claim_row": "r", "disclosure": "AI"},
            {"id": "a", "file": "a.png", "claim_row": "r", "disclosure": "AI"},
            {"id": "b", "file": "../../etc/x.png", "claim_row": "r", "disclosure": "AI", "cost_usd": "lots"}]))
        self.assertEqual(self.run_cli(str(d))[0], 1)
        for needle in ("relative path", "duplicate id", "cost_usd"):
            self.assertIn(needle, self.last_err)
