#!/usr/bin/env python3
"""Launch videos with HyperFrames (HTML rendered to MP4), under the operator's rules.

    python3 video.py facts --since v1.4.0 [--until HEAD] [--gh] --out <project>   # what actually shipped
    python3 video.py new <slug>                       # <state>/launches/<date>-<slug>/: brief, facts, video/
    python3 video.py hf <project> -- <hyperframes args…>   # run the pinned CLI under the policy below
    python3 video.py copy <project>                   # every on-screen word + the voiceover → claims guard
    python3 video.py approve <project> --quote … [--approver slack:U… --source <link>]
    python3 video.py status <project>                 # approved? does the approval still match the files?

HyperFrames is pinned (PIN below) and runs through `npx`, with telemetry off. The policy in `hf`:
- media is local only: `media-use resolve` always gets `--local-only`; `media-use generate`, `auth`,
  HeyGen-hosted or cloud rendering, `publish`, `feedback`, `upgrade`, `skills` and `open` are refused
  (paid media, accounts and uploads are decisions for a human, outside this script);
- `catalog --on-device` (a model download) needs `--allow-download`;
- a render above `--quality draft` needs an approval whose content hash matches the project now: a
  human approved these exact files (`approve`, refused in a scheduled run), so an edit after approval
  needs approving again. Draft renders are for review and need nothing.
`capture` always runs with `--skip-vision` (no AI captioning of screenshots) and every command with
HYPERFRAMES_SKIP_SKILLS=1 (init would otherwise fetch coding skills from GitHub).

A project is a launch folder: brief.md, facts.md and approval.json beside `video/`, the HyperFrames
project (`hf <project> -- init video --non-interactive` creates it; later commands run inside it).
The folder gets a .gitignore for renders and caches, because a `git` state store commits everything.
Stdlib only; Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "gtm" / "scripts"))
import gtm  # noqa: E402

PIN = "0.8.181"  # released 2026-10-20; bump deliberately after reading the release notes
ENV = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HYPERFRAMES_SKIP_SKILLS": "1"}
REFUSED = {
    "auth": "accounts are set up by a human, not by the operator",
    "cloud": "cloud rendering uploads the project to HeyGen",
    "cloudrun": "cloud rendering runs on a paid account",
    "lambda": "cloud rendering runs on a paid account",
    "publish": "publishing is a human's job",
    "feedback": "sends text to HeyGen",
    "upgrade": f"the version is pinned to {PIN} in video.py",
    "skills": f"the skills are pinned with the CLI ({PIN})",
    "open": "hands the project to a desktop app",
    "present": "opens a presentation server for a person, not for the operator",
}
IGNORE = ["renders/", ".hyperframes/", "snapshots/", "node_modules/", "*.mp4", "*.webm", "*.mov", "*.gif",
          "*.wav", "*.mp3"]
HASHED_SKIP = {"renders", ".hyperframes", "snapshots", "node_modules", ".git"}
HASHED_SKIP_FILES = {"approval.json", "facts.json", "facts.md", "copy.txt", ".gitignore"}


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> int:
    """The one place a process is started (tests replace it)."""
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None, env={**os.environ, **(env or {})})


def capture(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=True).stdout


# --------------------------------------------------------------------------- facts
MERGE = re.compile(r"Merge pull request #(\d+)")
SQUASH = re.compile(r"\(#(\d+)\)\s*$")


def facts(since: str, until: str = "HEAD", use_gh: bool = False) -> dict:
    """First-parent history between two refs: each merged PR (merge or squash) or plain commit."""
    log = capture(["git", "log", "--first-parent", "--format=%H%x1f%ad%x1f%s%x1f%b%x1e", "--date=short",
                   f"{since}..{until}"])
    items = []
    for rec in log.split("\x1e"):
        if not rec.strip():
            continue
        sha, date, subject, body = (rec.strip("\n").split("\x1f") + ["", "", "", ""])[:4]
        m = MERGE.search(subject) or SQUASH.search(subject)
        pr = int(m.group(1)) if m else None
        title = body.strip().splitlines()[0] if MERGE.search(subject) and body.strip() else SQUASH.sub("", subject).strip()
        item = {"sha": sha[:12], "date": date, "pr": pr, "title": title}
        if use_gh and pr:
            try:
                info = json.loads(capture(["gh", "pr", "view", str(pr), "--json", "title,body,labels,url"]))
                item.update({"title": info.get("title") or title, "url": info.get("url"),
                             "labels": [x["name"] for x in info.get("labels") or []],
                             "summary": (info.get("body") or "").strip().split("\n\n")[0][:600]})
            except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
                item["gh_error"] = True
        items.append(item)
    return {"since": since, "until": until, "built": dt.date.today().isoformat(), "changes": items}


def facts_md(f: dict) -> str:
    L = [f"# What shipped: {f['since']}..{f['until']}", "",
         "Read every line before it goes in the video. A change only goes on screen if it is user-visible "
         "and a claims-ledger row covers what you say about it.", ""]
    for c in f["changes"]:
        ref = f"#{c['pr']}" if c.get("pr") else c["sha"]
        L.append(f"- {c['date']} {ref}: {c['title']}" + (f" ({c['url']})" if c.get("url") else ""))
        if c.get("summary"):
            L.append(f"  > {c['summary'].splitlines()[0][:200]}")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- project
def project_dir(slug: str) -> Path:
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,60}$", slug):
        raise ValueError("slug is lowercase letters, digits and dashes")
    return gtm.R() / "launches" / f"{gtm.today().isoformat()}-{slug}"


def setup(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    (p / ".gitignore").write_text("\n".join(IGNORE) + "\n")
    # HyperFrames refuses paid calls past a project's credit limit; zero, in the folder and the project
    for d in (p, p / "video"):
        if d.is_dir():
            (d / ".hyperframes").mkdir(exist_ok=True)
            (d / ".hyperframes" / "credit-limit.json").write_text(json.dumps({"credits": 0}) + "\n")
    brief = p / "brief.md"
    if not brief.exists():
        brief.write_text(BRIEF)


BRIEF = """# Brief

