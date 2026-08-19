# MVP implementation guide — local LLM monitoring

Step-by-step breakdown of `intial_plan.md` for the **first bare-bones version**: Prometheus + Grafana in Docker, one provisioned dashboard, nothing else. Phase 2 (AMD GPU exporter) is out of scope here.

Three checkpoints:

- **Checkpoint A — stack alive** (Tasks 0–4): `docker compose up -d` works, Grafana opens on 3001, Prometheus says llama-server is UP.
- **Checkpoint B — provisioning works** (Tasks 5–6): datasource and a one-panel dashboard are loaded from files.
- **Checkpoint C — data visible** (Task 7): the dashboard has the real panels, and at least one inference request moves the throughput graph.

Then Tasks 8–9 close out the plan's definition-of-done and you stop.

---

## Deployment topology

- **Runs on:** an Ubuntu server — Docker Engine, not Docker Desktop. The monitoring stack and llama-server share this one machine.
- **Existing Docker network:** llama-server and Open WebUI already communicate over a shared user-defined network, and llama-server binds `0.0.0.0` inside its container. Prometheus joins that network to scrape — see correction #3, which supersedes the plan's `host.docker.internal` approach.
- **Authored on:** this Windows box (`C:\LocalCode\amon-hen`). Config files are written here and deployed there, so nothing in this guide should assume the authoring machine at runtime.
- **Viewed from:** a browser on the Windows desktop, over the network. This is the constraint the plan does not account for — see "Reaching the dashboard from Windows" below.

## Environment findings (checked 2026-08-19)

- The authoring machine has Docker 29.5.3 / Compose v5.1.4 with the daemon stopped, which is now irrelevant — what matters is Docker Engine plus the Compose v2 plugin on the Ubuntu server (`docker compose version`, not `docker-compose`).
- `C:\LocalCode\amon-hen` is **not a git repo**. The plan leans on "reproducible from Git" throughout. If you want Git as the Windows-to-Ubuntu transport, run `git init` before Task 1; otherwise copy the `monitoring/` directory by your usual deployment method.
- llama-server's `/metrics` could not be probed from this session, so **all metric names below are unverified**. Task 0 fixes that.

## Three corrections to the plan, before you write anything

1. **Prometheus does not expand environment variables in `prometheus.yml`.** The plan's config philosophy (§19) lists `LLAMA_METRICS_HOST`, `LLAMA_METRICS_PORT`, `SCRAPE_INTERVAL` as env vars, but Prometheus has no native templating — `${VAR}` in that file is read literally and the scrape target silently breaks. For the MVP, write those three values literally into `prometheus.yml` and keep `.env` for the values Compose itself consumes (`GRAFANA_PORT`, `PROMETHEUS_RETENTION`, `PROMETHEUS_RETENTION_SIZE`). If you later want them env-driven, add an `envsubst` entrypoint over a template — not worth it now.

2. **Setting `command:` on `prom/prometheus` replaces the image's default CMD entirely.** The retention flags (§6) require a `command:` block, and the moment you add one you must also re-specify `--config.file` and `--storage.tsdb.path` or Prometheus starts with neither your config nor your volume. The Task 3 snippet does this correctly.

3. **Skip `host.docker.internal` entirely — join the Docker network that already exists.** The plan treats host-gateway routing as the starting point and a shared network as a "later, if desired" option (§3). That ordering assumed no shared network existed. Yours does: llama-server and Open WebUI already talk over one, and llama-server binds `0.0.0.0` inside its container. So attach Prometheus to that same network as an **external** network and scrape the container by name — `llama-server:8080`.

   This is strictly better than the host-gateway route, not just tidier:
   - No dependency on llama-server publishing 8080 to the host. If that publish is ever removed or bound to loopback, monitoring keeps working.
   - No `extra_hosts`, no docker0 gateway address, no host firewall in the path.
   - Traffic stays on the container network instead of hairpinning through the host.

   It costs one thing: Prometheus must know the network's real name and llama-server's container name/alias. Task 0 discovers both. Attaching to an existing network is read-only from that network's point of view — it does not modify llama-server's stack, which is what §3 was protecting.

