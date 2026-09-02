"""Shared helpers for every check module.

Import from here rather than importing PyYAML directly: the guard below turns a
missing dependency into one readable line instead of a traceback, and it only
runs first if every module reaches yaml through this one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FAIL  PyYAML is required: py -m pip install pyyaml")
    sys.exit(1)

__all__ = [
    "ROOT",
    "RESULTS",
    "yaml",
    "ok",
    "fail",
    "skip",
    "rel",
    "load_yaml",
    "parse_frontmatter",
    "git",
]

# scripts/checks/common.py -> scripts/checks -> scripts -> repository root
ROOT = Path(__file__).resolve().parent.parent.parent

RESULTS: list[tuple[str, str, str]] = []


def ok(name: str, detail: str = "") -> None:
    RESULTS.append(("PASS", name, detail))


def fail(name: str, detail: str) -> None:
    RESULTS.append(("FAIL", name, detail))


def skip(name: str, detail: str) -> None:
    RESULTS.append(("SKIP", name, detail))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path):
    """Return (meta, error). meta is None when the block is missing or broken."""
    lines = path.read_text(encoding="utf-8").split("\n")
    if not lines or lines[0].strip() != "---":
        return None, "must start with a '---' frontmatter fence"
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.rstrip() == "---")
    except StopIteration:
        return None, "frontmatter is not closed by a '---' line"
    try:
        return (yaml.safe_load("\n".join(lines[1:end])) or {}), None
    except yaml.YAMLError as exc:
        return None, f"frontmatter does not parse: {exc}"


def git(*args: str) -> int | None:
    """Run a fixed git query. Returns the exit code, or None if git can't run."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.returncode