- **Launch**: <feature, tag or PR> (facts.md)
- **Audience**: <who this is for, from product-context.md>
- **One point**: <the single thing a viewer should remember>
- **Length**: <20-45 s>   **Format**: <1920×1080 | 1080×1920>
- **Real footage**: <which product screens, captured from where>

## Voiceover script

<one line per beat; every product claim matches an OK row in claims.md>

## Beats

| # | seconds | on screen | voiceover |
|---|---|---|---|
"""


def hf_command(p: Path, args: list[str], allow_download: bool = False) -> tuple[list[str] | None, str | None]:
    """The npx command for these HyperFrames args, or why it is refused."""
    if not args:
        return None, "give the hyperframes arguments after --"
    sub = args[0]
    if sub in REFUSED:
        return None, f"`hyperframes {sub}` is refused: {REFUSED[sub]}"
    if sub == "media-use":
        verb = args[1] if len(args) > 1 else ""
        if verb == "generate":
            return None, "`media-use generate` makes paid media; local tools only (ask a human for anything else)"
        if verb == "resolve" and "--local-only" not in args:
            args = args + ["--local-only"]
        if "--provider" in args:
            return None, "--provider picks a network provider; local tools only"
    if sub == "capture" and "--skip-vision" not in args:
        args = args + ["--skip-vision"]
    if sub == "catalog" and "--on-device" in args and not allow_download:
        return None, "`catalog --on-device` downloads a ~33 MB model: pass --allow-download once a human agrees"
    if sub == "render" and not _draft(args):
        ok, why = approval_matches(p)
        if not ok:
            return None, f"a render above --quality draft needs an approval of these exact files: {why}"
    return ["npx", "-y", f"hyperframes@{PIN}", *args], None


def _draft(args: list[str]) -> bool:
    for i, a in enumerate(args):
        if a == "--quality" and i + 1 < len(args):
            return args[i + 1] == "draft"
        if a.startswith("--quality="):
            return a.split("=", 1)[1] == "draft"
    return False  # the CLI's default quality is `looks`


# --------------------------------------------------------------------------- copy
class _Text(HTMLParser):
    """Visible text and data-var-text values from a composition; scripts and styles skipped."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        for k, v in attrs:
            if k in ("data-var-text", "alt", "aria-label", "title") and v:
                self.out.append(v)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.out.append(" ".join(data.split()))


def copy_text(p: Path) -> str:
    parts = []
    for f in sorted(p.rglob("*.html")):
        if any(x in HASHED_SKIP for x in f.relative_to(p).parts):
            continue
        t = _Text()
        t.feed(f.read_text(errors="replace"))
        if t.out:
            parts.append(f"<!-- {f.relative_to(p)} -->\n" + "\n".join(t.out))
    brief = p / "brief.md"
    if brief.exists():
        m = re.search(r"## Voiceover script\n(.*?)(\n## |\Z)", brief.read_text(), re.S)
        if m and m.group(1).strip():
            parts.append("<!-- voiceover (brief.md) -->\n" + m.group(1).strip())
    return "\n\n".join(parts) + "\n"


