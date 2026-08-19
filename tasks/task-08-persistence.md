# Task 8 — Persistence check

**Depends on:** Task 7
**Produces:** nothing — this task is verification
**Runs on:** Ubuntu server
**Checkpoint:** close-out

One of the plan's definition-of-done items: data must survive a container restart.

## Do

```bash
docker compose down     # WITHOUT -v
docker compose up -d
```

`-v` deletes the named volumes. That is the one flag that makes this test destroy exactly what it's meant to verify.

## Verify

- Historical data is still in the throughput graph — the window before the restart is intact, confirming `prometheus-data` persisted.
- The dashboard still loads, confirming provisioning re-ran cleanly against the existing `grafana-data`.

## Done when

Both hold. If Prometheus data vanished, the `prometheus-data:/prometheus` mount is wrong — likely a `command:` block reintroducing a different `--storage.tsdb.path` (see correction #2).
