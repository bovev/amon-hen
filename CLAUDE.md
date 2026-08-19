# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository currently contains **only `intial_plan.md`** — no code, no git repo, no `monitoring/` directory yet. `intial_plan.md` is the authoritative spec; read it before implementing anything. The sections below describe the target state it defines.

## What this project is

A Docker-based monitoring stack (Prometheus + Grafana OSS) for an **existing, externally-managed local llama.cpp inference server**. The llama-server is *not* part of this repo and its Docker topology must not be modified — the only required change on that side is starting it with `--metrics` so it exposes `http://localhost:8080/metrics`.

Everything is defined as code and provisioned from files. Never configure Grafana through its UI — data sources and dashboards must come from `grafana/provisioning/` so the stack is reproducible from a clean checkout.

## Target layout

```
monitoring/
├── compose.yaml
├── .env.example
├── README.md
├── prometheus/prometheus.yml
├── grafana/
│   ├── provisioning/datasources/prometheus.yml   # points at http://prometheus:9090
│   └── provisioning/dashboards/dashboards.yml    # loads from /var/lib/grafana/dashboards
│   └── dashboards/llm-overview.json
└── exporters/gpu/                                # Phase 2 only
```

## Architecture constraints

- **Only Grafana is published to the host**, bound to `127.0.0.1:3001` (port 3000 is taken by an existing Open WebUI). Prometheus stays on the internal Docker network.
- **Prometheus reaches llama-server via the host**, using `extra_hosts: ["host.docker.internal:host-gateway"]` and scraping `host.docker.internal:8080`. Do not merge the two Compose stacks to make monitoring work.
- **Named volumes** (`prometheus-data`, `grafana-data`) hold persistent state; bind mounts for config are read-only (`:ro`).
- Scrape interval 5s (not 1s). Retention ~30d with a ~5GB TSDB ceiling.
- Configurable values live in `.env` / environment, not hardcoded: `GRAFANA_PORT`, `LLAMA_METRICS_HOST`, `LLAMA_METRICS_PORT`, `PROMETHEUS_RETENTION`, `SCRAPE_INTERVAL`. Commit `.env.example` only.

### Deliberately excluded

Loki, Tempo, Mimir, Alertmanager, Postgres, Redis, nginx, and Node Exporter are all out of scope. Do not add them. Do not build a custom frontend.

## Commands (once `monitoring/` exists — run from that directory)

```bash
docker compose up -d          # start
docker compose ps             # status
docker compose logs -f        # logs
docker compose down           # stop
docker stats                  # resource measurement (required by the MVP checklist)
```

Dashboard: http://localhost:3001

## Working with llama.cpp metrics

**Always verify metric names against the running server before writing dashboard queries** — `curl http://localhost:8080/metrics` — rather than trusting the names listed in the plan or in older examples. The installed llama.cpp version is the source of truth. Metric names are namespaced `llamacpp:` (e.g. `llamacpp:prompt_tokens_seconds`, `llamacpp:predicted_tokens_seconds`, `llamacpp:requests_processing`, `llamacpp:requests_deferred`, `llamacpp:n_tokens_max`).

Speculative decoding (MTP) is in use, so the dashboard includes a draft-token acceptance rate; the query must handle division by zero when no speculative decoding has occurred yet.

Server reachability is shown with the standard `up{job="llama_cpp"}`.

## Phasing

- **Phase 1 (MVP):** Prometheus + Grafana + the `LLM Overview` dashboard only. `intial_plan.md` ends with an explicit definition-of-done checklist — when those items pass, **stop expanding the system**.
- **Phase 2:** a small custom AMD GPU exporter wrapping `rocm-smi --json`, exposing only the handful of metrics listed in the plan. Expose only values the hardware actually reports (voltage in particular is optional). Do not install a large GPU-monitoring system.

## Required documentation in `monitoring/README.md`

The MVP is not done until the README records the measurement results, not just the commands:

- `docker stats` for each container while idle, with the dashboard open, and during inference (target: well under 2 GB RAM total).
- An identical inference benchmark with monitoring OFF vs ON — a few percent variance is fine, a persistent throughput regression is not.
- The idle-GPU acceptance test: baseline `rocm-smi` readings, then again after several minutes of Prometheus scraping with no LLM requests, confirming the GPU still settles to the same idle state.
