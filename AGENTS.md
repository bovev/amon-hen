# AGENTS.md

## Source Of Truth

* `tasks/` define implementation and override conflicting examples elsewhere.
* Execute Tasks in order unless a task explicitly states otherwise.
* Task 0 runs first on the Ubuntu deployment server and produces `tasks/00-findings.md`. Treat its discovered network, scrape target, ports, and metric names as authoritative.
* Author files on Windows; run deployment and runtime verification on Ubuntu using Docker Engine and Compose v2 (`docker compose`).
* Use LF line endings.

## Authoring Machine

Agents run on the Windows authoring box and only edit files. Nothing in this repository runs, builds, installs or deploys here, so there is no environment to inspect: no interpreters, runtimes, package managers, container engines, remote hosts or installed tool versions. Never check for them.

Deployment and runtime verification happen on the Ubuntu server, performed by a human, outside this workflow.

## Agent Workflow

Use three roles for implementation:

* **orchestrator** — owns task sequencing, task state, and delegation.
* **local-coder** — implements and verifies exactly one assigned task.
* **code-reviewer** — independently reviews the implementation against the task specification.

Process one task at a time:

1. Orchestrator selects the next incomplete task and delegates it to `local-coder`.
2. Local-coder implements only that task, runs relevant verification, and reports the changes.
3. Orchestrator delegates the result to `code-reviewer`.
4. Reviewer returns `ACCEPT` or `REJECT`.
5. On `REJECT`, orchestrator sends the findings back to `local-coder` for correction and repeats review.
6. Only after `ACCEPT` may the orchestrator mark the task complete and continue.

Rules:

* Orchestrator does not implement source changes.
* Local-coder does not change task status or start another task.
* Code-reviewer does not implement fixes.
* Reviewer findings must be resolved before acceptance.
* Do not work ahead on later tasks.

## Architecture Constraints

Phase 1 is deliberately small:

* Prometheus
* Grafana OSS
* one file-provisioned `LLM Overview` dashboard

Do not add Phase 2 components, additional observability services, databases, proxies, exporters, or a custom frontend.

Do not modify llama-server inference settings except enabling `--metrics`.

Prometheus must scrape llama-server through its existing Docker network using the service alias and in-container port discovered in Task 0.

Only Grafana may be published to the host, bound to loopback:

`127.0.0.1:${GRAFANA_PORT:-3001}:3000`

Do not expose Prometheus or Grafana to the LAN.

Keep llama-server's existing Compose stack separate from this repository.

Use pinned image versions required by the task specifications, named data volumes, and read-only configuration mounts.

## Configuration Invariants

* Prometheus does not expand environment variables in `prometheus.yml`; use the exact Task 0 scrape target literally.
* `.env` contains only deployment-specific values defined by the task specs. Commit `.env.example`, never `.env`.
* Metric names from the deployed `/metrics` endpoint are authoritative; documentation examples are not.
* Do not apply `rate()` to metrics that are already throughput gauges.
* Grafana datasource and dashboards must be file-provisioned, not configured manually in the UI.
* Prometheus datasource URL is `http://prometheus:9090` with UID `prometheus`.
* Provisioned dashboard JSON must use the stable datasource UID and remain non-editable through Grafana.
* `llamacpp:n_tokens_max` is a context high-water mark, not current context utilization or configured context capacity.
* Only create speculative-decoding panels when the deployed server exposes the required counters.

## Verification

`py scripts/verify.py` is the only verification command in this repository.

It covers every file-level check the tasks require: YAML parsing, JSON parsing, LF line endings, agent frontmatter, and the Compose, Prometheus, datasource and dashboard invariants listed above. Agents must not invent or search for lint, format, schema, frontmatter, type-check or build commands — there are none. If a check is worth running, add it to `scripts/verify.py` instead of running something ad hoc.

Anything the script cannot check from files is runtime verification. It happens on the Ubuntu deployment server, performed by a human, and is reported as `Deployment verification pending` rather than attempted.

Follow task checkpoints instead of implementing the full stack before testing.

At minimum:

* validate Compose configuration before first boot;
* prove Prometheus can scrape llama-server;
* prove Grafana provisioning works from files;
* verify dashboard metrics against real inference traffic;
* verify persistence without deleting named volumes;
* complete the measurements required by Task 9.

Use container-internal Prometheus queries rather than exposing its port.

For persistence tests, never use `docker compose down -v`.

Record required benchmark and resource measurements in `monitoring/README.md`.

Once Task 9 and the MVP checklist pass, stop expanding the system.
