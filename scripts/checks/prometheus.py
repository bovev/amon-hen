"""Prometheus config — correction 1: no env templating, literal scrape target."""

from __future__ import annotations

from .common import fail, load_yaml, ok, skip, yaml, ROOT

ORDER = 30


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
