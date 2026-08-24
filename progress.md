# Progress — Task 9 (README and measurements)

IMPLEMENTATION_COMPLETE

## Files changed
- `monitoring/README.md`
- `scripts/verify.py`

## What changed
- Added the Phase 1 monitoring README with operating commands, dashboard access,
  pinned image tags, dashboard caveats, and required measurements.
- Recorded real resource, benchmark, and idle GPU measurements from the Ubuntu
  deployment server.
- Strengthened `py scripts/verify.py` so Task 9 fails on placeholder
  measurements and passes only with plausible numeric values and units.

## Verification performed
- `py scripts/verify.py` passed all 10 checks.
- Independent code review: `ACCEPT`.

## Deployment verification
All Task 9 runtime measurements were supplied from the Ubuntu deployment server
and recorded in `monitoring/README.md`.

## Next
Stop. Phase 1 MVP checklist is complete; do not expand the system.
