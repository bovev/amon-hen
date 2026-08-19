# Task 4 — First boot → **CHECKPOINT A**

**Depends on:** Tasks 1–3
**Produces:** nothing — this task is verification
**Runs on:** Ubuntu server
**Checkpoint:** A — stack alive

## Do

```bash
docker compose up -d
docker compose ps
```

Use `docker compose logs -f` only if a container is unhealthy or restart-looping.

## Verify — in order, stop at the first failure

**1. Both containers are `running`, not restart-looping.**
A Prometheus restart loop here is almost always a YAML error in Task 2; the logs name the line.

**2. Grafana answers on the server:**
```bash
curl -sI http://localhost:3001    # expect 302
```
Then open the SSH tunnel from Windows and confirm the login page renders at `http://localhost:3001` (default `admin`/`admin`). Check both sides separately — it tells you whether a failure is Grafana or the tunnel.

**3. The scrape target is UP:**
```bash
docker compose exec prometheus promtool query instant http://localhost:9090 'up{job="llama_cpp"}'
```
Expect a value of `1`.

## If `up` is 0

Prometheus is healthy but cannot reach llama-server. Find which half is broken from inside the container:

```bash
docker compose exec prometheus wget -qO- http://llama-server:8080/metrics | head -5
```

- **Name does not resolve** → Prometheus isn't on the `llm` network, or the container name is wrong. Check with `docker network inspect <llm-network>` and confirm the Prometheus container now appears among its members.
- **Resolves, connection refused** → wrong port. You probably used the published host port instead of the in-container one.

## Done when

`up{job="llama_cpp"}` is `1`. **Do not continue to Task 5 until it is** — every panel in Task 7 depends on this target, and debugging a blank dashboard is much harder than debugging a DOWN target.
