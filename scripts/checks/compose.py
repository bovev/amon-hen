"""Compose invariants — AGENTS.md: pinned images, loopback-only Grafana,
read-only config mounts, named volumes, external llm network."""

from __future__ import annotations

from .common import fail, load_yaml, ok, skip, yaml, ROOT

ORDER = 20


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
