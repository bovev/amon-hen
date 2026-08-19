# Task 9 — README and measurements

**Depends on:** Tasks 7–8
**Produces:** `monitoring/README.md`
**Runs on:** Ubuntu server
**Checkpoint:** close-out — the last task

## Do — the README

Keep it short. Plan §20 asks for only:

- The four commands: `docker compose up -d`, `ps`, `logs -f`, `down`
- The dashboard URL, plus the SSH-tunnel line that actually reaches it from Windows
- The required `--metrics` flag on llama-server

Three things from earlier tasks also belong here, because they are what a future reader would otherwise have to re-derive:

- The **pinned image tags** you actually tested (correction #4)
- That **`CONTEXT HIGH-WATER` is a high-water mark**, not current utilisation, and that current-vs-configured needs a `/slots` collector
- Whether the **speculative-decoding panels exist** for your llama.cpp build

## Do — the three measurements

This is the part that's easy to skip and is genuinely the last real work. The plan's definition-of-done requires all three written down.

**1. Resource usage.** `docker stats` for both containers in three states: idle, dashboard open, inference active. Target is well under 2 GB total — a project goal, not an upstream guarantee.

**2. Monitoring ON vs OFF.** One identical inference benchmark, run both ways. A few percent of run-to-run variance is fine; a clear persistent regression is not, and would mean the stack has failed its primary constraint.

**3. Idle GPU behaviour.** `rocm-smi` baseline first, then again after several minutes of Prometheus scraping with no LLM requests. It passes if the GPU settles into essentially the same idle state.

`rocm-smi` is a Linux ROCm tool, so on the Ubuntu server this runs exactly as the plan describes — no caveat. Take the readings even though nothing in Phase 1 touches the GPU: this is the idle baseline the Phase 2 exporter gets compared against, and it is much harder to reconstruct once something is polling the card.

## Done when

The README exists and all three measurements are recorded with real numbers.

## Then stop

Plan's instruction, and it is deliberate: once these pass, don't keep expanding. No Node Exporter, no Loki/Tempo/Alertmanager, no custom frontend. The AMD GPU exporter is Phase 2, starting from this measured baseline.
