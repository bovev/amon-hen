---
task: 2
status: done
accepted_at: 837d789
---

# Task 2 — Write `prometheus/prometheus.yml`

**Depends on:** Task 0 (scrape target), Task 1 (tree)
**Produces:** `monitoring/prometheus/prometheus.yml`
**Runs on:** either machine
**Checkpoint:** none (feeds A)

## Do

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 15s

storage:
  tsdb:
    retention:
      time: 30d
      size: 5GB

scrape_configs:
  - job_name: llama_cpp
    metrics_path: /metrics
    authorization:
      type: Bearer
      credentials_file: /run/secrets/llama_api_key
    static_configs:
      - targets:
          - llama-server:8080
```

That is the whole file. No alerting, no rule files, no self-scrape.

## Two things to get right

**The scrape target is literal.** Replace `llama-server:8080` with the exact name and **in-container** port from `00-findings.md` — not the published host port, if they differ. It cannot be `${LLAMA_CONTAINER}`: Prometheus does not expand env vars (correction #1). This is the awkward half of the split, so the comment in `.env.example` points here.

**Retention lives here, not in Compose** (correction #2). The CLI flags `--storage.tsdb.retention.time` / `.size` are deprecated in favour of these settings, and keeping them out of Compose is what lets Task 3 omit `command:` entirely.

`scrape_interval: 5s` is deliberate — token-generation metrics are worth watching live. The plan explicitly rules out 1s polling.

## Verify

Valid YAML. Real validation happens at Task 4; a syntax error there shows as Prometheus restart-looping on boot.

## Done when

The file exists with your real scrape target substituted in.
