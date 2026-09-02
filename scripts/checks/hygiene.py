"""Repository hygiene — AGENTS.md: LF line endings, parseable YAML."""

from __future__ import annotations

from .common import fail, load_yaml, ok, rel, skip, yaml, ROOT

ORDER = 10

TEXT_GLOBS = (
    "*.md",
    "monitoring/**/*",
    "tasks/**/*",
    "scripts/**/*.py",
    ".opencode/agents/*.md",
)

# The globs above are broad on purpose, so anything a task adds is covered by
# default. That means they also sweep up whatever the tooling generates next to
# the source - a .pyc read as text is all CRLF and would fail every run.
GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".git", "node_modules"}
BINARY_SUFFIXES = {
    ".pyc", ".pyo", ".so", ".dll", ".png", ".jpg", ".jpeg",
    ".gif", ".ico", ".pdf", ".zip", ".gz", ".db", ".woff", ".woff2",
}


def is_source(path) -> bool:
    """A committed text file a human wrote, as opposed to build output."""
    if not path.is_file():
        return False
    if GENERATED_DIRS.intersection(path.parts):
        return False
    return path.suffix.lower() not in BINARY_SUFFIXES


def check_line_endings() -> None:
    """AGENTS.md: use LF line endings."""
    offenders = []
    for pattern in TEXT_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if not is_source(path):
                continue
            if b"\r\n" in path.read_bytes():
                offenders.append(rel(path))
    if offenders:
        fail("line endings", "CRLF found in: " + ", ".join(offenders))
    else:
        ok("line endings", "all LF")


def check_yaml_parses() -> None:
    files = [
        p
        for p in sorted(ROOT.glob("monitoring/**/*"))
        if p.suffix in (".yml", ".yaml") and is_source(p)
    ]
    if not files:
        skip("yaml parses", "no YAML under monitoring/ yet")
        return
    bad = []
    for path in files:
        try:
            load_yaml(path)
        except yaml.YAMLError as exc:
            bad.append(f"{rel(path)} ({exc.__class__.__name__})")
    if bad:
        fail("yaml parses", "; ".join(bad))
    else:
        ok("yaml parses", f"{len(files)} file(s)")
