---
task: 5
status: done
accepted_at: 728dbfc
---

# Task 5 — Provision the Prometheus datasource

**Depends on:** Task 4 (Checkpoint A)
**Produces:** `monitoring/grafana/provisioning/datasources/prometheus.yml`
**Runs on:** either machine
**Checkpoint:** none (feeds B)

## Do

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

## Two things to get right

**`uid: prometheus` is load-bearing.** Without it Grafana generates a random uid, and the dashboard JSON in Tasks 6–7 would have to hardcode whatever that happened to be. Pinning it is what makes the dashboard survive a `docker compose down -v` and reprovision cleanly on a fresh volume.

**The URL is `http://prometheus:9090`** — the Compose service name on the `monitoring` network. Not `localhost`, which inside the Grafana container means Grafana itself.

## Verify

```bash
docker compose restart grafana
```

In the UI the datasource appears marked as provisioned, and its connection test succeeds.

**Do not edit or save the provisioned datasource in the UI.** The whole point of the plan's §7 is that there is no manual setup step; a UI edit creates state that isn't in Git and will be silently reverted on the next restart.

## Done when

Grafana starts already connected to Prometheus, with nobody having touched the Data Sources page.
