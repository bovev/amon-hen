# LLM Monitoring — Phase 1

Prometheus + Grafana OSS monitoring an existing llama.cpp `llm-server`
container over its existing Docker network (`ai-net`), with one
file-provisioned `LLM Overview` dashboard. Everything is provisioned
from files in this directory; nothing is configured in the Grafana UI.

## Commands

Run from this directory on the Ubuntu server:

```bash
docker compose up -d     # start
docker compose ps        # status
docker compose logs -f   # logs
docker compose down      # stop
```

## Dashboard

Grafana is published to the server's loopback only
(`127.0.0.1:${GRAFANA_PORT:-3001}`; port 3000 is taken by an existing
Open WebUI). From a Windows machine, open a tunnel first:

```bash
ssh -L 3001:localhost:3001 you@ubuntu-server
```

Then browse `http://localhost:3001` while the tunnel is open (default
login `admin` / `admin`).

## llama-server requirement

llama-server must run with `--metrics` so it exposes `/metrics` on its
container port. That is the only change on the llama-server side; its
Compose stack stays separate from this repository.

## Pinned images

Tested and deployed with:

- `prom/prometheus:v3.13.2`
- `grafana/grafana:13.2.0`

## Dashboard notes

- **`CONTEXT HIGH-WATER`** shows `llamacpp:n_tokens_max`, which is a
  high-water mark: the largest token count the server has observed so
  far. It never decreases and is not current context utilisation or the
  configured context capacity. Current-vs-configured would need a
  `/slots`-based collector — out of scope for Phase 1 (known gap).
- **Speculative-decoding panels** are present because the deployed
  server exposes the `llamacpp:spec_decode_*` counters:
  `Speculative Acceptance %`, `Speculative Draft Tokens`,
  `Speculative Accepted Draft Tokens`.

## Measurements

All three readings are taken on the Ubuntu server and are the
definition-of-done for Phase 1.

### 1. Resource usage

`docker stats` for both containers in three states — idle, dashboard
open, inference active. Target: well under 2 GB total (a project goal,
not an upstream guarantee).

```bash
docker stats --no-stream monitoring-prometheus-1 monitoring-grafana-1
```

Values are MEM USAGE from `docker stats`:

| state | prometheus | grafana | total |
| --- | --- | --- | --- |
| idle | 26.82 MiB | 242.3 MiB | 269.12 MiB |
| dashboard open | 40.14 MiB | 275 MiB | 315.14 MiB |
| inference active | 39.15 MiB | 424.8 MiB | 463.95 MiB |

Result: PASS — all states well under 2 GiB total (269.12 / 315.14 /
463.95 MiB; target was well under 2 GB total).

### 2. Monitoring ON vs OFF

One identical inference benchmark, run against the same server both ways
in a controlled test suite: same model (Qwen3.8 27B dense), identical
prompt, identical API, identical API client, and identical generation
settings for both runs.

1. OFF: `docker compose down`, run the benchmark, record output tok/s.
2. ON: `docker compose up -d`, run the same benchmark, record output
   tok/s.

| run | monitoring | output tok/s |
| --- | --- | --- |
| 1 | OFF | 55.32 tok/s |
| 2 | ON | 54.50 tok/s |

Raw response fields (the sustained generation rate is the compared
metric):

| run | prompt tokens (cached) | completion tokens | predicted_ms |
| --- | --- | --- | --- |
| 1 | 83 (79) | 9161 | 165608.065 |
| 2 | 83 (0) | 9842 | 180590.038 |

The runs differ in prompt-cache state (79 vs 0 cached tokens) and
completion length (9161 vs 9842 tokens); the sustained generation rate
(`predicted_per_second`) is what is compared. Monitoring ON is
approximately 1.48% slower than OFF (54.50 vs 55.32 tok/s), which is
normal run-to-run variance, not a clear persistent regression.

Result: PASS - no clear persistent regression; the ~1.48% difference is
within normal run-to-run variance.

### 3. Idle GPU behaviour

`rocm-smi` baseline first (monitoring stopped), then again after several
minutes of Prometheus scraping with no LLM requests (monitoring
running). It passes if the GPU settles into essentially the same idle
state. Nothing in Phase 1 touches the GPU — these readings are the idle
baseline the Phase 2 exporter gets compared against. VRAM is a
percentage of allocated VRAM, not memory-used bytes.

```bash
rocm-smi
```

| reading | temperature | power | SCLK | MCLK | fan | VRAM | GPU use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 31.0 C | 1.0 W | 0 MHz | 96 MHz | 20.0% | 91% | 0% |
| after scraping | 30.0 C | 1.0 W | 0 MHz | 96 MHz | 20.0% | 91% | 0% |

Result: PASS — essentially identical idle state (0% GPU use and 1.0 W in
both; only a 1 C temperature difference).