## Reaching the dashboard from Windows

The loopback binding in the plan means loopback *on the server* — a Windows browser cannot reach it. Use an SSH tunnel; change no config:

```bash
ssh -L 3001:localhost:3001 you@ubuntu-server
```

Browse `http://localhost:3001` on Windows while the session is open. Grafana stays unreachable from the network and `compose.yaml` needs no change. (Do not bind to the LAN — it exposes an admin console to the network for no benefit.)

---

## Task 0 — Verify prerequisites (no code written)

Nothing in this task creates files. It exists because every later task depends on facts you don't have yet.

**Do — all of this on the Ubuntu server, over SSH:**
1. Confirm `docker ps` works without sudo and `docker compose version` reports v2.x.
2. Confirm llama-server was started with `--metrics`. If not, add the flag and restart it — change nothing else about the inference settings.
3. Capture the real metric list:
   ```bash
   curl -s http://localhost:8080/metrics > llama-metrics.txt
   grep '^llamacpp:' llama-metrics.txt | cut -d'{' -f1 | sort -u
   ```
4. **Get the two names correction #3 depends on.** These are the only unknowns that can't be guessed:
   ```bash
   docker network ls
   docker network inspect <llm-network> --format \
     '{{range .Containers}}{{.Name}} {{end}}'
   ```
   Write down the **exact network name** and the **exact llama-server container name**. If llama-server was started by its own Compose file, also check its aliases — Compose registers the *service* name as an alias, which may differ from the container name:
   ```bash
   docker inspect <llama-container> --format \
     '{{range $n, $c := .NetworkSettings.Networks}}{{$n}}: {{$c.Aliases}}{{"\n"}}{{end}}'
   ```
   Either the container name or any alias works as a scrape target. Prefer the service alias if one exists — it survives container recreation.
5. Confirm nothing already holds port 3001: `ss -tln | grep 3001` (expect no output).

**Verify:** you have a concrete list of `llamacpp:*` names on screen. **Keep that list open** — Task 7 writes queries against it, and the names in `intial_plan.md` are from documentation, not from your build. In particular the **speculative-decoding counters vary most between versions**; if you don't see draft/accepted counters at all, MTP metrics may not be exposed and Task 7e becomes a no-op rather than something to debug.

**Blocked if:** `/metrics` returns 404 → the `--metrics` flag didn't take effect.

## Task 1 — Scaffold the directory tree

**Do:** create the layout from §1, empty for now:

```
monitoring/
├── prometheus/
├── grafana/provisioning/datasources/
├── grafana/provisioning/dashboards/
└── grafana/dashboards/
```

Add `.env.example` and a `.gitignore` containing `.env`.

Optional but sensible because you author on Windows and run on Linux: add a `.gitattributes` with `* text=auto eol=lf`. The YAML and JSON parsers tolerate CRLF, so this changes nothing today; it mainly prevents future shell-script surprises.

`.env.example`:
```
GRAFANA_PORT=3001
PROMETHEUS_RETENTION=30d
PROMETHEUS_RETENTION_SIZE=5GB

# Existing Docker network shared with llama-server / Open WebUI (see Task 0).
# The llama-server *container name* is NOT here — it must be literal in
# prometheus/prometheus.yml, which does not expand env vars.
LLM_NETWORK=
```

**Verify:** copy `.env.example` to `.env` on the Ubuntu server. Everything from here runs out of `monitoring/`.

## Task 2 — Write `prometheus/prometheus.yml`

**Do:**
```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 15s

scrape_configs:
  - job_name: llama_cpp
    metrics_path: /metrics
    static_configs:
      - targets:
          - llama-server:8080
```

Replace `llama-server` with the exact container name or alias from Task 0, and `8080` with the port llama-server listens on **inside** its container — not the published host port, if those differ.

