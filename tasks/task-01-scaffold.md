# Task 1 — Scaffold the directory tree

**Depends on:** Task 0 (for `LLM_NETWORK`)
**Produces:** `monitoring/` tree, `.env.example`, `.gitignore`, `.gitattributes`
**Runs on:** either machine
**Checkpoint:** none (feeds A)

## Do

Create the layout from plan §1, empty for now:

```
monitoring/
├── prometheus/
├── grafana/provisioning/datasources/
├── grafana/provisioning/dashboards/
└── grafana/dashboards/
```

The GPU exporter directory is deliberately absent — Phase 2 creates it, and an empty placeholder just invites scope creep.

`.gitignore`:
```
.env
```

`.gitattributes` — you author on Windows and run on Linux:
```
* text=auto eol=lf
```
The YAML and JSON parsers tolerate CRLF, so this changes nothing today. It prevents the Phase 2 exporter script failing with a confusing `bad interpreter` error from a CRLF shebang.

`.env.example`:
```
GRAFANA_PORT=3001

# Existing Docker network shared with llama-server / Open WebUI (Task 0).
# The llama-server *container name* is NOT here — it must be literal in
# prometheus/prometheus.yml, which does not expand env vars (correction #1).
LLM_NETWORK=
```

Only two variables. Retention is not among them (correction #2) — it lives in `prometheus.yml` and is a set-once decision.

## Verify

Copy `.env.example` to `.env` on the Ubuntu server and fill in `LLM_NETWORK` from `00-findings.md`. Everything from here runs out of `monitoring/`.

## Done when

The tree exists, `.env` is filled in on the server, and `.env` is gitignored.
