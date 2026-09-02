---
task: 0
status: done
accepted_at: 1569cbe
---

# Task 0 — Verify prerequisites

**Depends on:** nothing
**Produces:** `tasks/00-findings.md`
**Runs on:** Ubuntu server, over SSH
**Checkpoint:** none (feeds A)

Nothing here creates config. This task exists because Tasks 2, 3 and 7 all need facts that cannot be guessed from the authoring machine — and getting them wrong produces a stack that looks correct and silently collects nothing.

## Do

1. Confirm the Docker environment:
   ```bash
   docker ps                  # works without sudo
   docker compose version     # v2.x — the plugin, not docker-compose
   ```

2. Confirm llama-server runs with `--metrics`. If not, add the flag and restart it. **Change nothing else about the inference settings** — the plan is explicit that monitoring must not alter inference behaviour.

3. Capture the real metric names:
   ```bash
   curl -s http://localhost:8080/metrics > llama-metrics.txt
   grep '^llamacpp:' llama-metrics.txt | cut -d'{' -f1 | sort -u
   ```

4. Get the two names correction #3 depends on:
   ```bash
   docker network ls
   docker network inspect <llm-network> --format '{{range .Containers}}{{.Name}} {{end}}'
   ```
   If llama-server was started by its own Compose file, also check its network aliases — Compose registers the *service* name as an alias, which may differ from the container name:
   ```bash
   docker inspect <llama-container> --format \
     '{{range $n, $c := .NetworkSettings.Networks}}{{$n}}: {{$c.Aliases}}{{"\n"}}{{end}}'
   ```
   Either the container name or any alias works as a scrape target. **Prefer the service alias if one exists** — it survives container recreation.

5. Note the port llama-server listens on **inside** its container. This is what Task 2 scrapes, and it is not necessarily the published host port.

6. Confirm port 3001 is free: `ss -tln | grep 3001` (expect no output).

## Record

Write the answers to `tasks/00-findings.md`. Later tasks read this file rather than re-running the commands:

```markdown
# Task 0 findings — <date>

- Docker network name:        <exact name>          → .env LLM_NETWORK
- llama-server scrape target: <name>:<in-container port>  → prometheus.yml (literal, per correction #1)
- Metric names present:
  - throughput:    llamacpp:...
  - requests:      llamacpp:...
  - counters:      llamacpp:...
  - context:       llamacpp:n_tokens_max
  - speculative:   <exact names, or NONE>
```

## Verify

You have a concrete list of `llamacpp:*` names from **this** build. The names in `intial_plan.md` come from documentation, not from your installation — Task 7 writes queries against your list, not against the plan.

Pay attention to the **speculative-decoding counters**: they vary most between llama.cpp versions. If no draft/accepted counters appear, Task 7e becomes a documented no-op rather than something to debug later.

## Done when

`00-findings.md` exists with the network name, the scrape target, and the metric list filled in.

## Blocked if

`/metrics` returns 404 → the `--metrics` flag didn't take effect. Nothing downstream can work until this returns Prometheus-format text.
