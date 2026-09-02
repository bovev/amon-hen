---
task: 7
status: done
accepted_at: 72952c6
---

# Task 7 — Build out the panels → **CHECKPOINT C**

**Depends on:** Task 6 (Checkpoint B), Task 0 (metric names)
**Produces:** full `grafana/dashboards/llm-overview.json`
**Runs on:** either machine
**Checkpoint:** C — data visible

The largest task, so work it one panel at a time and check each in the UI before moving on. **Write every query against `00-findings.md`**, not against the names below — those come from the plan's documentation, not from your build.

Dashboard defaults: time range **last 30 minutes**, refresh **5s**.

## 7a — Top stat row (4 panels)

Generation tok/s, prompt tok/s, active requests, context high-water. Likely `llamacpp:predicted_tokens_seconds`, `llamacpp:prompt_tokens_seconds`, `llamacpp:requests_processing`, `llamacpp:n_tokens_max`.

These are gauges — graph them directly, no `rate()`.

**Title the fourth panel `CONTEXT HIGH-WATER`, not `CONTEXT` or `CONTEXT MAX`.** `llamacpp:n_tokens_max` is the high-water mark of observed context size — the largest seen so far, which never decreases. "Context max" reads as the configured limit; bare "context" reads as current utilisation. Either label would have you misreading the number during normal use, and neither would look wrong.

A current-vs-configured display (`67,420 / 110,000`) is genuinely more useful, but it is **not available from this endpoint** — it needs a separate `/slots`-based collector, which is out of scope. Record that in the README (Task 9) so it's a known gap rather than something to rediscover.

## 7b — Throughput graph

The two tok/s gauges on one time series panel. This is the main panel of the dashboard (plan §9).

## 7c — Request activity

`llamacpp:requests_processing` and `llamacpp:requests_deferred`, small time series. Mostly flat now; it earns its place once multiple agents hit the server concurrently.

## 7d — Token counters

`llamacpp:prompt_tokens_total`, `llamacpp:tokens_predicted_total`. These are counters, not gauges — show cumulative totals as stat panels, in secondary placement. They're diagnostic history, and the plan is explicit that they shouldn't dominate.

## 7e — Speculative decoding

Draft tokens, accepted draft tokens, and acceptance %.

**Guard the division.** Before any speculative decoding has happened the denominator is 0 and the panel shows `NaN`. Replace the placeholders with the exact counter names from `00-findings.md`:

```promql
100 * accepted_total / clamp_min(draft_total, 1)
```

If Task 0 found no draft counters, **skip this section and say so in the README** — that's a documented absence, not a failure.

## Verify

Send a real inference request and watch the throughput graph move.

A flat zero line during active generation means a wrong metric name, not a broken stack — go back to `00-findings.md` rather than to the Compose file.

## Done when

All panels render real values and an inference request visibly moves the throughput graph. That is Checkpoint C.
