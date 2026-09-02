"""Grafana provisioning — file-provisioned datasource, dashboard provider, and
the dashboard JSON invariants that apply to every dashboard.

``walk_panels`` lives here because it is the shared way to traverse a dashboard;
task-specific panel checks import it rather than reimplementing it.
"""

from __future__ import annotations

import json

from .common import fail, load_yaml, ok, rel, skip, yaml, ROOT

ORDER = 40


def walk_panels(panels):
    for panel in panels or []:
        yield panel
        yield from walk_panels(panel.get("panels"))


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

        for panel in walk_panels(doc.get("panels")):
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
