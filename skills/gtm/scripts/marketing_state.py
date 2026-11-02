#!/usr/bin/env python3
"""Where the marketing program keeps its state. Shared by every script in the plugin.

The state store is a directory. Its backend decides where that directory lives:

    dir   ~/.marketing/<owner>-<repo>/          default; for a persistent host
    git   a clone of a private state repo       for ephemeral hosts, or for history
    repo  <product repo>/.marketing/            the 0.3 behaviour, kept for teams that want it

Resolution, first match wins:
    1. $MARKETING_STATE: a directory path, a git URL, or the word "repo"
    2. ~/.marketing/config.json: {"stores": {"<owner>-<repo>": "<path | git URL | repo>"}}
    3. <repo>/.marketing/gtm.json exists: the repo backend (an unmigrated 0.3 install)
    4. the dir backend at ~/.marketing/<owner>-<repo>/

$MARKETING_HOME overrides ~/.marketing (tests use it so nothing touches the real home).

Other skills import this module through a path relative to their own script:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gtm" / "scripts"))
    from marketing_state import state_root
Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

LEGACY_DIR = ".marketing"


@dataclass
class Store:
    root: Path            # the state directory every script reads and writes
    backend: str          # "dir" | "git" | "repo"
    slug: str             # "<owner>-<repo>" of the product repo
    remote: str | None    # git URL for the git backend
    source: str           # which resolution rule picked it

    def as_dict(self) -> dict:
        return {"root": str(self.root), "backend": self.backend, "slug": self.slug,
                "remote": self.remote, "source": self.source}


def home() -> Path:
    return Path(os.environ.get("MARKETING_HOME") or Path.home() / ".marketing").expanduser()


def _git(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def repo_root(cwd: Path | None = None) -> Path:
    """Top of the product repo, or the working directory when it isn't a git repo."""
    cwd = Path(cwd or Path.cwd())
    try:
        top = _git(["rev-parse", "--show-toplevel"], cwd=cwd)
        if top:
            return Path(top)
    except (RuntimeError, FileNotFoundError):
        pass
    return cwd.resolve()


def slug_from_url(url: str) -> str | None:
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url.strip())
    return f"{m.group(1)}-{m.group(2)}".lower() if m else None


def repo_slug(root: Path) -> str:
    try:
        url = _git(["remote", "get-url", "origin"], cwd=root)
        s = slug_from_url(url)
        if s:
            return s
    except (RuntimeError, FileNotFoundError):
        pass
    return re.sub(r"[^a-z0-9._-]+", "-", root.name.lower()) or "product"


def is_git_url(spec: str) -> bool:
    return spec.startswith(("git@", "ssh://", "https://", "http://", "file://")) or spec.endswith(".git")


def config_path() -> Path:
    return home() / "config.json"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {"stores": {}}
    c = json.loads(p.read_text())
    c.setdefault("stores", {})
    return c


def normalize_spec(spec: str, root: Path | None = None) -> str:
    """Store specs are saved absolute: a relative directory means relative to the product repo root."""
    spec = spec.strip()
    if spec == "repo" or is_git_url(spec):
        return spec
    p = Path(spec).expanduser()
    if not p.is_absolute():
        p = (root or repo_root()) / p
    return str(p.resolve())


def register(slug: str, spec: str) -> None:
    """Remember which store a product uses, so later runs resolve it without an env var."""
    spec = normalize_spec(spec)
    c = load_config()
    c["stores"][slug] = spec
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(c, indent=2) + "\n")


def _from_spec(spec: str, slug: str, root: Path, source: str) -> Store:
    spec = spec.strip()
    if spec == "repo":
        return Store(root / LEGACY_DIR, "repo", slug, None, source)
    if is_git_url(spec):
        return Store(home() / "clones" / slug, "git", slug, spec, source)
    return Store(Path(spec).expanduser().resolve(), "dir", slug, None, source)


class StoreError(RuntimeError):
    pass


