"""Shared test scaffolding: load a skill script as a module and run its CLI in an isolated store."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses (marketing_state.Store) look their module up here
    spec.loader.exec_module(mod)
    return mod


class StoreCase(unittest.TestCase):
    """Runs every test in a temp product dir with MARKETING_HOME in a temp dir: nothing touches ~."""

    module = None  # set by subclasses: the loaded script whose main() `run` calls

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.product = self.base / "product"
        self.product.mkdir()
        self.cwd = os.getcwd()
        self.env = {k: os.environ.get(k) for k in ("MARKETING_HOME", "MARKETING_STATE")}
        os.environ["MARKETING_HOME"] = str(self.base / "home")
        os.environ.pop("MARKETING_STATE", None)
        os.chdir(self.product)

    def tearDown(self):
        os.chdir(self.cwd)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def run_cli(self, *argv, module=None):
        mod = module or self.module
        out, err = io.StringIO(), io.StringIO()
        old = sys.argv
        sys.argv = ["script.py", *argv]
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = mod.main()
                except SystemExit as e:
                    code = e.code if isinstance(e.code, int) else 1
                    if not isinstance(e.code, int) and e.code:
                        err.write(str(e.code))
        finally:
            sys.argv = old
        self.last_err = err.getvalue()
        return code, out.getvalue()

    def json_cli(self, *argv, module=None):
        code, out = self.run_cli(*argv, module=module)
        self.assertEqual(code, 0, self.last_err or out)
        return json.loads(out)
