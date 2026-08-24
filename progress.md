# Progress — Task 5 (Prometheus datasource provisioning)

IMPLEMENTATION_COMPLETE

## Files changed
- `monitoring/grafana/provisioning/datasources/prometheus.yml` (new)

## What changed
Provisioned Prometheus as Grafana's default datasource with the stable
`prometheus` UID and the internal URL `http://prometheus:9090`.

## Verification performed
- Parsed the provisioning file as YAML and checked every required value.
- Confirmed the file uses LF line endings.
- Confirmed the existing Compose mount exposes the file read-only to Grafana.

## Deployment verification pending
Restart Grafana on the Ubuntu deployment server and confirm the provisioned
datasource connection succeeds. No deployment host was available from the
Windows authoring environment.

## Next
Task 6 — dashboard provisioning.
