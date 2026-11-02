"""Static check of evals/: every case loads in `claude plugin eval` terms, without calling a model.

Checks that each case directory has prompt.md (or case.yaml), only known frontmatter keys, at least
one grader with a known type and its required fields. Cheap enough for every PR.
"""
import re
import sys
from pathlib import Path

PROMPT_KEYS = {"name", "description", "tags", "plugins", "runs", "model", "max_turns", "timeout_seconds",
               "allowed_tools", "append_system_prompt", "env"}
GRADERS = {"regex": {"pattern"}, "tool_used": {"tool"}, "tool_order": set(), "file_exists": set(),
           "llm": set(), "baseline": set()}


def frontmatter(p: Path) -> dict:
    text = p.read_text()
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        raise ValueError(f"{p}: no frontmatter")
    keys = {}
    for line in m.group(1).splitlines():
        if line.strip() and not line.startswith((" ", "-")):
            k, _, v = line.partition(":")
            keys[k.strip()] = v.strip()
    return keys


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "evals")
    if not root.exists():
        print("no evals/ directory")
        return 0
    errors, cases = [], 0
    for case in sorted(d for d in root.iterdir() if d.is_dir() and d.name != "results"):
        cases += 1
        prompt = case / "prompt.md"
        if not prompt.exists() and not (case / "case.yaml").exists():
            errors.append(f"{case}: needs prompt.md or case.yaml")
            continue
        if prompt.exists():
            try:
                fm = frontmatter(prompt)
                unknown = set(fm) - PROMPT_KEYS
                if unknown:
                    errors.append(f"{prompt}: unknown keys {sorted(unknown)}")
                if "runs" in fm and not 1 <= int(fm["runs"]) <= 50:
                    errors.append(f"{prompt}: runs must be 1-50")
            except ValueError as e:
                errors.append(str(e))
        graders = sorted((case / "graders").glob("*.md")) if (case / "graders").exists() else []
        if not graders:
            errors.append(f"{case}: no graders")
        for g in graders:
            try:
                fm = frontmatter(g)
            except ValueError as e:
                errors.append(str(e))
                continue
            t = fm.get("type")
            if t not in GRADERS:
                errors.append(f"{g}: unknown grader type {t!r}")
            elif GRADERS[t] - set(fm):
                errors.append(f"{g}: {t} grader needs {sorted(GRADERS[t] - set(fm))}")
    for e in errors:
        print(f"::error::{e}")
    print(f"{cases} eval cases checked, {len(errors)} problems")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
