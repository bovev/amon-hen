# Task 6 — Provision the dashboard loader → **CHECKPOINT B**

**Depends on:** Task 5
**Produces:** `grafana/provisioning/dashboards/dashboards.yml`, one-panel `grafana/dashboards/llm-overview.json`
**Runs on:** either machine
**Checkpoint:** B — provisioning works

The goal here is the *pipeline*, not the dashboard. Build one panel, prove it loads from a file, and only then design (Task 7).

## Do

`grafana/provisioning/dashboards/dashboards.yml`:
```yaml
apiVersion: 1
providers:
  - name: local
    type: file
    allowUiUpdates: false
    options:
      path: /var/lib/grafana/dashboards
```

Then `grafana/dashboards/llm-overview.json` with **one** panel: server status, `up{job="llama_cpp"}`, as a stat panel showing UP/DOWN. This is plan §13, and it is the right first panel because Task 4 already proved the underlying query returns 1.

## Three JSON rules that cause silent failures

These fail by the dashboard simply not appearing — no error in the UI, and the log line is easy to miss:

- **`"id": null`** at the top level. A non-null `id` collides with an existing dashboard and the file is skipped.
- **Set a stable `"uid"`** and `"title": "LLM Overview"`. The uid is how the dashboard keeps its identity across reprovisioning.
- **Every panel's datasource is `{"type": "prometheus", "uid": "prometheus"}`**, matching the uid pinned in Task 5.

`allowUiUpdates: false` is deliberate: it makes Grafana reject UI edits to this dashboard, so the file stays the source of truth. Expect to edit JSON by hand in Task 7 — that is the cost of the plan's "reproducible from Git" requirement.

## Verify

Restart Grafana. "LLM Overview" appears in the dashboard list without anyone touching the UI, and the panel reads UP.

## Done when

The dashboard loads from the file and shows correct server status. That is Checkpoint B — the provisioning pipeline works end to end, and everything after this is panel work.