That name has to be literal here, not `${LLAMA_CONTAINER}`, because of correction #1. The network name in Task 3 *can* be an env var, since Compose reads that file. It's a slightly awkward split; the comment in `.env.example` should say the container name lives in `prometheus.yml`.

That's the whole file. No alerting, no rule files, no self-scrape.

**Verify:** it's valid YAML. Real validation happens in Task 4.

## Task 3 — Write `compose.yaml`

**Do:**
```yaml
services:
  prometheus:
    image: prom/prometheus
    restart: unless-stopped
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=${PROMETHEUS_RETENTION:-30d}
      - --storage.tsdb.retention.size=${PROMETHEUS_RETENTION_SIZE:-5GB}
    networks:
      - monitoring
      - llm
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus

  grafana:
    image: grafana/grafana
    restart: unless-stopped
    depends_on: [prometheus]
    ports:
      - "127.0.0.1:${GRAFANA_PORT:-3001}:3000"
    networks:
      - monitoring
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro

networks:
  monitoring:
  llm:
    external: true
    name: ${LLM_NETWORK}

volumes:
  prometheus-data:
  grafana-data:
```

Add `LLM_NETWORK=<name from Task 0>` to `.env.example`. `external: true` means Compose expects the network to already exist and **will not create or delete it** — `docker compose down` leaves llama-server's network untouched. If the name is wrong, `up` fails immediately with a clear error rather than starting a half-connected stack.

Only Prometheus joins `llm`; Grafana has no business on that network and doesn't need it. Note also what's **absent**: no port mapping on Prometheus (§ "Grafana should be the only component exposed"). Reach its UI during debugging with `docker compose exec`, or add `127.0.0.1:9090:9090` temporarily — don't leave it in.

**Verify:** `docker compose config` renders with your `.env` values substituted, and the `llm` network resolves to the real name.

## Task 4 — First boot → **CHECKPOINT A**

**Do:** `docker compose up -d`, then `docker compose ps`. Use `docker compose logs -f` only if a container is unhealthy or restart-looping.

**Verify, in order — stop at the first failure:**
1. Both containers are `running`, not restart-looping.
2. Grafana answers **on the server** — `curl -sI http://localhost:3001` returns `302`. Then open the SSH tunnel from Windows and confirm the login page renders in your browser at `http://localhost:3001` (default `admin`/`admin`). Checking both sides separately tells you whether a failure is Grafana or the tunnel.
3. The scrape target is UP:
   ```bash
   docker compose exec prometheus promtool query instant http://localhost:9090 'up{job="llama_cpp"}'
   ```
   Expect a value of `1`. A `0` means Prometheus is running fine but cannot reach llama-server. Confirm which half is broken from inside the container:
   ```bash
   docker compose exec prometheus wget -qO- http://llama-server:8080/metrics | head -5
   ```
   Name resolution failure → Prometheus isn't on the `llm` network, or you have the container name wrong; check with `docker network inspect <llm-network>` and confirm the Prometheus container is now listed among its members. Resolves but connection refused → wrong port, i.e. you used the published host port rather than the in-container one.

Do not continue to Task 5 until `up` is `1`. Every panel in Task 7 depends on it.

## Task 5 — Provision the Prometheus datasource

**Do:** `grafana/provisioning/datasources/prometheus.yml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

**The `uid: prometheus` line is load-bearing.** Grafana otherwise generates a random uid, and the dashboard JSON in Task 6 has to hardcode a datasource reference. Pinning it is what makes the dashboard survive a `docker compose down -v`.

The URL is `http://prometheus:9090` — the Compose service name on the internal network, not localhost.

**Verify:** `docker compose restart grafana`, then in the UI the datasource appears marked as provisioned and its connection test succeeds. Do not edit or save the provisioned datasource in the UI.

## Task 6 — Provision the dashboard loader → **CHECKPOINT B**

