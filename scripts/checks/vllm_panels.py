"""vLLM Overview dashboard (monitoring/grafana/dashboards/vllm-overview.json).

The dashboard is checked by the rules its queries must follow rather than by
pinning every expression:

- Every ``vllm:`` series it queries is in CONFIRMED_METRICS, the list read from
  the deployed server's /metrics (tasks/vllm-findings.md). vLLM has renamed
  metrics between versions (gpu_cache_usage_perc -> kv_cache_usage_perc,
  time_per_output_token_seconds -> inter_token_latency_seconds), and a wrong
  name renders as a silent "No data", never an error.
- Every division is guarded with clamp_min so an idle server reads 0, not NaN.
- Stat panels reduce to a single lastNotNull value and never carry the `> 0`
  idle filter; that filter belongs on time series only (see the idle-zero note
  in task_07_panels.py - the same reasoning applies here).
- The panels that answer the concurrency questions are present.
"""

from __future__ import annotations

import json
import re

from .common import fail, ok, skip, ROOT
from .grafana import walk_panels

ORDER = 55

VLLM_DASHBOARD = "monitoring/grafana/dashboards/vllm-overview.json"

# Metric families exposed by the deployed vLLM server, without the
# _bucket/_count/_sum/_created suffixes. Update from a fresh
# `curl .../metrics` (and tasks/vllm-findings.md) when vLLM is upgraded.
CONFIRMED_METRICS = {
    "vllm:cache_config_info",
    "vllm:e2e_request_latency_seconds",
    "vllm:engine_sleep_state",
    "vllm:estimated_flops_per_gpu_total",
    "vllm:estimated_read_bytes_per_gpu_total",
    "vllm:estimated_write_bytes_per_gpu_total",
    "vllm:external_prefix_cache_hits_total",
    "vllm:external_prefix_cache_queries_total",
    "vllm:generation_tokens_total",
    "vllm:inter_token_latency_seconds",
    "vllm:iteration_tokens_total",
    "vllm:kv_cache_usage_perc",
    "vllm:mm_cache_hits_total",
    "vllm:mm_cache_queries_total",
    "vllm:num_preemptions_total",
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
    "vllm:num_requests_waiting_by_reason",
    "vllm:prefix_cache_hits_total",
    "vllm:prefix_cache_queries_total",
    "vllm:prompt_tokens_by_source_total",
    "vllm:prompt_tokens_cached_total",
    "vllm:prompt_tokens_total",
    "vllm:request_decode_time_seconds",
    "vllm:request_generation_tokens",
    "vllm:request_inference_time_seconds",
    "vllm:request_max_num_generation_tokens",
    "vllm:request_params_max_tokens",
    "vllm:request_params_n",
    "vllm:request_prefill_kv_computed_tokens",
    "vllm:request_prefill_time_seconds",
    "vllm:request_prompt_tokens",
    "vllm:request_queue_time_seconds",
    "vllm:request_success_total",
    "vllm:request_time_per_output_token_seconds",
    "vllm:spec_decode_num_accepted_tokens_per_pos_total",
    "vllm:spec_decode_num_accepted_tokens_total",
    "vllm:spec_decode_num_drafts_total",
    "vllm:spec_decode_num_draft_tokens_total",
    "vllm:time_to_first_token_seconds",
    "vllm:tool_call_parser_invocations_total",
}

# Histogram and counter sample suffixes. iteration_tokens_total is a histogram
# whose family name already ends in _total, so strip only the sample suffix.
SAMPLE_SUFFIXES = ("_bucket", "_count", "_sum", "_created")

METRIC_RE = re.compile(r"vllm:[a-zA-Z0-9_]+")

