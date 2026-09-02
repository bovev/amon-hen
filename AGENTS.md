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
2. Local-coder implements only that task, runs relevant verification, and reports the changes — including a mapping from every acceptance criterion to the file and line satisfying it.
3. Orchestrator delegates the result to `code-reviewer`.
4. Reviewer forms findings from the task file and the diff **before** reading the coder's summary, then returns `ACCEPT` or `REJECT`.
5. On `REJECT`, orchestrator sends the findings back to `local-coder` for correction and repeats review.
6. Only after `ACCEPT` may the orchestrator mark the task complete and continue.

Rules:

* Orchestrator does not implement source changes.
* Local-coder does not change task status or start another task.
* Code-reviewer does not implement fixes.
* Reviewer findings must be resolved before acceptance.
* Do not work ahead on later tasks.

### Task state

Status lives in the frontmatter of each `tasks/task-NN-*.md`, written only by the orchestrator:

```yaml
---
task: 7
status: done          # todo | in-progress | done
accepted_at: 72952c6  # the commit that accepted it
---
```

This is the record of what is done. Do not infer it from commit subjects — they are prose and have been wrong. `progress.md` describes the current task only and is overwritten each time; it is not a state store. `py scripts/verify.py` enforces the frontmatter, the single in-progress task, in-order completion, and that every `accepted_at` is a real ancestor of `HEAD`.

### Findings are authoritative

`tasks/00-findings.md` is the source of truth for metric names, scrape target, network, ports and container names. Names in task files, `implementation-guide.md`, `intial_plan.md` and `README.md` are illustrative and are frequently wrong. Where they disagree, `00-findings.md` wins, and a diff that follows an example against it is a blocking review finding.

### Severity

Findings are `blocking-correctness` (violates an acceptance criterion, an AGENTS.md invariant, or `00-findings.md`), `blocking-scope` (work the task did not ask for), or `observation` (style and preference). Only the first two justify `REJECT`. Runtime behaviour that cannot be observed from the files is never blocking — it is `Deployment verification pending`.

### Rework limit

Stop after the second `REJECT` on the same task and escalate to the human with the task file, both reviews, and the current diff. A third rejection usually means the task specification is wrong rather than the implementation.

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

It covers every file-level check the tasks require: YAML parsing, JSON parsing, LF line endings, task state, agent frontmatter and agent policy, and the Compose, Prometheus, datasource and dashboard invariants listed above. Agents must not invent or search for lint, format, schema, frontmatter, type-check or build commands — there are none. If a check is worth running, add it under `scripts/checks/` instead of running something ad hoc.

### Where checks live

`scripts/verify.py` is only a runner. The checks are modules in `scripts/checks/`, each declaring an `ORDER` and defining `check_*` functions that the runner discovers automatically. Adding a check means adding a file; the runner never changes, and two tasks adding checks never touch the same lines.

Module naming carries meaning and permission:

* `task_NN_<slug>.py` — acceptance checks for one task. `local-coder` may write these.
* everything else (`hygiene`, `compose`, `prometheus`, `grafana`, `workflow`, `common`) — architectural invariants that apply to all work. Only a human edits these; they define the rules the coder is graded against, so a coder that could loosen them would be grading itself.

**A task's checks stay after the task is accepted.** That is when they start earning their keep: `task_07_panels.py` exists so a later task cannot silently break a dashboard query. Deleting a previous task's check module is a blocking review finding, and so is any diff where `local-coder` touched the runner or an invariant module. Within a task module the coder may only **add**; removing, weakening or narrowing an existing check is an automatic `REJECT`. The reviewer reads any diff under `scripts/` first and separately.

Checks report missing files as `SKIP`, never `FAIL`, so early tasks pass before later tasks create their outputs.

### Tests (Phase 2)

`scripts/checks/` asserts things about **files** — that a compose file binds to
loopback, that a dashboard uses the right datasource UID. Phase 2 introduces the
first real **code** in this repository, the AMD GPU exporter, and assertions
about code are unit tests. Keep the two apart: no check module imports exporter
internals, and no test reads `monitoring/`.

Exporter tests are `pytest`, living beside the code in `exporters/gpu/tests/`,
driven by fixture files of `rocm-smi --json` output captured from the real card
and committed. Test the pure functions only — parsing a payload, rendering
Prometheus text, handling a field the hardware does not report. Nothing invokes
`rocm-smi`; it does not exist on the authoring machine and no agent may run it.

**`py scripts/verify.py` remains the only verification command.** It does not
become one of two. A check module runs `pytest` as a subprocess and reports the
result as a single line like any other check, skipping when pytest is not
installed. This is not cosmetic: the deny-by-default `bash` policy in every
agent profile allows exactly that one command, and a second entry point would
mean allowing agents to run `py -m ...`, which is also how packages get
installed and servers get started.

Tests carry the same rules as task check modules: `local-coder` may add them,
never weaken or delete them, and a test that would pass against a broken
implementation is a blocking review finding.

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