**Do:** `grafana/provisioning/dashboards/dashboards.yml`:
```yaml
apiVersion: 1
providers:
  - name: local
    type: file
    allowUiUpdates: false
    options:
      path: /var/lib/grafana/dashboards
```

Then create `grafana/dashboards/llm-overview.json` with **one** panel — server status, `up{job="llama_cpp"}`, as a stat panel. Keep it to one panel deliberately: you are testing the provisioning pipeline, not designing yet.

Three JSON rules that cause silent failures:
- `"id": null` at the top level. A non-null `id` collides with existing dashboards and the file is skipped.
- Set a stable `"uid"` and `"title": "LLM Overview"`.
- Every panel's datasource is `{"type": "prometheus", "uid": "prometheus"}`, matching Task 5.

**Verify:** restart Grafana; "LLM Overview" appears in the dashboard list without anyone touching the UI, and the panel reads UP. That is Checkpoint B — the provisioning pipeline works end to end, and the rest is just panels.

## Task 7 — Build out the panels

One panel at a time, checking each in the UI before moving on. **Write every query against your Task 0 list**, not the names in this file. Dashboard defaults: time range last 30 minutes, refresh 5s.

- **7a — Top stat row (4 panels):** generation tok/s, prompt tok/s, active requests, context max. Likely `llamacpp:predicted_tokens_seconds`, `llamacpp:prompt_tokens_seconds`, `llamacpp:requests_processing`, `llamacpp:n_tokens_max`. These are gauges — graph them directly, no `rate()`.
- **7b — Throughput graph:** the two tok/s gauges on one time series panel. This is the main panel of the dashboard.
- **7c — Request activity:** `llamacpp:requests_processing` and `llamacpp:requests_deferred`, small time series.
- **7d — Token counters:** `llamacpp:prompt_tokens_total`, `llamacpp:tokens_predicted_total`. These are counters — show cumulative totals as stat panels, secondary placement.
- **7e — Speculative decoding:** draft tokens, accepted draft tokens, and acceptance %. **Guard the division** — before any speculative decoding happens the denominator is 0 and the panel shows `NaN`. Replace these placeholders with the exact counter names from Task 0:
  ```promql
  100 * accepted_total / clamp_min(draft_total, 1)
  ```
  If Task 0 found no draft counters, skip this section and say so in the README.

**Verify:** send a real inference request and watch the throughput graph move. A flat zero line during active generation means a wrong metric name, not a broken stack. This is Checkpoint C.

## Task 8 — Persistence check

**Do:** `docker compose down` (**without** `-v`), then `docker compose up -d`.

**Verify:** historical data is still in the throughput graph and the dashboard still loads. This confirms the named volumes are doing their job.

## Task 9 — README and measurements

`monitoring/README.md` gets the four commands (`up -d`, `ps`, `logs -f`, `down`), the dashboard URL, and the required `--metrics` flag on llama-server. Short.

The plan's definition-of-done also requires **three measurements written down** — this is the part that's easy to skip and is genuinely the last real work:

1. `docker stats` for both containers: idle, dashboard open, inference active. Target well under 2 GB total.
2. One identical inference benchmark with monitoring OFF vs ON. A few percent variance is fine; a persistent regression is not.
3. The idle-GPU test: `rocm-smi` baseline, then again after several minutes of scraping with no LLM requests.

**On measurement 3:** `rocm-smi` is a Linux ROCm tool, so on the Ubuntu server this test runs exactly as the plan describes — no caveat. Take the readings even though nothing in Phase 1 touches the GPU: this is the idle baseline the Phase 2 exporter gets compared against, and it is much harder to reconstruct later once the GPU exporter is polling.

---

## Then stop

The plan is explicit about this: once Task 9's checklist passes, don't keep expanding. No Node Exporter, no Loki/Tempo/Alertmanager, no custom frontend. The GPU exporter is a separate Phase 2 effort against a working, measured baseline.