def is_plugin_repo(root: Path) -> bool:
    p = root / ".claude-plugin" / "plugin.json"
    try:
        return p.exists() and json.loads(p.read_text()).get("name") == "marketing"
    except (OSError, ValueError):
        return False


def resolve(cwd: Path | None = None) -> Store:
    root = repo_root(cwd)
    slug = repo_slug(root)
    env = os.environ.get("MARKETING_STATE")
    if env:
        return _from_spec(normalize_spec(env, root), slug, root, "env MARKETING_STATE")
    spec = load_config()["stores"].get(slug)
    if spec:
        return _from_spec(spec, slug, root, f"{config_path()}")
    if is_plugin_repo(root):
        raise StoreError(f"{root} is the marketing plugin itself, not a product: run from the product repo root "
                         "(call the plugin's scripts by absolute path)")
    moved = root / LEGACY_DIR / "MOVED"
    if moved.exists():
        raise StoreError(f"state was migrated out of {root / LEGACY_DIR} ({moved.read_text().strip()}); "
                         "on this host run `gtm.py store use <that store>` or set MARKETING_STATE")
    if (root / LEGACY_DIR / "gtm.json").exists():
        return Store(root / LEGACY_DIR, "repo", slug, None, "found .marketing/gtm.json in the repo")
    return Store(home() / slug, "dir", slug, None, "default")


def state_root(cwd: Path | None = None, create: bool = True) -> Path:
    st = resolve(cwd)
    if st.backend == "git" and not (st.root / ".git").exists():
        raise StoreError(f"the git state store isn't cloned yet: run `gtm.py sync pull` first ({st.remote})")
    if create:
        st.root.mkdir(parents=True, exist_ok=True)
    return st.root


# --------------------------------------------------------------------------- git backend
def pull(store: Store) -> str:
    """Clone or fast-forward the state repo. Refuses to merge: a diverged store needs a human."""
    if store.backend != "git":
        return f"{store.backend} backend: nothing to pull"
    if not (store.root / ".git").exists():
        if store.root.exists() and any(store.root.iterdir()):
            raise RuntimeError(f"{store.root} exists but isn't a clone of {store.remote}; move it aside first")
        store.root.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--quiet", store.remote, str(store.root)])
        return f"cloned {store.remote}"
    _check_clone(store)
    if _git(["status", "--porcelain"], cwd=store.root):
        raise RuntimeError(f"state clone {store.root} has uncommitted changes; push or inspect them first")
    has_upstream = subprocess.run(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=store.root,
                                  capture_output=True, text=True).returncode == 0
    if not has_upstream:
        return "state repo is empty; nothing to pull yet"
    _git(["pull", "--quiet", "--ff-only"], cwd=store.root)
    return "pulled"


def _check_clone(store: Store) -> None:
    """Refuse to touch any git repo other than the store's own clone (never a parent repo)."""
    if not (store.root / ".git").exists():
        raise RuntimeError(f"{store.root} is not a clone; run `gtm.py sync pull` first")
    top = Path(_git(["rev-parse", "--show-toplevel"], cwd=store.root)).resolve()
    if top != store.root.resolve():
        raise RuntimeError(f"{store.root} is inside another repo ({top}); refusing")


def push(store: Store, message: str) -> str:
    """Commit everything in the state clone and push. Never forces."""
    if store.backend != "git":
        return f"{store.backend} backend: nothing to push"
    _check_clone(store)
    _git(["add", "-A"], cwd=store.root)
    if not _git(["status", "--porcelain"], cwd=store.root):
        return "no changes"
    _git(["-c", "user.name=marketing-operator", "-c", "user.email=marketing-operator@users.noreply.github.com",
          "commit", "--quiet", "-m", message], cwd=store.root)
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=store.root)
    _git(["push", "--quiet", "-u", "origin", branch], cwd=store.root)
    return f"pushed to {store.remote} ({branch})"


if __name__ == "__main__":
    print(json.dumps(resolve().as_dict(), indent=2))
