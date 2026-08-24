#!/usr/bin/env python3
"""The only verification command in this repository.

    py scripts/verify.py

Every file-level check the tasks require lives here: YAML parsing, JSON
parsing, line endings, agent frontmatter, and the configuration invariants
from AGENTS.md. Agents must not invent lint, format, schema or build
commands — if a check is worth running, add it to this file.

Runtime verification (docker compose up, restarting Grafana, querying
Prometheus targets) happens on the Ubuntu deployment server and is
deliberately out of scope here. Missing files are reported as SKIP so that
early tasks pass before later tasks create them.

Exit code 0 = no failures, 1 = at least one FAIL.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FAIL  PyYAML is required: py -m pip install pyyaml")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
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


# --------------------------------------------------------------------------
# Repository hygiene
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Compose invariants (AGENTS.md: pinned images, loopback-only Grafana,
# read-only config mounts, named volumes, external llm network)
# --------------------------------------------------------------------------


def check_compose() -> None:
    path = ROOT / "monitoring" / "compose.yaml"
    if not path.exists():
        skip("compose", "monitoring/compose.yaml not created yet")
        return
    try:
        doc = load_yaml(path) or {}
    except yaml.YAMLError as exc:
        fail("compose", f"does not parse: {exc}")
        return

    services = doc.get("services") or {}
    problems = []

    for name, svc in services.items():
        image = (svc or {}).get("image", "")
        tag = image.rsplit(":", 1)[-1] if ":" in image else ""
        if not tag or tag == "latest":
            problems.append(f"{name}: image must be pinned to a version, got {image!r}")

        for spec in (svc or {}).get("ports") or []:
            spec = str(spec)
            if name != "grafana":
                problems.append(f"{name}: only grafana may publish a port, found {spec!r}")
            elif not spec.startswith("127.0.0.1:"):
                problems.append(f"{name}: port must bind loopback, got {spec!r}")

        for spec in (svc or {}).get("volumes") or []:
            spec = str(spec)
            if spec.startswith("./") and not spec.endswith(":ro"):
                problems.append(f"{name}: config mount must be read-only, got {spec!r}")

    volumes = doc.get("volumes") or {}
    for expected in ("prometheus-data", "grafana-data"):
        if expected not in volumes:
            problems.append(f"missing named volume {expected!r}")

    llm = (doc.get("networks") or {}).get("llm")
    if llm is None:
        problems.append("missing 'llm' network")
    elif not llm.get("external"):
        problems.append("'llm' network must be external (correction 3)")

    if problems:
        fail("compose", "; ".join(problems))
    else:
        ok("compose", f"{len(services)} service(s)")


# --------------------------------------------------------------------------
# Prometheus config (correction 1: no env templating, literal scrape target)
# --------------------------------------------------------------------------


def check_prometheus() -> None:
    path = ROOT / "monitoring" / "prometheus" / "prometheus.yml"
    if not path.exists():
        skip("prometheus.yml", "not created yet")
        return

    raw = path.read_text(encoding="utf-8")
    problems = []
    if "${" in raw:
        problems.append("contains ${...}; Prometheus does not expand env vars (correction 1)")

    try:
        doc = load_yaml(path) or {}
    except yaml.YAMLError as exc:
        fail("prometheus.yml", f"does not parse: {exc}")
        return

    jobs = [j.get("job_name") for j in (doc.get("scrape_configs") or [])]
    if "llama_cpp" not in jobs:
        problems.append(f"no scrape job named 'llama_cpp' (found {jobs})")

    if problems:
        fail("prometheus.yml", "; ".join(problems))
    else:
        ok("prometheus.yml", f"jobs: {', '.join(j for j in jobs if j)}")


# --------------------------------------------------------------------------
# Grafana provisioning
# --------------------------------------------------------------------------


def check_datasource() -> None:
    path = ROOT / "monitoring" / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
    if not path.exists():
        skip("grafana datasource", "not created yet")
        return
    try:
        doc = load_yaml(path) or {}
    except yaml.YAMLError as exc:
        fail("grafana datasource", f"does not parse: {exc}")
        return

    sources = doc.get("datasources") or []
    problems = []
    if len(sources) != 1:
        problems.append(f"expected exactly one datasource, found {len(sources)}")
    for src in sources:
        if src.get("uid") != "prometheus":
            problems.append(f"uid must be 'prometheus', got {src.get('uid')!r}")
        if src.get("url") != "http://prometheus:9090":
            problems.append(f"url must be 'http://prometheus:9090', got {src.get('url')!r}")
        if src.get("type") != "prometheus":
            problems.append(f"type must be 'prometheus', got {src.get('type')!r}")

    if problems:
        fail("grafana datasource", "; ".join(problems))
    else:
        ok("grafana datasource", "uid=prometheus url=http://prometheus:9090")


def check_dashboard_provider() -> None:
    path = ROOT / "monitoring" / "grafana" / "provisioning" / "dashboards" / "dashboards.yml"
    if not path.exists():
        skip("dashboard provider", "not created yet")
        return
    try:
        doc = load_yaml(path) or {}
    except yaml.YAMLError as exc:
        fail("dashboard provider", f"does not parse: {exc}")
        return

    providers = doc.get("providers") or []
    problems = []
    if not providers:
        problems.append("no providers defined")
    for provider in providers:
        path_option = (provider.get("options") or {}).get("path")
        if path_option != "/var/lib/grafana/dashboards":
            problems.append(f"options.path must be '/var/lib/grafana/dashboards', got {path_option!r}")
        if provider.get("allowUiUpdates") is not False:
            problems.append("allowUiUpdates must be false so files stay the source of truth")

    if problems:
        fail("dashboard provider", "; ".join(problems))
    else:
        ok("dashboard provider", "file provider -> /var/lib/grafana/dashboards")


def _walk_panels(panels):
    for panel in panels or []:
        yield panel
        yield from _walk_panels(panel.get("panels"))


def check_dashboards() -> None:
    directory = ROOT / "monitoring" / "grafana" / "dashboards"
    files = sorted(directory.glob("*.json")) if directory.exists() else []
    if not files:
        skip("dashboard json", "no dashboards created yet")
        return

    problems = []
    for path in files:
        name = rel(path)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{name}: invalid JSON at line {exc.lineno}")
            continue

        if doc.get("id") is not None:
            problems.append(f"{name}: top-level 'id' must be null or provisioning skips the file")
        if not doc.get("uid"):
            problems.append(f"{name}: needs a stable 'uid'")
        if not doc.get("title"):
            problems.append(f"{name}: needs a 'title'")
        if doc.get("editable") is not False:
            problems.append(f"{name}: 'editable' must be false")

        for panel in _walk_panels(doc.get("panels")):
            if panel.get("type") == "row":
                continue
            label = panel.get("title") or f"panel {panel.get('id')}"
            for where, obj in [("panel", panel)] + [
                ("target", t) for t in panel.get("targets") or []
            ]:
                src = obj.get("datasource")
                if src is None:
                    problems.append(f"{name}: {label} {where} has no datasource")
                elif src.get("uid") != "prometheus":
                    problems.append(
                        f"{name}: {label} {where} datasource uid must be 'prometheus', got {src.get('uid')!r}"
                    )

    if problems:
        fail("dashboard json", "; ".join(problems))
    else:
        ok("dashboard json", f"{len(files)} dashboard(s)")


# --------------------------------------------------------------------------
# Task 7 dashboard panels (tasks/task-07-panels.md): the required panels with
# the exact Task 0 expressions, no rate() on the throughput gauges, the
# clamp_min guard on the speculative acceptance division, stat panels reduced
# to a single value, and the 30m/5s dashboard defaults.
# --------------------------------------------------------------------------

TASK7_DASHBOARD = "monitoring/grafana/dashboards/llm-overview.json"

# title -> (panel type, exact target expressions in refId order)
TASK7_PANELS = {
    "Generation tok/s": ("stat", ["llamacpp:predicted_tokens_seconds"]),
    "Prompt tok/s": ("stat", ["llamacpp:prompt_tokens_seconds"]),
    "Active Requests": ("stat", ["llamacpp:requests_processing"]),
    "CONTEXT HIGH-WATER": ("stat", ["llamacpp:n_tokens_max"]),
    "Throughput": (
        "timeseries",
        ["llamacpp:predicted_tokens_seconds", "llamacpp:prompt_tokens_seconds"],
    ),
    "Request Activity": (
        "timeseries",
        ["llamacpp:requests_processing", "llamacpp:requests_deferred"],
    ),
    "Speculative Acceptance %": (
        "stat",
        [
            "100 * llamacpp:spec_decode_num_accepted_tokens_total"
            " / clamp_min(llamacpp:spec_decode_num_draft_tokens_total, 1)"
        ],
    ),
    "Speculative Draft Tokens": ("stat", ["llamacpp:spec_decode_num_draft_tokens_total"]),
    "Speculative Accepted Draft Tokens": (
        "stat",
        ["llamacpp:spec_decode_num_accepted_tokens_total"],
    ),
    "Prompt Tokens (total)": ("stat", ["llamacpp:prompt_tokens_total"]),
    "Generated Tokens (total)": ("stat", ["llamacpp:tokens_predicted_total"]),
}


def check_task7_panels() -> None:
    """tasks/task-07-panels.md: required panels, exact expressions, no rate()."""
    path = ROOT / TASK7_DASHBOARD
    if not path.exists():
        skip("task7 panels", "llm-overview.json not created yet")
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("task7 panels", f"invalid JSON at line {exc.lineno}")
        return

    problems = []
    if doc.get("refresh") != "5s":
        problems.append(f"refresh must be '5s', got {doc.get('refresh')!r}")
    time_range = doc.get("time") or {}
    if time_range.get("from") != "now-30m" or time_range.get("to") != "now":
        problems.append(
            "time range must be now-30m -> now, "
            f"got {time_range.get('from')!r} -> {time_range.get('to')!r}"
        )

    panels = {p.get("title"): p for p in _walk_panels(doc.get("panels"))}
    for title, (panel_type, exprs) in TASK7_PANELS.items():
        panel = panels.get(title)
        if panel is None:
            problems.append(f"missing panel {title!r}")
            continue
        if panel.get("type") != panel_type:
            problems.append(f"{title!r} must be a {panel_type} panel, got {panel.get('type')!r}")
        got = [t.get("expr") for t in panel.get("targets") or []]
        if got != exprs:
            problems.append(f"{title!r} targets must be {exprs}, got {got}")
        for expr in got:
            if expr and "rate(" in expr:
                problems.append(
                    f"{title!r} applies rate() to {expr!r}; gauge metrics are queried directly"
                )
        if panel_type == "stat":
            reduce = (panel.get("options") or {}).get("reduceOptions") or {}
            if reduce.get("values") is not False:
                problems.append(
                    f"{title!r} stat panel must show a single value (reduceOptions.values must be false)"
                )
            if "lastNotNull" not in (reduce.get("calcs") or []):
                problems.append(f"{title!r} stat panel must reduce with lastNotNull")

    if problems:
        fail("task7 panels", "; ".join(problems))
    else:
        ok("task7 panels", f"{len(TASK7_PANELS)} panel(s) verified")


# --------------------------------------------------------------------------
# Task 9 README (tasks/task-09-readme-measurements.md): operational
# commands, the loopback-only dashboard access path, the --metrics
# requirement, pinned images, the high-water mark caveat, and the three
# measurement sections. Measurement tables must contain real numeric values,
# not PENDING placeholders.
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Agent definitions — catches the frontmatter mistakes that silently disable
# an agent's permission rules.
# --------------------------------------------------------------------------

AGENT_TOP_LEVEL_KEYS = {
    "description",
    "mode",
    "model",
    "temperature",
    "top_p",
    "prompt",
    "tools",
    "permission",
    "disable",
    "color",
    "hidden",
    "steps",
    "variant",
    "options",
    "name",
}

PERMISSION_KEYS = {
    "bash",
    "edit",
    "read",
    "write",
    "task",
    "webfetch",
    "websearch",
    "external_directory",
    "question",
    "doom_loop",
}


def check_agents() -> None:
    directory = ROOT / ".opencode" / "agents"
    files = sorted(directory.glob("*.md")) if directory.exists() else []
    if not files:
        skip("agent frontmatter", "no agents defined")
        return

    problems = []
    for path in files:
        name = rel(path)
        lines = path.read_text(encoding="utf-8").split("\n")
        if not lines or lines[0].strip() != "---":
            problems.append(f"{name}: must start with a '---' frontmatter fence")
            continue

        try:
            end = next(i for i, line in enumerate(lines[1:], start=1) if line.rstrip() == "---")
        except StopIteration:
            stray = next(
                (line for line in lines[1:] if set(line.strip()) == {"-"} and line.strip()),
                None,
            )
            hint = f" (found {stray.strip()!r})" if stray else ""
            problems.append(f"{name}: frontmatter is not closed by a '---' line{hint}")
            continue

        try:
            meta = yaml.safe_load("\n".join(lines[1:end])) or {}
        except yaml.YAMLError as exc:
            problems.append(f"{name}: frontmatter does not parse: {exc}")
            continue

        for key in ("description", "mode", "model"):
            if not meta.get(key):
                problems.append(f"{name}: missing '{key}'")
        if meta.get("mode") not in (None, "primary", "subagent", "all"):
            problems.append(f"{name}: mode must be primary|subagent|all, got {meta['mode']!r}")

        for key in meta:
            if key in PERMISSION_KEYS and key not in AGENT_TOP_LEVEL_KEYS:
                problems.append(f"{name}: '{key}' is at the top level; nest it under 'permission:'")
            elif key not in AGENT_TOP_LEVEL_KEYS:
                problems.append(f"{name}: unknown frontmatter key {key!r}")

        permission = meta.get("permission")
        if permission is None:
            problems.append(f"{name}: no 'permission' block")
        elif not isinstance(permission, dict):
            problems.append(f"{name}: 'permission' must be a mapping")
        else:
            for key, rules in permission.items():
                if key not in PERMISSION_KEYS:
                    problems.append(f"{name}: unknown permission key {key!r}")
                if isinstance(rules, dict) and rules and next(iter(rules)) != "*":
                    problems.append(
                        f"{name}: permission.{key} must list '*' first - rules are last-match-wins"
                    )

    if problems:
        fail("agent frontmatter", "; ".join(problems))
    else:
        ok("agent frontmatter", f"{len(files)} agent(s)")


# --------------------------------------------------------------------------


CHECKS = (
    check_line_endings,
    check_yaml_parses,
    check_compose,
    check_prometheus,
    check_datasource,
    check_dashboard_provider,
    check_dashboards,
    check_task7_panels,
    check_task9_readme,
    check_agents,
)


def main() -> int:
    for check in CHECKS:
        try:
            check()
        except Exception as exc:  # a broken check must not look like a clean run
            fail(check.__name__, f"check crashed: {exc!r}")

    width = max(len(name) for _, name, _ in RESULTS)
    for status, name, detail in RESULTS:
        print(f"{status}  {name.ljust(width)}  {detail}")

    failures = [r for r in RESULTS if r[0] == "FAIL"]
    print()
    if failures:
        print(f"FAILED - {len(failures)} check(s) need fixing")
        return 1
    skipped = sum(1 for r in RESULTS if r[0] == "SKIP")
    print(f"OK - {len(RESULTS) - skipped} check(s) passed, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
