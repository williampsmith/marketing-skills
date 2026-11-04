"""Tests for launch-video's wrapper around HyperFrames: release facts from git, the command policy
(pin, telemetry off, local-only media, refused cloud and paid commands), the copy check and the
content-pinned render approval. No process is started: `video.run` is replaced, nothing downloads.
Run: python3 -m unittest discover tests"""
import json
import os
import subprocess
from pathlib import Path

from helpers import StoreCase, load

gtm = load("skills/gtm/scripts/gtm.py", "gtm")
video = load("skills/launch-video/scripts/video.py", "video")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})


class VideoCase(StoreCase):
    module = video

    def setUp(self):
        super().setUp()
        self.saved = os.environ.pop("MARKETING_UNATTENDED", None)
        self.run_cli("init", module=gtm)
        self.calls = []
        self.real_run = video.run
        video.run = lambda cmd, cwd=None, env=None: self.calls.append({"cmd": cmd, "cwd": cwd, "env": env}) or 0

    def tearDown(self):
        video.run = self.real_run
        if self.saved is not None:
            os.environ["MARKETING_UNATTENDED"] = self.saved
        super().tearDown()

    def new(self, slug="batch-export"):
        out = self.json_cli("new", slug)
        p = Path(out["project"])
        (p / "video" / "compositions").mkdir(parents=True)
        (p / "video" / "index.html").write_text(
            '<div data-composition-id="root" data-duration="20"><h1 data-var-text="Export a whole case at once">'
            'Export a whole case at once</h1><script>window.__timelines = {}; var x = "not copy";</script>'
            '<style>.a{color:red}</style><img src="assets/ui.png" alt="The batch export dialog"></div>')
        return p


class FactsTest(VideoCase):
    def test_merged_and_squashed_prs_between_tags(self):
        repo = self.product
        (repo / "a.txt").write_text("1")
        git("add", ".", cwd=repo)
        git("commit", "-q", "-m", "initial", cwd=repo)
        git("tag", "v1.0.0", cwd=repo)
        (repo / "b.txt").write_text("2")
        git("add", ".", cwd=repo)
        git("commit", "-q", "-m", "Add batch export (#12)", cwd=repo)
        git("checkout", "-q", "-b", "feature", cwd=repo)
        (repo / "c.txt").write_text("3")
        git("add", ".", cwd=repo)
        git("commit", "-q", "-m", "wip", cwd=repo)
        git("checkout", "-q", "-", cwd=repo)
        git("merge", "-q", "--no-ff", "feature", "-m", "Merge pull request #13 from acme/feature\n\nRedact by search term",
            cwd=repo)
        out = self.json_cli("facts", "--since", "v1.0.0", "--out", str(self.base / "launch"))
        self.assertEqual(out["changes"], 2)
        f = json.loads((self.base / "launch" / "facts.json").read_text())
        self.assertEqual([(c["pr"], c["title"]) for c in f["changes"]],
                         [(13, "Redact by search term"), (12, "Add batch export")])
        self.assertIn("#12: Add batch export", (self.base / "launch" / "facts.md").read_text())

    def test_bad_ref_is_an_error_not_an_empty_list(self):
        code, _ = self.run_cli("facts", "--since", "nope", "--out", str(self.base / "x"))
        self.assertEqual(code, 1)


