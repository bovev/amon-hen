# AGENTS.md

## Sources And Workflow

- This repository is currently documentation-only and is not a Git repository; the `monitoring/` implementation has not been created yet.
- `intial_plan.md` is authoritative for product scope. `tasks/README.md` and `tasks/task-00-prerequisites.md` through `task-09-readme-measurements.md` are authoritative for implementation details and intentionally supersede conflicting examples in `intial_plan.md`, `CLAUDE.md`, and `implementation-guide.md`.
- Execute Tasks 0-9 in order. Task 0 must run first on the Ubuntu deployment server and produce `tasks/00-findings.md`; Tasks 2, 3, and 7 depend on its exact network, scrape-target, and metric findings.
- Author files on Windows, but run deployment and runtime checks on the Ubuntu server using Docker Engine and the Compose v2 plugin (`docker compose`, not `docker-compose`). Use LF line endings because deployment is Linux.

## Architecture Constraints

- Phase 1 contains only Prometheus, Grafana OSS, and one file-provisioned `LLM Overview` dashboard. Do not add the Phase 2 GPU exporter, Node Exporter, Loki, Tempo, Mimir, Alertmanager, databases, proxies, or a custom frontend.
- Do not alter llama-server inference settings beyond enabling `--metrics`, and do not merge its Compose stack into this repository.
- Prometheus must join the existing llama-server/Open WebUI Docker network as an external network and scrape the stable llama-server service alias plus its in-container port. Do not use `host.docker.internal`; only Prometheus joins the external network.
- Publish only Grafana as `127.0.0.1:${GRAFANA_PORT:-3001}:3000`; never expose Prometheus or bind Grafana to the LAN. From Windows, tunnel with `ssh -L 3001:localhost:3001 you@ubuntu-server`.
- Pin the tested images; the task specs currently require `prom/prometheus:v3.13.2` and `grafana/grafana:13.2.0`.
- Use named volumes for `/prometheus` and `/var/lib/grafana`; mount config and dashboards read-only.

## Configuration Traps

- Prometheus does not expand environment variables in `prometheus.yml`. Put the exact scrape alias and in-container port from `tasks/00-findings.md` there literally. `.env` contains only `GRAFANA_PORT` and `LLM_NETWORK`; commit `.env.example`, never `.env`.
- Configure the 5s scrape interval and 30d/5GB retention in `prometheus.yml`. Do not add a Prometheus `command:` block or deprecated retention CLI flags; the official image defaults already match the mounted config and data paths.
- Verify metric names from the deployed server's `/metrics` output recorded by Task 0; examples in the docs are not authoritative. Use throughput gauges directly, without `rate()`.
- Grafana configuration must be file-provisioned, never created or edited in the UI. The datasource URL is `http://prometheus:9090` and its UID must be `prometheus`.
- Provisioned dashboard JSON needs top-level `"id": null`, a stable UID, title `LLM Overview`, and panel datasource `{"type":"prometheus","uid":"prometheus"}`. Keep `allowUiUpdates: false`.
- Label `llamacpp:n_tokens_max` as `CONTEXT HIGH-WATER`; it is not current utilization or the configured context limit.
- Calculate speculative acceptance with a zero guard such as `100 * accepted_total / clamp_min(draft_total, 1)`. If the deployed build exposes no draft counters, omit those panels and document the absence.

## Verification

- Run Compose commands from `monitoring/`. Before first boot, run `docker compose config` and confirm the external network resolves correctly.
- Follow checkpoints rather than building everything at once: Tasks 0-4 prove the stack and `up{job="llama_cpp"} == 1`; Tasks 5-6 prove file provisioning with one status panel; Task 7 adds panels one at a time and verifies a real inference request moves throughput; Tasks 8-9 verify persistence and measurements.
- Query reachability without exposing Prometheus: `docker compose exec prometheus promtool query instant http://localhost:9090 'up{job="llama_cpp"}'`.
- Test persistence with `docker compose down` followed by `docker compose up -d`; never pass `-v` during this test because it deletes the named volumes.
- MVP completion requires real results in `monitoring/README.md`: `docker stats` for idle/dashboard-open/inference states, identical monitoring-OFF versus monitoring-ON inference benchmarks, and `rocm-smi` idle readings before and after several minutes of scraping.
- Once Task 9 and the MVP checklist pass, stop expanding the system.
