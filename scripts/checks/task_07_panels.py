"""Task 7 acceptance (tasks/task-07-panels.md): the required panels with the
exact expressions, throughput derived with rate() from the monotonic counters,
the clamp_min guard on every division, stat panels reduced to a single value,
and the 30m/5s dashboard defaults.

Throughput note: Task 7 originally graphed llamacpp:predicted_tokens_seconds
and llamacpp:prompt_tokens_seconds directly, because they are gauges. Upstream
llama.cpp computes those two gauges over the window since the last poll and
resets that bucket on every /metrics *and* /health request, so any second
poller (a container HEALTHCHECK, a load balancer) drains the bucket and
Prometheus reads 0 during active inference. The counters are monotonic and
immune to that, so the throughput panels now use them and the two gauges are
banned from the dashboard.
"""

from __future__ import annotations

import json

from .common import fail, ok, skip, ROOT
from .grafana import walk_panels

ORDER = 50

TASK7_DASHBOARD = "monitoring/grafana/dashboards/llm-overview.json"

# Throughput is tokens per second *of processing time*: the token counter's rate
# divided by the matching seconds counter's rate. clamp_min keeps an idle server
# (0 / 0) at 0 instead of NaN.
GENERATION_TOK_S = (
    "rate(llamacpp:tokens_predicted_total[$__rate_interval])"
    " / clamp_min(rate(llamacpp:tokens_predicted_seconds_total[$__rate_interval]), 0.001)"
)
PROMPT_TOK_S = (
    "rate(llamacpp:prompt_tokens_total[$__rate_interval])"
    " / clamp_min(rate(llamacpp:prompt_seconds_total[$__rate_interval]), 0.001)"
)

# The reset-on-poll gauges Task 7 originally used; banned from the dashboard.
RESET_PRONE_GAUGES = (
    "llamacpp:predicted_tokens_seconds",
    "llamacpp:prompt_tokens_seconds",
)

# title -> (panel type, exact target expressions in refId order)
TASK7_PANELS = {
    "Generation tok/s": ("stat", [GENERATION_TOK_S]),
    "Prompt tok/s": ("stat", [PROMPT_TOK_S]),
    "Active Requests": ("stat", ["llamacpp:requests_processing"]),
    "CONTEXT HIGH-WATER": ("stat", ["llamacpp:n_tokens_max"]),
    "Throughput": ("timeseries", [GENERATION_TOK_S, PROMPT_TOK_S]),
    "Request Activity": (
        "timeseries",
        ["llamacpp:requests_processing", "llamacpp:requests_deferred"],
    ),
    "Speculative Acceptance %": (
        "stat",
        [
            "100 * llamacpp:spec_decode_num_accepted_tokens_total"
            " / clamp_min(llamacpp:spec_decode_num_draft_tokens_total, 1)"
        ],
    ),
    "Speculative Draft Tokens": ("stat", ["llamacpp:spec_decode_num_draft_tokens_total"]),
    "Speculative Accepted Draft Tokens": (
        "stat",
        ["llamacpp:spec_decode_num_accepted_tokens_total"],
    ),
    "Prompt Tokens (total)": ("stat", ["llamacpp:prompt_tokens_total"]),
    "Generated Tokens (total)": ("stat", ["llamacpp:tokens_predicted_total"]),
}


def check_task7_panels() -> None:
    """tasks/task-07-panels.md: required panels, exact expressions, no reset-prone gauges."""
    path = ROOT / TASK7_DASHBOARD
    if not path.exists():
        skip("task7 panels", "llm-overview.json not created yet")
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail("task7 panels", f"invalid JSON at line {exc.lineno}")
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

    panels = {p.get("title"): p for p in walk_panels(doc.get("panels"))}
    for title, (panel_type, exprs) in TASK7_PANELS.items():
        panel = panels.get(title)
        if panel is None:
            problems.append(f"missing panel {title!r}")
            continue
        if panel.get("type") != panel_type:
            problems.append(f"{title!r} must be a {panel_type} panel, got {panel.get('type')!r}")
        got = [t.get("expr") for t in panel.get("targets") or []]
        if got != exprs:
            problems.append(f"{title!r} targets must be {exprs}, got {got}")
        for expr in got:
            for gauge in RESET_PRONE_GAUGES:
                if expr and gauge in expr:
                    problems.append(
                        f"{title!r} uses {gauge}; that gauge is reset by any /metrics or"
                        " /health poll and reads 0 under load, so derive throughput from"
                        " the counters instead"
                    )
        if panel_type == "stat":
            reduce = (panel.get("options") or {}).get("reduceOptions") or {}
            if reduce.get("values") is not False:
                problems.append(
                    f"{title!r} stat panel must show a single value (reduceOptions.values must be false)"
                )
            if "lastNotNull" not in (reduce.get("calcs") or []):
                problems.append(f"{title!r} stat panel must reduce with lastNotNull")

    if problems:
        fail("task7 panels", "; ".join(problems))
    else:
        ok("task7 panels", f"{len(TASK7_PANELS)} panel(s) verified")