class PolicyTest(VideoCase):
    def test_new_sets_up_a_safe_folder(self):
        p = self.new()
        self.assertTrue(str(p).startswith(str(gtm.R() / "launches")))
        self.assertIn("renders/", (p / ".gitignore").read_text())
        self.assertTrue((p / "brief.md").exists())
        self.assertEqual(json.loads((p / ".hyperframes" / "credit-limit.json").read_text()), {"credits": 0})
        self.assertEqual(self.run_cli("new", "Bad Slug!")[0], 1)

    def test_every_command_is_pinned_with_telemetry_and_skill_fetching_off(self):
        p = self.new()
        self.assertEqual(self.run_cli("hf", str(p), "--", "check", "--json")[0], 0)
        c = self.calls[-1]
        self.assertEqual(c["cmd"][:3], ["npx", "-y", f"hyperframes@{video.PIN}"])
        self.assertEqual(c["cwd"], p / "video")
        self.assertEqual(c["env"], {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HYPERFRAMES_SKIP_SKILLS": "1"})
        # the HyperFrames project itself gets the zero credit limit
        self.assertEqual(json.loads((p / "video" / ".hyperframes" / "credit-limit.json").read_text()), {"credits": 0})

    def test_init_runs_in_the_launch_folder(self):
        out = self.json_cli("new", "fresh")
        self.run_cli("hf", out["project"], "--", "init", "video", "--non-interactive")
        self.assertEqual(self.calls[-1]["cwd"], Path(out["project"]))

    def test_cloud_paid_and_account_commands_are_refused(self):
        p = self.new()
        for args in (["auth", "login"], ["cloud", "render"], ["lambda", "deploy"], ["publish"], ["upgrade"],
                     ["feedback", "--search-miss", "x"], ["media-use", "generate", "--type", "voice"],
                     ["media-use", "resolve", "--type", "bgm", "--provider", "heygen"], ["open"]):
            code, _ = self.run_cli("hf", str(p), "--", *args)
            self.assertEqual(code, 3, args)
        self.assertEqual(self.calls, [])

    def test_media_is_local_only_and_capture_skips_ai_captioning(self):
        p = self.new()
        self.run_cli("hf", str(p), "--", "media-use", "resolve", "--type", "sfx", "--intent", "click")
        self.assertEqual(self.calls[-1]["cmd"][-1], "--local-only")
        self.run_cli("hf", str(p), "--", "capture", "https://example.com")
        self.assertEqual(self.calls[-1]["cmd"][-1], "--skip-vision")

    def test_model_download_needs_a_yes(self):
        p = self.new()
        self.assertEqual(self.run_cli("hf", str(p), "--", "catalog", "--query", "x", "--on-device")[0], 3)
        self.assertEqual(self.run_cli("hf", str(p), "--allow-download", "--", "catalog", "--query", "x", "--on-device")[0], 0)

    def test_a_real_render_needs_an_approval_of_these_exact_files(self):
        p = self.new()
        self.assertEqual(self.run_cli("hf", str(p), "--", "render", "--quality", "draft")[0], 0)
        self.assertEqual(self.run_cli("hf", str(p), "--", "render", "--output", "out.mp4")[0], 3)  # default = looks
        self.assertIn("approval", self.last_err)
        self.assertEqual(self.run_cli("approve", str(p), "--quote", "looks good, render it")[0], 0, self.last_err)
        self.assertTrue(json.loads(self.run_cli("status", str(p))[1])["approved"])
        self.assertEqual(self.run_cli("hf", str(p), "--", "render", "--quality=delivery")[0], 0, self.last_err)
        # renders, snapshots and caches don't change what was approved; the composition does
        (p / "video" / "renders").mkdir()
        (p / "video" / "renders" / "x.mp4").write_bytes(b"\0")
        self.assertTrue(json.loads(self.run_cli("status", str(p))[1])["approved"])
        (p / "video" / "index.html").write_text("<h1>Now 10x faster</h1>")
        self.assertEqual(self.run_cli("hf", str(p), "--", "render", "--quality", "delivery")[0], 3)
        self.assertIn("changed since", self.last_err)

    def test_approval_rules_are_gtms(self):
        p = self.new()
        os.environ["MARKETING_UNATTENDED"] = "1"
        try:
            self.assertEqual(self.run_cli("approve", str(p), "--quote", "ok")[0], 1)
        finally:
            os.environ.pop("MARKETING_UNATTENDED")
        self.run_cli("approvers", "add", "slack:U1", "--quote", "me", module=gtm)
        self.assertEqual(self.run_cli("approve", str(p), "--quote", "ok")[0], 1)
        self.assertEqual(self.run_cli("approve", str(p), "--quote", "ok", "--approver", "slack:U1",
                                      "--source", "https://x/1")[0], 0)
        row = gtm.read_jsonl(gtm.R() / "approvals.jsonl")[-1]
        self.assertEqual((row["approver"], row["video"]), ("slack:U1", str(p)))
        self.assertEqual(gtm.approved_hashes("anything"), set())  # batch lookups skip video rows


class CopyTest(VideoCase):
    def test_copy_collects_what_viewers_see_and_hear(self):
        p = self.new()
        brief = (p / "brief.md").read_text().replace(
            "<one line per beat; every product claim matches an OK row in claims.md>",
            "Redact a whole case in one pass.")
        (p / "brief.md").write_text(brief)
        text = video.copy_text(p)
        self.assertIn("Export a whole case at once", text)
        self.assertIn("The batch export dialog", text)
        self.assertIn("Redact a whole case in one pass.", text)
        self.assertNotIn("not copy", text)
        self.assertNotIn("color:red", text)

    def test_copy_runs_the_claims_guard(self):
        p = self.new()
        (p / "video" / "index.html").write_text("<h1>The fastest and only 100% secure redaction tool</h1>")
        (gtm.R() / "claims.md").write_text("# Claims\n\n## OK to claim\n\n| claim | evidence |\n|---|---|\n")
        (gtm.R() / "product-context.md").write_text("# Product\n")
        rc, _ = self.run_cli("copy", str(p))  # the guard runs as a real, offline subprocess
        self.assertEqual(rc, 1)
        self.assertIn("fastest", (p / "copy.txt").read_text())
