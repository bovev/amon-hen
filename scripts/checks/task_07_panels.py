"""Task 7 acceptance (tasks/task-07-panels.md): the required panels with the
exact Task 0 expressions, no rate() on the throughput gauges, the clamp_min
guard on the speculative acceptance division, stat panels reduced to a single
value, and the 30m/5s dashboard defaults.

Kept after acceptance: this is what catches a later task silently breaking a
panel query.
"""

from __future__ import annotations

import json

from .common import fail, ok, skip, ROOT
from .grafana import walk_panels

ORDER = 50

TASK7_DASHBOARD = "monitoring/grafana/dashboards/llm-overview.json"

# title -> (panel type, exact target expressions in refId order)
TASK7_PANELS = {
    "Generation tok/s": ("stat", ["llamacpp:predicted_tokens_seconds"]),
    "Prompt tok/s": ("stat", ["llamacpp:prompt_tokens_seconds"]),
    "Active Requests": ("stat", ["llamacpp:requests_processing"]),
    "CONTEXT HIGH-WATER": ("stat", ["llamacpp:n_tokens_max"]),
    "Throughput": (
        "timeseries",
        ["llamacpp:predicted_tokens_seconds", "llamacpp:prompt_tokens_seconds"],
    ),
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
    """tasks/task-07-panels.md: required panels, exact expressions, no rate()."""
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
            if expr and "rate(" in expr:
                problems.append(
                    f"{title!r} applies rate() to {expr!r}; gauge metrics are queried directly"
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
