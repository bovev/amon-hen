# Progress — Task 4 (first-boot verification)

IMPLEMENTATION_COMPLETE

## Files changed
- `tasks/04-findings.md` (new)
- `monitoring/prometheus/prometheus.yml` (scrape target corrected to `llm-server:8080`)

## What changed
Verified the full stack boots and Prometheus successfully scrapes llama-server.
The only code change was correcting the scrape target in `prometheus.yml`
from `llama-server:8080` to `llm-server:8080` (the live container name).

## Verification performed
- `docker compose up -d` — both containers start cleanly.
- `docker compose ps` — both `running`, correct restart policy.
- `docker port monitoring-grafana-1` — only `127.0.0.1:3001 -> 3000/tcp`.
- `docker network inspect ai-net` — Prometheus attached, DNS = 127.0.0.11.
- `nslookup llm-server` inside Prometheus — resolves to 172.18.0.5.
- Direct unauthenticated `curl 172.18.0.5:8080/metrics` — 401 (auth layer active).
- `promtool query instant 'up{job="llama_cpp"}'` — returns `1`.

## Troubleshooting
- Initial target `llama-server` did not resolve; the live container is named
  `llm-server` with no network alias. Fixed via:
  `docker network connect --alias llm-server ai-net llm-server`
- `wget` in the Prometheus image reports "bad address" for hostnames even when
  DNS resolves (implementation limitation). `nslookup` and the Prometheus
  scrape itself confirm connectivity; the `up` metric is authoritative.

## Known concerns
- The `llm-server` alias is runtime-only. It must be persisted in the external
  Compose/stack file that manages the llama container so it survives recreation.
- `tasks/00-findings.md` already records `llm-server:8080` as the target
  (line 2), so it is consistent.

## Next
Task 5 — Grafana datasource provisioning.