# title -> panel type; the concurrency-first panels this dashboard exists for.
REQUIRED_PANELS = {
    "Server Status": "stat",
    "Running Requests": "stat",
    "Waiting Requests": "stat",
    "KV Cache Usage": "gauge",
    "Generation tok/s (total)": "stat",
    "Per-request tok/s": "stat",
    "Throughput": "timeseries",
    "Running vs Waiting": "timeseries",
    "KV Cache Usage %": "timeseries",
    "Preemptions / min": "timeseries",
    "Queue Time": "timeseries",
    "Time to First Token": "timeseries",
    "Inter-token Latency": "timeseries",
    "End-to-end Request Latency": "timeseries",
    "Speculative Acceptance %": "stat",
}


def family(name: str) -> str:
    for suffix in SAMPLE_SUFFIXES:
        if name.endswith(suffix) and name[: -len(suffix)] in CONFIRMED_METRICS:
            return name[: -len(suffix)]
    return name


def unguarded_divisions(expr: str) -> list[str]:
    """Denominators that are not wrapped in clamp_min (directly or via scalar())."""
    bad = []
    for match in re.finditer(r"/\s*(\S+)", expr):
        denominator = match.group(1)
        if not denominator.startswith(("clamp_min(", "scalar(clamp_min(")):
            bad.append(denominator)
    return bad


def check_vllm_panels() -> None:
    path = ROOT / VLLM_DASHBOARD
    if not path.exists():
        skip("vllm panels", "vllm-overview.json not created yet")
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("vllm panels", f"invalid JSON at line {exc.lineno}")
        return

    problems = []
    if doc.get("refresh") != "5s":
        problems.append(f"refresh must be '5s', got {doc.get('refresh')!r}")
    time_range = doc.get("time") or {}
    if time_range.get("from") != "now-30m" or time_range.get("to") != "now":
        problems.append(
            "time range must be now-30m -> now, "
            f"got {time_range.get('from')!r} -> {time_range.get('to')!r}"
        )

    panels = [p for p in walk_panels(doc.get("panels")) if p.get("type") != "row"]
    by_title = {p.get("title"): p for p in panels}

    for title, panel_type in REQUIRED_PANELS.items():
        panel = by_title.get(title)
        if panel is None:
            problems.append(f"missing panel {title!r}")
        elif panel.get("type") != panel_type:
            problems.append(f"{title!r} must be a {panel_type} panel, got {panel.get('type')!r}")

    up = [t.get("expr") for t in (by_title.get("Server Status") or {}).get("targets") or []]
    if up and up != ['up{job="vllm"}']:
        problems.append(f"'Server Status' must query up{{job=\"vllm\"}}, got {up}")

    for panel in panels:
        title = panel.get("title")
        exprs = [t.get("expr") or "" for t in panel.get("targets") or []]
        if not exprs:
            problems.append(f"{title!r} has no targets")

        for expr in exprs:
            unknown = sorted({family(m) for m in METRIC_RE.findall(expr)} - CONFIRMED_METRICS)
            if unknown:
                problems.append(
                    f"{title!r} queries {', '.join(unknown)}, which the deployed server does not"
                    " expose (tasks/vllm-findings.md)"
                )
            for denominator in unguarded_divisions(expr):
                problems.append(
                    f"{title!r} divides by {denominator!r} without clamp_min; an idle server"
                    " would read NaN"
                )

        if panel.get("type") in ("stat", "gauge"):
            reduce = (panel.get("options") or {}).get("reduceOptions") or {}
            if reduce.get("values") is not False:
                problems.append(f"{title!r} must show a single value (reduceOptions.values false)")
            if "lastNotNull" not in (reduce.get("calcs") or []):
                problems.append(f"{title!r} must reduce with lastNotNull")
            if any(expr.rstrip().endswith("> 0") for expr in exprs):
                problems.append(
                    f"{title!r} filters idle samples with '> 0'; stat panels should read 0 when idle"
                )

    if problems:
        fail("vllm panels", "; ".join(problems))
    else:
        ok("vllm panels", f"{len(panels)} panel(s), all metrics confirmed")
