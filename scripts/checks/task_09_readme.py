"""Task 9 acceptance (tasks/task-09-readme-measurements.md): operational
commands, the loopback-only dashboard access path, the --metrics requirement,
pinned images, the high-water mark caveat, and the three measurement sections.
Measurement tables must contain real numeric values, not PENDING placeholders.

Kept after acceptance: a later edit to monitoring/README.md that drops a
measurement or reintroduces a placeholder fails here.
"""

from __future__ import annotations

import re

from .common import fail, ok, skip, ROOT

ORDER = 60

TASK9_README = "monitoring/README.md"

TASK9_README_REQUIRED = (
    "docker compose up -d",
    "docker compose ps",
    "docker compose logs -f",
    "docker compose down",
    "http://localhost:3001",
    "ssh -L 3001:localhost:3001",
    "--metrics",
    "prom/prometheus:v3.13.2",
    "grafana/grafana:13.2.0",
    "high-water",
    "/slots",
    "Speculative Acceptance %",
    "docker stats",
    "benchmark",
    "rocm-smi",
    "2 GB",
)

TASK9_PLACEHOLDERS = ("pending", "tbd", "todo", "n/a", "na", "xxx")
TASK9_NUM = r"\d+(?:\.\d+)?"
TASK9_UNITS = {
    "memory": rf"{TASK9_NUM}\s*(?:MiB|GiB|MB|GB|B)",
    "toks": rf"{TASK9_NUM}\s*tok/s",
    "temp": rf"{TASK9_NUM}\s*(?:C|°C)",
    "power": rf"{TASK9_NUM}\s*W",
    "mhz": rf"{TASK9_NUM}\s*MHz",
    "percent": rf"{TASK9_NUM}\s*%",
}

TASK9_TABLE_SPECS = (
    {
        "header": ("state", "prometheus", "grafana", "total"),
        "fields": {
            (row, col): "memory"
            for row in ("idle", "dashboard open", "inference active")
            for col in ("prometheus", "grafana", "total")
        },
    },
    {
        "header": ("run", "monitoring", "output tok/s"),
        "fields": {("1", "output tok/s"): "toks", ("2", "output tok/s"): "toks"},
        "labels": {("1", "monitoring"): "OFF", ("2", "monitoring"): "ON"},
    },
    {
        "header": ("reading", "temperature", "power", "SCLK", "MCLK", "fan", "VRAM", "GPU use"),
        "fields": {
            (row, col): unit
            for row in ("baseline", "after scraping")
            for col, unit in (
                ("temperature", "temp"),
                ("power", "power"),
                ("SCLK", "mhz"),
                ("MCLK", "mhz"),
                ("fan", "percent"),
                ("VRAM", "percent"),
                ("GPU use", "percent"),
            )
        },
    },
)

TASK9_BENCHMARK_REQUIRED = (
    "controlled test suite",
    "same model",
    "identical prompt",
    "identical API",
    "identical API client",
    "identical generation settings",
)


def _task9_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _task9_tables(text: str) -> dict[tuple[str, ...], dict[tuple[str, str], str]]:
    tables = {}
    block = []

    def flush() -> None:
        nonlocal block
        if len(block) >= 3:
            header = tuple(_task9_cells(block[0]))
            separator = _task9_cells(block[1])
            if all(cell and set(cell) <= set(":-") for cell in separator):
                cells = {}
                for line in block[2:]:
                    row = _task9_cells(line)
                    if row:
                        for col, value in zip(header[1:], row[1:]):
                            cells[(row[0], col)] = value
                tables[header] = cells
        block = []

    for line in text.splitlines():
        if line.strip().startswith("|"):
            block.append(line)
        else:
            flush()
    flush()
    return tables


def _task9_placeholder(value: str) -> bool:
    value = value.strip().lower()
    return not value or any(value == p or value.startswith(f"{p} ") for p in TASK9_PLACEHOLDERS)


def check_task9_readme() -> None:
    """tasks/task-09-readme-measurements.md: README content for Phase 1."""
    path = ROOT / TASK9_README
    if not path.exists():
        skip("task9 readme", "monitoring/README.md not created yet")
        return
    text = path.read_text(encoding="utf-8")
    problems = []
    normalized = " ".join(text.split())
    missing = [item for item in TASK9_README_REQUIRED if item not in text]
    if missing:
        problems.append("missing: " + ", ".join(missing))

    tables = _task9_tables(text)
    for spec in TASK9_TABLE_SPECS:
        header = spec["header"]
        cells = tables.get(header)
        if cells is None:
            problems.append(f"missing measurement table {header}")
            continue
        for (row, col), unit in spec["fields"].items():
            value = cells.get((row, col), "")
            if _task9_placeholder(value):
                problems.append(f"placeholder value in {header}: {row}/{col}")
            elif not re.fullmatch(TASK9_UNITS[unit], value):
                problems.append(f"invalid {unit} value in {header}: {row}/{col}={value!r}")
        for (row, col), expected in spec.get("labels", {}).items():
            value = cells.get((row, col), "")
            if value.upper() != expected:
                problems.append(f"{header}: {row}/{col} must be {expected}, got {value!r}")

    for phrase in TASK9_BENCHMARK_REQUIRED:
        if phrase not in normalized:
            problems.append(f"benchmark missing comparability phrase: {phrase!r}")

    for line in text.splitlines():
        if line.startswith("Result:") and _task9_placeholder(line.split(":", 1)[1]):
            problems.append(f"placeholder result line: {line!r}")

    if problems:
        fail("task9 readme", "; ".join(problems))
    else:
        ok("task9 readme", "commands, tunnel, --metrics, pinned tags, 3 real measurements")