# --------------------------------------------------------------------------- approval
def content_hash(p: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(x for x in p.rglob("*") if x.is_file()):
        rel = f.relative_to(p)
        if any(x in HASHED_SKIP for x in rel.parts) or rel.name in HASHED_SKIP_FILES:
            continue
        h.update(str(rel).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def approval_matches(p: Path) -> tuple[bool, str]:
    a = p / "approval.json"
    if not a.exists():
        return False, "none yet (video.py approve, with the human's words)"
    try:
        rec = json.loads(a.read_text())
    except json.JSONDecodeError:
        return False, "approval.json is unreadable"
    if rec.get("hash") != content_hash(p):
        return False, f"the project changed since {rec.get('approver') or 'the human'} approved it on {rec.get('date')}"
    return True, "ok"


# --------------------------------------------------------------------------- cli
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("facts", help="run from the product repo root, after git pull")
    p.add_argument("--since", required=True, help="the previous release tag or commit")
    p.add_argument("--until", default="HEAD")
    p.add_argument("--gh", action="store_true", help="add PR titles, labels and summaries via gh")
    p.add_argument("--out", required=True, help="the launch folder (video.py new)")
    p = sub.add_parser("new")
    p.add_argument("slug")
    p = sub.add_parser("hf")
    p.add_argument("project")
    p.add_argument("--allow-download", action="store_true")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p = sub.add_parser("copy")
    p.add_argument("project")
    p = sub.add_parser("approve")
    p.add_argument("project")
    p.add_argument("--quote", required=True, help="the human's words, verbatim")
    p.add_argument("--approver", help="platform:id; required when gtm.json lists approvers")
    p.add_argument("--source", help="link to the message or reaction")
    p = sub.add_parser("status")
    p.add_argument("project")
    a = ap.parse_args()

    if a.cmd == "facts":
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        try:
            f = facts(a.since, a.until, a.gh)
        except subprocess.CalledProcessError as e:
            print(f"git log failed: {(e.stderr or '').strip()}", file=sys.stderr)
            return 1
        (out / "facts.json").write_text(json.dumps(f, indent=1) + "\n")
        (out / "facts.md").write_text(facts_md(f))
        print(json.dumps({"facts": str(out / "facts.md"), "changes": len(f["changes"])}))
        return 0
    if a.cmd == "new":
        try:
            d = project_dir(a.slug)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        setup(d)
        print(json.dumps({"project": str(d), "pin": PIN,
                          "next": f"python3 {HERE} hf {d} -- init video --non-interactive"}))
        return 0
    proj = Path(a.project)
    if a.cmd == "hf":
        if not proj.is_dir():
            print(f"no project at {proj}: video.py new <slug> first", file=sys.stderr)
            return 1
        setup(proj)  # idempotent: re-asserts the credit cap and the ignore list
        args = a.args[1:] if a.args[:1] == ["--"] else a.args
        cmd, why = hf_command(proj, args, a.allow_download)
        if why:
            print(why, file=sys.stderr)
            return 3
        workdir = proj / "video" if (proj / "video").is_dir() and args[0] != "init" else proj
        code = run(cmd, cwd=workdir, env=ENV)
        setup(proj)  # after init, the new project gets its credit limit too
        return code
    if a.cmd == "copy":
        text = copy_text(proj)
        (proj / "copy.txt").write_text(text)
        guard = HERE.parents[2] / "writing" / "scripts" / "claims_guard.py"
        return subprocess.call([sys.executable, str(guard), str(proj / "copy.txt")])
    if a.cmd == "approve":
        s = gtm.load_state()
        why = gtm.unattended_refusal("approving a video")
        if why:
            print(why, file=sys.stderr)
            return 1
        prov, why = gtm.approval_provenance(s, a, "approving a video")
        if why:
            print(why, file=sys.stderr)
            return 1
        rec = {"date": gtm.today().isoformat(), "hash": content_hash(proj), "quote": a.quote, **prov}
        (proj / "approval.json").write_text(json.dumps(rec, indent=1) + "\n")
        gtm.append_jsonl(gtm.R() / "approvals.jsonl", {"date": rec["date"], "video": str(proj), "hash": rec["hash"],
                                                        "quote": a.quote, **prov})
        print(f"approved {proj.parent.name}: renders above draft may run until the files change")
        return 0
    ok, why = approval_matches(proj)
    print(json.dumps({"project": str(proj), "approved": ok, "why": why, "pin": PIN}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
