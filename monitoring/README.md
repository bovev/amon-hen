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

## vLLM requirement

A vLLM server (dual R9700) is monitored alongside llama.cpp by the `vllm`
scrape job and the `vLLM Overview` dashboard. The two backends are run one
at a time: both jobs stay configured, and whichever server is stopped reads
**DOWN** on its dashboard.

vLLM serves `/metrics` on its API port by default, so no extra flag is needed.
The container must join `ai-net` under the stable alias `vllm-server`. Prometheus
scrapes `vllm-server:8080`, so the container name can change with the model
without touching `prometheus.yml`. Add these to the vLLM `docker run` command:

```bash
--network ai-net --network-alias vllm-server
```

or attach a running container once:

```bash
docker network connect --alias vllm-server ai-net <vllm-container>
```

vLLM's `--api-key` guards only `/v1/*`, so the `vllm` job scrapes without
credentials. If a future vLLM version starts returning 401 on `/metrics`, add
an `authorization` block to the job the same way `llama_cpp` does.

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
  `Speculative Accepted Draft Tokens`. Upstream now documents
  `spec_decode_num_draft_tokens_total`,
  `spec_decode_num_accepted_tokens_total`, `spec_decode_num_drafts_total`
  and `spec_decode_num_accepted_tokens_per_pos_total`; all four read 0
  while speculative decoding is off, and the per-position counter is
  absent until the first speculative request completes.
- **Throughput is derived from counters, not from the tok/s gauges.**
  `llamacpp:predicted_tokens_seconds` and `llamacpp:prompt_tokens_seconds`
  look like the obvious choice, but upstream computes them over the window
  since the *last poll* and resets that bucket on every `/metrics` **and**
  `/health` request — the two share one task type. Any second poller (a
  container `HEALTHCHECK`, a load balancer, a curl in a terminal) therefore
  drains the bucket between Prometheus scrapes and the panels read 0 during
  active generation. `Generation tok/s`, `Prompt tok/s` and `Throughput`
  instead divide the token counter's rate by the matching seconds counter's
  rate:

  ```promql
  rate(llamacpp:tokens_predicted_total[$__rate_interval])
    / clamp_min(rate(llamacpp:tokens_predicted_seconds_total[$__rate_interval]), 0.001)
  ```

  The counters are monotonic, so no other poller can disturb them. This
  reads tokens per second *of processing time* — the same quantity the
  gauge claimed to report — and `clamp_min` keeps an idle server (`0 / 0`)
  at 0 instead of `NaN`. `scripts/checks/task_07_panels.py` fails the build
  if either gauge comes back into the dashboard.
- **The `Throughput` graph gates both series on `> 0`; the stat panels do
  not.** That `clamp_min` 0 is what the `Generation tok/s` and `Prompt tok/s`
  stat panels want: they reduce with `lastNotNull`, so an idle server reads
  0 rather than a stale figure from ten minutes ago. The `Throughput` graph
  wants the opposite. Its legend is a table with a **Mean** column, and an
  idle server emits one real 0 every 5s scrape — over the default 30-minute
  range those zeros swamp the average and the mean decays toward 0 no matter
  how fast generation actually ran. Both of its targets therefore end in
  `> 0`:

  ```promql
  rate(llamacpp:tokens_predicted_total[$__rate_interval])
    / clamp_min(rate(llamacpp:tokens_predicted_seconds_total[$__rate_interval]), 0.001)
    > 0
  ```

  A bare PromQL comparison (no `bool`) *filters* rather than returning 0/1,
  so idle scrapes produce no sample at all and Grafana's mean — which divides
  by the non-null count — covers active generation only. The visible
  consequence is intended: the line breaks instead of flatlining at 0 while
  idle, and if the server was idle for the whole selected range the panel
  reads **No data**.

## vLLM dashboard notes

Every query uses only metric names confirmed on the deployed server
(`tasks/vllm-findings.md`); `scripts/checks/vllm_panels.py` fails the build
if a panel queries anything else. When upgrading vLLM, re-read `/metrics`
and update both.

- **The dashboard is built around concurrency.** The panels that show
  saturation are `Running vs Waiting` (concurrency actually achieved vs
  requests left in the queue), `KV Cache Usage`, `Preemptions / min` (requests
  evicted because the KV cache ran out), `Queue Time`, and `Tokens per Engine
  Step` (how full each batch is). Waiting > 0 together with KV cache near 100%
  or preemptions > 0 means concurrency is above what the cache holds.
- **Two throughput figures.** `Generation tok/s (total)` is wall-clock tokens
  per second summed over *all* concurrent requests. `Per-request tok/s` is
  the speed one user sees: `1 / mean time-per-output-token` of the requests
  that finished in the window, so it updates when requests complete. Neither
  is the same quantity as llama.cpp's per-processing-time tok/s; do not
  compare the two dashboards 1:1.
- **Latency panels are p50/p95 from histograms**
  (`histogram_quantile` over `sum by (le)`). With no requests in the window
  the quantile is undefined and the line breaks, which is expected.
- **Inter-token latency with speculative decoding** measures the gap between
  output chunks, and one chunk can hold several accepted tokens. That is
  why per-request speed comes from `request_time_per_output_token`, not
  `1 / ITL`.
- **Speculative decoding.** `Speculative Acceptance %` and `Mean Acceptance
  Length` (accepted drafts per step + 1 bonus token) are since server start;
  `Acceptance % over Time` is windowed. `Acceptance % by Draft Position`
  shows how often the k-th draft token survives. A steep drop after the
  first positions means fewer speculative tokens would do as well.
- **`(range)` stats** (prefix cache hit %, average prompt/generated tokens
  per request, requests finished) use `increase(...[$__range])`, so they
  follow the selected time range.
- The same idle rules as `LLM Overview` apply: every division uses
  `clamp_min`, time series filter idle samples with `> 0` where a legend
  mean is shown, and stat panels do not.

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
