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


def check_line_endings() -> None:
    """AGENTS.md: use LF line endings."""
    offenders = []
    for pattern in TEXT_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            if b"\r\n" in path.read_bytes():
                offenders.append(rel(path))
    if offenders:
        fail("line endings", "CRLF found in: " + ", ".join(offenders))
    else:
        ok("line endings", "all LF")


def check_yaml_parses() -> None:
    files = [p for p in sorted(ROOT.glob("monitoring/**/*")) if p.suffix in (".yml", ".yaml")]
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
