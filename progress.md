# Progress — Task 3 (`monitoring/compose.yaml`)

IMPLEMENTATION_COMPLETE

## Files changed
- `monitoring/compose.yaml` (new)

## What changed
Wrote `monitoring/compose.yaml` with the minimal valid Compose structure satisfying all Task 3 invariants. The task's YAML block is indentation-invalid as printed (a top-level `secrets:` key appears mid-`services:` with `grafana` nested under it), so it was not reproduced literally; instead the declared intent was implemented:

- `services.prometheus` — `prom/prometheus:v3.13.2`, `restart: unless-stopped`,
  networks `monitoring` + `llm`, read-only bind mount
  `./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro`,
  named volume `prometheus-data:/prometheus`, and service-level
  `secrets: [llama_api_key]` (required so the file-backed secret is
  materialized at `/run/secrets/llama_api_key` for Task 2's
  `credentials_file`; the default Compose secret path is exactly that).
- `services.grafana` — `grafana/grafana:13.2.0`, `restart: unless-stopped`,
  `depends_on: [prometheus]`, port `127.0.0.1:${GRAFANA_PORT:-3001}:3000`
  (only published port in the stack; loopback only), network `monitoring`
  only, named volume `grafana-data:/var/lib/grafana`, read-only mounts
  `./grafana/provisioning:/etc/grafana/provisioning:ro` and
  `./grafana/dashboards:/var/lib/grafana/dashboards:ro`.
- Top-level `secrets.llama_api_key: environment: LLAMA_API_KEY` — value
  sourced from the runtime environment only; no secret material is stored
  in the file or anywhere tracked.
- Top-level `networks` — `monitoring` (default, compose-created) and
  `llm` (`external: true`, `name: ${LLM_NETWORK}`).
- Top-level `volumes` — `prometheus-data`, `grafana-data`.
- No `command:` block anywhere (retention lives in `prometheus.yml`,
  per Task 2 / correction #2); no port mapping on Prometheus;
  Prometheus is the only service attached to the external `llm` network.

Nothing else was touched (no task files, no task status, no `up` run).
No real secret values were read from or copied into any tracked file;
the untracked root `.env` was not opened.

## Verification performed
- Structural review against task invariants: images pinned
  (`v3.13.2` / `13.2.0`), restart policies, network membership,
  `:ro` on all three config bind mounts, named data volumes, single
  Grafana port on `127.0.0.1`, `external: true` + `name: ${LLM_NETWORK}`
  on `llm`, no Prometheus port, no `command:`.
- Line endings: byte-level check of `monitoring/compose.yaml` —
  0 CR bytes (830 bytes total), i.e. LF-only, consistent with
  `.gitattributes` (`* text=auto eol=lf`).

## Verification NOT performed
- `docker compose config` (with safe temporary values
  `LLM_NETWORK=ai-net`, dummy `LLAMA_API_KEY`, default/explicit
  `GRAFANA_PORT`) was prepared but the tool call was rejected by the
  user; therefore rendered-environment validation did not run.
  Docker Compose v5.1.4 is available on this machine, so the check
  remains runnable as-is when permitted.

## Known concerns
- The Compose rendering check is still outstanding (see above). The file
  is hand-verified structurally but has not been parsed by Compose itself.
- At `up` time (Task 4) the `LLAMA_API_KEY` environment variable must be
  set for the host shell running Compose; otherwise secret provisioning
  will fail (intended behavior, fails loudly rather than silently).
- `monitoring/grafana/provisioning` and `monitoring/grafana/dashboards`
  are currently empty (Task 1 scaffold); bind-mount sources do not need to
  contain files for `config` to pass, and content arrives in Tasks 5–6.
