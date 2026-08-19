# Task 3 — Write `compose.yaml`

**Depends on:** Task 0 (network name), Task 1 (`.env`), Task 2 (config file to mount)
**Produces:** `monitoring/compose.yaml`
**Runs on:** either machine
**Checkpoint:** none (feeds A)

## Do

```yaml
services:
  prometheus:
    image: prom/prometheus:v3.13.2
    restart: unless-stopped
    networks:
      - monitoring
      - llm
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus

  grafana:
    image: grafana/grafana:13.2.0
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

## Why it looks like this

**No `command:` block** (correction #2). The official Prometheus image already defaults to `/etc/prometheus/prometheus.yml` and `/prometheus` — exactly the two mount points above — and retention now lives in the config file. Adding a `command:` would replace the image's default CMD, and forgetting to re-specify those paths detaches Prometheus from its config or its data volume.

**`external: true` on the `llm` network** (correction #3). Compose expects the network to already exist and will neither create nor delete it, so `docker compose down` cannot touch llama-server's networking. A wrong name fails loudly at `up` rather than starting a half-connected stack. Only Prometheus joins it — Grafana has no business on that network.

**Pinned image tags** (correction #4). Record whichever tags you actually test; the point is that upgrades become a deliberate edit rather than a side effect of the next `pull`.

**No port mapping on Prometheus.** The plan requires Grafana to be the only exposed component. Reach the Prometheus UI during debugging with `docker compose exec`, or add `127.0.0.1:9090:9090` temporarily — don't leave it in.

**Grafana on `127.0.0.1`.** That is loopback *on the server*; you reach it from Windows over the SSH tunnel (see the index). Do not change this to `0.0.0.0`.

## Verify

```bash
docker compose config
```

Renders with your `.env` values substituted, and the `llm` network resolves to the real name from `00-findings.md`.

## Done when

`docker compose config` is clean. Do not run `up` yet — that's Task 4, which has its own verification order.
