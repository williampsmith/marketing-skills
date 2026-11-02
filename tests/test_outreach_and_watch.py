"""Tests for outreach_targets.py and watch_pages.py. Run: python3 -m unittest discover tests"""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


targets = _load("skills/citation-outreach/scripts/outreach_targets.py", "outreach_targets")
watch = _load("skills/competitive-intel/scripts/watch_pages.py", "watch_pages")
PANEL = json.loads((ROOT / "skills/ai-visibility-audit/references/prompt-panel.example.json").read_text())


def ans(engine, pid, text, sources, bucket="category"):
    return {"engine": engine, "prompt_id": pid, "bucket": bucket, "text": text, "sources": sources, "error": None}


class Targets(unittest.TestCase):
    def test_ranking_and_exclusions(self):
        answers = [
            # lost on two engines, cites a listicle and reddit; adobe.com is a competitor domain
            ans("chatgpt", "p1", "Use Adobe Acrobat.", ["https://www.listicle.com/best?utm_source=chatgpt.com", "https://adobe.com/x"]),
            ans("gemini", "p1", "Acrobat is standard.", ["https://listicle.com/best", "https://reddit.com/r/law/1"]),
            # won: cited pages here get no "lost" credit
            ans("chatgpt", "p2", "Acme Redact works offline.", ["https://won.com/a", "https://acmeredact.com/g"]),
            ans("chatgpt", "p3", "error row", [], "brand") | {"error": "http 500"},
        ]
        got = {t["url"]: t for t in targets.build(answers, PANEL)}
        self.assertNotIn("https://adobe.com/x", got)
        self.assertNotIn("https://acmeredact.com/g", got)
        best = got["https://listicle.com/best"]  # utm stripped, www dropped, merged
        self.assertEqual(best["citations"], 2)
        self.assertEqual(best["engines"], ["chatgpt", "gemini"])
        self.assertEqual(best["lost_prompts"], ["p1"])
        self.assertEqual(best["competitors_named"], {"Adobe Acrobat": 2})
        self.assertGreater(best["score"], got["https://reddit.com/r/law/1"]["score"])
        self.assertEqual(got["https://reddit.com/r/law/1"]["kind"], "forum")
        self.assertEqual(got["https://won.com/a"]["lost_prompts"], [])

    def test_kind(self):
        self.assertEqual(targets.kind("https://www.g2.com/products/x"), "directory")
        self.assertEqual(targets.kind("https://www.youtube.com/watch?v=1"), "video")
        self.assertEqual(targets.kind("https://csrc.nist.gov/pubs"), "gov_or_standard")
        self.assertEqual(targets.kind("https://blog.example.com/post"), "editorial")


class Watch(unittest.TestCase):
    def test_normalize_drops_noise_and_blank_lines(self):
        t = watch.normalize("  Pricing   $10/mo \n\n© 2026 Foo. All rights reserved\nAccept cookies\nPlan B")
        self.assertEqual(t, "Pricing $10/mo\nPlan B")

    def test_mention_is_word_bounded(self):
        self.assertTrue(watch.mention("we like Acrobat.", "acrobat"))
        self.assertFalse(watch.mention("acrobatics", "Acrobat"))

    def test_id_is_stable(self):
        self.assertEqual(watch.wid("https://x.com/a"), watch.wid("https://x.com/a"))
        self.assertNotEqual(watch.wid("https://x.com/a"), watch.wid("https://x.com/b"))


if __name__ == "__main__":
    unittest.main()
