"""Tests for the writing skill's claims_guard.py. Run: python3 -m unittest discover tests"""
import json
from pathlib import Path

from helpers import StoreCase, load

guard = load("skills/writing/scripts/claims_guard.py", "claims_guard")

LEDGER = """# Claims ledger — Acme — verified 2026-11-01 against abc123

## OK to claim
| claim (as it may appear in copy) | evidence | notes / required qualifier |
|---|---|---|
| Files are processed on your device and never uploaded | src/server.ts binds to localhost | except the license check, which sends no file data |
| Checks every export and refuses to save one that fails | checkExport() in src/export/verify.ts | covers only the areas the user marked |
| Exports a 100-page PDF in under 30 seconds | bench/export.test.ts | on an M2 laptop |

## Never claim (not shipped / not true)
| claim | why |
|---|---|
| The fastest redaction tool | no benchmark against competitors |
"""


class GuardTest(StoreCase):
    module = guard

    def setUp(self):
        super().setUp()
        self.claims = self.base / "claims.md"
        self.claims.write_text(LEDGER)

    def page(self, text, name="page.md"):
        p = self.base / name
        p.write_text(text)
        return str(p)

    def check(self, text, *extra):
        code, out = self.run_cli(self.page(text), "--claims", str(self.claims), "--json", *extra)
        return code, json.loads(out)

    def test_covered_claim_passes_with_its_row(self):
        code, res = self.check("Your files are never uploaded: they are processed on your device.")
        self.assertEqual(code, 0)
        f = res["findings"][0]
        self.assertEqual(f["status"], "covered")
        self.assertIn("never uploaded", f["row"])
        self.assertIn("license check", f["qualifier"])

    def test_superlative_without_a_row_is_unsupported(self):
        code, res = self.check("Acme is the fastest redaction tool on the market.")
        self.assertEqual(code, 1)
        f = res["findings"][0]
        self.assertEqual(f["status"], "unsupported")
        self.assertIn("risky", f["kinds"])
        self.assertIn("fastest", f["terms"])

    def test_numbers_must_appear_in_the_row(self):
        self.assertEqual(self.check("Acme exports a 100-page PDF in under 30 seconds.")[0], 0)
        code, res = self.check("Acme exports a 100-page PDF in under 10 seconds.")
        self.assertEqual(code, 1)
        self.assertEqual(res["findings"][0]["status"], "unsupported")

    def test_years_alone_are_not_claims(self):
        code, res = self.check("We started building Acme in 2024.")
        self.assertEqual(code, 0)
        self.assertEqual(res["findings"], [])

    def test_banned_phrase_fails_even_without_a_claim(self):
        code, res = self.check("Unlock the power of private document workflows.")
        self.assertEqual(code, 1)
        self.assertEqual(res["findings"][0]["status"], "banned")
        self.assertIn("unlock the power", res["findings"][0]["banned"])

    def test_competitor_comparison_is_flagged(self):
        code, res = self.check("Acme is easier to set up than Adobe Acrobat.", "--competitor", "Adobe Acrobat")
        self.assertEqual(code, 1)
        f = res["findings"][0]
        self.assertIn("comparison", f["kinds"])
        self.assertIn("Adobe Acrobat", f["terms"])
        # naming a competitor without comparing is fine
        self.assertEqual(self.check("Acme opens files exported from Adobe Acrobat.", "--competitor", "Adobe Acrobat")[1]["findings"], [])

    def test_overused_is_reported_but_does_not_fail(self):
        code, res = self.check("A powerful editor. A powerful viewer.")
        self.assertEqual(code, 0)
        self.assertEqual(res["overused"][0]["phrase"], "powerful")

    def test_json_shape_and_html_input(self):
        code, res = self.check("<html><body><h1>Hi</h1><p>The only tool you need.</p>"
                               "<script>var x = 100;</script></body></html>")
        for k in ("findings", "overused", "summary", "ok", "ledger_rows", "claims_path", "competitors"):
            self.assertIn(k, res)
        self.assertEqual(res["ledger_rows"], 3)
        self.assertEqual(res["summary"]["unsupported"], 1)
        self.assertFalse(res["ok"])
        self.assertEqual(code, 1)

    def test_defaults_come_from_the_store(self):
        root = guard.state_root()
        (root / "claims.md").write_text(LEDGER)
        (root / "product-context.md").write_text("## Positioning\n- **Alternatives:** Redactable, Adobe Acrobat, do nothing\n")
        code, out = self.run_cli(self.page("Acme is cheaper than Redactable."), "--json")
        res = json.loads(out)
        self.assertEqual(res["claims_path"], str(root / "claims.md"))
        self.assertEqual(res["competitors"], ["Redactable", "Adobe Acrobat"])
        self.assertEqual(code, 1)
        self.assertIn("comparison", res["findings"][0]["kinds"])

    def test_missing_ledger_and_bad_input(self):
        code, out = self.run_cli(self.page("The best tool."), "--claims", str(self.base / "none.md"))
        self.assertEqual(code, 1)
        self.assertIn("no OK rows", out)
        self.assertEqual(self.run_cli(str(self.base / "missing.md"), "--claims", str(self.claims))[0], 2)
