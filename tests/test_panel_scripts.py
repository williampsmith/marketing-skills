"""Tests for the ai-visibility-audit scripts. Run: python3 -m unittest discover tests"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ai-visibility-audit" / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_panel = _load("run_panel")
score_panel = _load("score_panel")
PANEL = json.loads((ROOT / "skills/ai-visibility-audit/references/prompt-panel.example.json").read_text())


class Normalize(unittest.TestCase):
    def test_cloro_chatgpt_shape(self):
        body = {"success": True, "result": {
            "text": "short", "markdown": "Use **Acme Redact** or Acrobat. [FINRA](https://www.finra.org/x?utm_source=chatgpt.com)",
            "sources": [{"position": 1, "url": "https://www.reddit.com/r/legal/abc", "label": "r/legal"}],
            "citationPills": [{"url": "https://acmeredact.com/guide", "domain": "acmeredact.com"}],
            "searchQueries": ["best pdf redaction tool"],
            "html": "https://cdn.cloro.dev/results/abc/page-1.html"}}
        n = run_panel.normalize(body)
        self.assertIn("Acme Redact", n["text"])
        self.assertIn("https://www.reddit.com/r/legal/abc", n["sources"])
        self.assertIn("https://acmeredact.com/guide", n["sources"])
        self.assertTrue(any("finra.org" in u for u in n["sources"]))
        self.assertFalse(any("cdn.cloro.dev" in u for u in n["sources"]))
        self.assertEqual(n["fanout"], ["best pdf redaction tool"])

    def test_routed_perplexity_shape(self):
        body = {"output": {"answer": "Redactable is popular.", "sources": [{"url": "https://redactable.com/a"}]},
                "raw": {}, "_treg": {"served_by": "cloro"}}
        n = run_panel.normalize(body)
        self.assertEqual(n["text"], "Redactable is popular.")
        self.assertEqual(n["sources"], ["https://redactable.com/a"])

    def test_fill_template(self):
        out = run_panel._fill([{"user_prompt": "{prompt}", "c": "{country}"}], {"prompt": "hi \"x\"", "country": "US"})
        self.assertEqual(out, [{"user_prompt": 'hi "x"', "c": "US"}])


class Score(unittest.TestCase):
    def _answers(self):
        mk = lambda e, pid, text, src, b="category": {
            "engine": e, "prompt_id": pid, "bucket": b, "prompt": pid, "sample": 0, "text": text,
            "sources": src, "fanout": ["q " + pid]}
        return [
            mk("chatgpt", "p1", "Try Acrobat first, then Acme Redact.", ["https://www.acmeredact.com/x", "https://g2.com/y"]),
            mk("chatgpt", "p2", "Redactable and Adobe Acrobat are common.", ["https://reddit.com/r/a", "https://g2.com/z"]),
            mk("gemini", "p1", "acmeredact is fine.", []),
            mk("gemini", "p2", "Nothing specific.", []),
            # word boundary: must not count "Acrobatics" as Acrobat
            mk("gemini", "p3", "Acrobatics is unrelated.", []),
        ]

    def test_metrics(self):
        s = score_panel.score(self._answers(), PANEL)
        o = s["overall"]
        self.assertEqual(o["answers"], 5)
        self.assertAlmostEqual(o["mention_rate"], 0.4)
        self.assertAlmostEqual(o["citation_rate"], 0.2)
        self.assertEqual(s["by_engine"]["chatgpt"]["avg_rank_when_named"], 2)
        self.assertEqual(o["competitors"]["Adobe Acrobat"]["mention_rate"], 0.4)
        # g2 + reddit are cited where a competitor beat us; acmeredact is owned and excluded
        self.assertEqual(dict(s["citation_targets"]), {"reddit.com": 1, "g2.com": 1})
        self.assertEqual([g["prompt_id"] for g in s["gaps"]], ["p2"])
        self.assertEqual({a["prompt_id"] for a in s["no_tracked_brand"]}, {"p2", "p3"})

    def test_diff_and_report(self):
        cur = score_panel.score(self._answers(), PANEL)
        prev_answers = self._answers()
        prev_answers[2]["text"] = "Nothing."
        prev = json.loads(json.dumps(score_panel.score(prev_answers, PANEL)))
        d = score_panel.diff(cur, prev)
        self.assertEqual(d["won"], ["p1 on gemini"])
        self.assertEqual(d["lost"], [])
        md = score_panel.report(cur, d, "2026-10-31")
        self.assertIn("| chatgpt |", md)
        self.assertIn("Won 1, lost 0", md)

    def test_load_answers_keeps_last_success(self):
        with tempfile.TemporaryDirectory() as t:
            rows = [
                {"engine": "chatgpt", "prompt_id": "p1", "sample": 0, "error": "http 500", "prompt": "p1"},
                {"engine": "chatgpt", "prompt_id": "p1", "sample": 0, "error": None, "text": "ok", "prompt": "p1"},
            ]
            (Path(t) / "answers.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            got = score_panel.load_answers(Path(t))
            self.assertEqual(len(got), 1)
            self.assertEqual(got[0]["text"], "ok")


if __name__ == "__main__":
    unittest.main()
