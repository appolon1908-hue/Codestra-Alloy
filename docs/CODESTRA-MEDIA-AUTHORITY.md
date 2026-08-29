# Codestra Grafana Alloy Authority

Principal repository: `appolon1908-hue/Codestra-Alloy`
Canonical service host: `allo.codestra.media`
Canonical DNS target: `37.27.128.39`
TTL: `600`

DNS has been externally verified. No alternate authoritative hostname is permitted.

## Ownership
Own Grafana Alloy agent/collector configuration, discovery, telemetry pipelines, relabeling/redaction policy, remote-write/export destinations and upgrade runbooks. Do not own Loki, Tempo, Prometheus storage, Grafana dashboards, OpenTelemetry application instrumentation, Caddy or secrets.

## Exposure
Private/internal only. DNS may exist, but Alloy administration/listener ports must be restricted to approved private networks and telemetry sources.

## Integration
Upstream: hosts, containers, logs, metrics and traces from approved systems. Downstream: Prometheus-compatible metrics destinations, Loki, Tempo and/or OpenTelemetry Collector according to the reviewed pipeline.

## Branch policy
Persistent: `main`, `development`, `test`, `staging`, `production`.
Temporary: `feature/*`, `fix/*`, `upgrade/*`, `security/*`, `docs/*`, `hotfix/*`, optional `release/*`, `rollback/*`.
Promotion: work -> development -> test -> staging -> production -> main.
