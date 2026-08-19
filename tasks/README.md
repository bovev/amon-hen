# Task index — local LLM monitoring MVP

`../implementation-guide.md` split into one file per task. Each task file is self-contained: it states what it depends on, what it produces, and how you know it's done. Work them in order.

Source of truth for scope is `../intial_plan.md`. This directory is how it gets built.

## Checkpoints

| Checkpoint | Tasks | Means |
|---|---|---|
| **A — stack alive** | 0–4 | `docker compose up -d` works, Grafana opens on 3001, Prometheus says llama-server is UP |
| **B — provisioning works** | 5–6 | Datasource and a one-panel dashboard load from files, no UI clicking |
| **C — data visible** | 7 | Real panels, and an inference request moves the throughput graph |
| *close-out* | 8–9 | Persistence confirmed, README and measurements written — then stop |

## Tasks

| # | File | Produces | Runs on |
|---|---|---|---|
| 0 | [task-00-prerequisites.md](task-00-prerequisites.md) | `00-findings.md` | Ubuntu server |
| 1 | [task-01-scaffold.md](task-01-scaffold.md) | directory tree, `.env.example`, `.gitignore` | either |
| 2 | [task-02-prometheus-config.md](task-02-prometheus-config.md) | `prometheus/prometheus.yml` | either |
| 3 | [task-03-compose.md](task-03-compose.md) | `compose.yaml` | either |
| 4 | [task-04-first-boot.md](task-04-first-boot.md) | *(nothing — verification)* | Ubuntu server |
| 5 | [task-05-datasource.md](task-05-datasource.md) | `grafana/provisioning/datasources/prometheus.yml` | either |
| 6 | [task-06-dashboard-provisioning.md](task-06-dashboard-provisioning.md) | `dashboards.yml`, one-panel `llm-overview.json` | either |
| 7 | [task-07-panels.md](task-07-panels.md) | full `llm-overview.json` | either |
| 8 | [task-08-persistence.md](task-08-persistence.md) | *(nothing — verification)* | Ubuntu server |
| 9 | [task-09-readme-measurements.md](task-09-readme-measurements.md) | `monitoring/README.md` | Ubuntu server |

Task 0 is the only one that must complete before anything else can be written correctly — Tasks 2, 3 and 7 all consume its findings.

---

## Shared context

Every task file assumes the following. Read once; the task files don't repeat it.

### Deployment topology

- **Runs on:** an Ubuntu server — Docker Engine, not Docker Desktop. The monitoring stack and llama-server share this one machine.
- **Existing Docker network:** llama-server and Open WebUI already communicate over a shared user-defined network, and llama-server binds `0.0.0.0` inside its container. Prometheus joins that network to scrape.
- **Authored on:** a Windows box (`C:\LocalCode\amon-hen`). Config is written there and deployed to the server, so nothing may assume the authoring machine at runtime.
- **Viewed from:** a browser on the Windows desktop, over an SSH tunnel.

### Four corrections to `intial_plan.md`

These are deviations from the plan, decided deliberately. Each task file references them by number.

**1 — Prometheus does not expand environment variables in `prometheus.yml`.** The plan's §19 lists `LLAMA_METRICS_HOST`, `LLAMA_METRICS_PORT`, `SCRAPE_INTERVAL` as env vars, but Prometheus has no native templating: `${VAR}` is read literally and the scrape target silently breaks. Write those values literally into `prometheus.yml`; keep `.env` for the two values Compose itself consumes (`GRAFANA_PORT`, `LLM_NETWORK`).

**2 — Retention goes in `prometheus.yml`, not CLI flags.** §6 implies `--storage.tsdb.retention.time` / `.size` via a `command:` block, but those flags are deprecated in favour of config-file settings. With retention in the config file, the Prometheus service needs **no `command:` block at all** — the official image already defaults to `/etc/prometheus/prometheus.yml` and `/prometheus`, exactly what the volumes mount. This removes the whole class of bug where overriding `command:` drops the default CMD and detaches Prometheus from its config or its data volume. Retention also stays out of `.env`: 30d/5GB is a set-once decision.

**3 — Skip `host.docker.internal`; join the network that already exists.** The plan treats host-gateway routing as the starting point and a shared network as a "later, if desired" option (§3) — an ordering that assumed no shared network existed. Attach Prometheus to the existing network as an **external** network and scrape the container by name (`llama-server:8080`). This removes any dependency on llama-server publishing 8080 to the host, removes `extra_hosts` and the docker0 gateway from the path, and keeps traffic on the container network. Attaching to an existing network does not modify llama-server's stack, which is what §3 was protecting.

**4 — Pin the image versions.** The plan's snippet uses bare `prom/prometheus` and `grafana/grafana`, i.e. floating `latest`, which contradicts its own "fully defined as code" objective. Pin `prom/prometheus:v3.13.2` (current LTS) and `grafana/grafana:13.2.0`. Which Grafana 13.x patch you start on barely matters; pinning **the version you tested** is the point.

### Reaching the dashboard from Windows

The plan's loopback binding means loopback *on the server* — a Windows browser cannot reach it. Use an SSH tunnel, change no config:

```bash
ssh -L 3001:localhost:3001 you@ubuntu-server
```

Browse `http://localhost:3001` on Windows while that session is open. Do not bind Grafana to the LAN — it exposes an admin console to the network for no benefit.

---

## Then stop

Once Task 9 passes, stop expanding. No Node Exporter, no Loki/Tempo/Alertmanager, no custom frontend. The AMD GPU exporter is a separate Phase 2 effort against a working, measured baseline.
