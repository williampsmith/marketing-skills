"""Tests for marketing_state.py and gtm.py store/sync/migrate. Run: python3 -m unittest discover tests"""
import json
import os
import subprocess
from pathlib import Path

from helpers import StoreCase, load

ms = load("skills/gtm/scripts/marketing_state.py", "marketing_state")
gtm = load("skills/gtm/scripts/gtm.py", "gtm_store")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class ResolveTest(StoreCase):
    module = gtm

    def test_default_is_outside_the_repo(self):
        st = ms.resolve()
        self.assertEqual(st.backend, "dir")
        self.assertEqual(st.root.resolve(), (self.base / "home" / "product").resolve())
        self.assertEqual(st.source, "default")

    def test_slug_from_origin(self):
        git("remote", "add", "origin", "git@github.com:Acme/Redact-App.git", cwd=self.product)
        self.assertEqual(ms.resolve().slug, "acme-redact-app")
        self.assertEqual(ms.slug_from_url("https://github.com/acme/site"), "acme-site")

    def test_env_beats_config_beats_legacy(self):
        (self.product / ".marketing").mkdir()
        (self.product / ".marketing" / "gtm.json").write_text("{}")
        self.assertEqual(ms.resolve().backend, "repo")
        ms.register("product", str(self.base / "elsewhere"))
        self.assertEqual(ms.resolve().root, (self.base / "elsewhere").resolve())
        os.environ["MARKETING_STATE"] = "git@github.com:acme/state.git"
        st = ms.resolve()
        self.assertEqual((st.backend, st.remote), ("git", "git@github.com:acme/state.git"))
        self.assertEqual(st.root, self.base / "home" / "clones" / "product")
        os.environ["MARKETING_STATE"] = "repo"
        self.assertEqual(ms.resolve().root, self.product.resolve() / ".marketing")

    def test_gtm_writes_only_to_the_store(self):
        self.run_cli("init")
        self.run_cli("metric", "add", "x", "1")
        self.assertEqual([p.name for p in self.product.iterdir() if p.name != ".git"], [])
        self.assertTrue((self.base / "home" / "product" / "gtm.json").exists())
        where = self.json_cli("where")
        self.assertTrue(where["initialized"])


class GitBackendTest(StoreCase):
    module = gtm

    def setUp(self):
        super().setUp()
        self.remote = self.base / "state.git"
        git("init", "-q", "--bare", "-b", "main", str(self.remote), cwd=self.base)
        self.url = self.remote.as_uri()

    def test_use_pull_init_push_and_reclone(self):
        self.json_cli("store", "use", self.url)
        self.assertEqual(self.run_cli("sync", "pull")[0], 0)        # clones the empty repo
        self.run_cli("init")
        code, out = self.run_cli("sync", "push", "--message", "init")
        self.assertEqual(code, 0, self.last_err)
        self.assertIn("pushed", out)
        clone = self.base / "home" / "clones" / "product"
        subprocess.run(["rm", "-rf", str(clone)], check=True)
        gtm._root_for.cache_clear()
        self.assertEqual(self.run_cli("sync", "pull")[0], 0)
        self.assertTrue((clone / "gtm.json").exists())
        self.assertIn("no changes", self.run_cli("sync", "push")[1])

    def test_pull_refuses_a_dirty_clone(self):
        self.json_cli("store", "use", self.url)
        self.run_cli("sync", "pull")
        self.run_cli("init")
        self.run_cli("sync", "push")
        (self.base / "home" / "clones" / "product" / "stray.txt").write_text("x")
        self.assertEqual(self.run_cli("sync", "pull")[0], 1)
        self.assertIn("uncommitted", self.last_err)


class MigrateTest(StoreCase):
    module = gtm

    def test_migrate_legacy_repo_state_to_dir(self):
        legacy = self.product / ".marketing"
        (legacy / "runs" / "2026-10-01").mkdir(parents=True)
        (legacy / "runs" / "2026-10-01" / "score.json").write_text("{}")
        (legacy / "gtm.json").write_text(json.dumps({"stage": "launched", "state_commit": "direct",
                                                     "last_run": {"audit": "2026-10-01"}}))
        self.assertEqual(gtm.R().resolve(), legacy.resolve())
        target = self.base / "store"
        out = self.json_cli("migrate", "--to", str(target))
        self.assertEqual(out["backend"], "dir")
        s = json.loads((target / "gtm.json").read_text())
        self.assertEqual(s["last_run"]["audit"], "2026-10-01")
        self.assertNotIn("state_commit", s)
        self.assertTrue((target / "runs" / "2026-10-01" / "score.json").exists())
        gtm._root_for.cache_clear()
        self.assertEqual(gtm.R(), target.resolve())                # config now wins over the legacy dir
        self.assertEqual(self.run_cli("migrate", "--to", str(target))[0], 1)  # refuses to overwrite history
        self.assertTrue((legacy / "MOVED").exists())

    def test_nothing_to_migrate(self):
        self.assertEqual(self.run_cli("migrate", "--to", str(self.base / "s"))[0], 1)


class SafetyTest(StoreCase):
    module = gtm

    def test_plugin_repo_is_not_a_product(self):
        (self.product / ".claude-plugin").mkdir()
        (self.product / ".claude-plugin" / "plugin.json").write_text('{"name": "marketing"}')
        self.assertEqual(self.run_cli("tick")[0], 1)
        self.assertIn("plugin itself", self.last_err)

    def test_migrated_repo_on_another_host_refuses_the_stale_copy(self):
        legacy = self.product / ".marketing"
        legacy.mkdir()
        (legacy / "gtm.json").write_text("{}")
        (legacy / "MOVED").write_text("moved to git@github.com:acme/state.git on 2026-11-01")
        self.assertEqual(self.run_cli("tick")[0], 1)
        self.assertIn("store use", self.last_err)

    def test_relative_store_paths_are_saved_absolute(self):
        (self.product / "sub").mkdir()
        self.json_cli("store", "use", "./mystate")
        os.chdir(self.product / "sub")
        gtm._root_for.cache_clear()
        self.assertEqual(ms.resolve().root, (self.product / "mystate").resolve())

    def test_git_store_must_be_cloned_and_never_pushes_a_parent_repo(self):
        os.environ["MARKETING_STATE"] = "git@github.com:acme/state.git"
        self.assertEqual(self.run_cli("init")[0], 1)                    # not cloned: refuse, create nothing
        self.assertIn("sync pull", self.last_err)
        self.assertFalse((self.base / "home" / "clones").exists())
        clone = self.base / "home" / "clones" / "product"
        clone.mkdir(parents=True)
        (clone / "junk").write_text("x")
        self.assertEqual(self.run_cli("sync", "push")[0], 1)            # not a clone: refuse
        self.assertEqual(self.run_cli("sync", "pull")[0], 1)            # non-empty dir: refuse to clone over

    def test_parallel_records_keep_valid_state(self):
        import subprocess as sp
        import sys as _sys
        self.run_cli("init")
        script = str(Path(gtm.__file__))
        env = dict(os.environ)
        procs = [sp.Popen([_sys.executable, script, "record", f"job{i}", "--cost", "0.1"], cwd=self.product, env=env,
                          stdout=sp.DEVNULL, stderr=sp.PIPE) for i in range(8)]
        for p in procs:
            self.assertEqual(p.wait(), 0, p.stderr.read())
        s = json.loads((gtm.R() / "gtm.json").read_text())
        self.assertEqual(sum(1 for k in s["last_run"] if k.startswith("job")), 8)
        self.assertAlmostEqual(gtm.month_spend(gtm.spend_rows()), 0.8)
