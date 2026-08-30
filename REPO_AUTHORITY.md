# Repository Authority

Canonical service hostname: `allo.codestra.media`
Canonical DNS A target: `37.27.128.39`
DNS TTL: `600`

This repository is the principal source authority for the Codestra Grafana Alloy deployment/configuration. Do not introduce alternate public hostnames or legacy domain names in configuration, documentation, examples, health checks, or deployment manifests.

Exposure policy: PRIVATE. DNS may resolve publicly, but Alloy receivers, administrative endpoints, and metrics endpoints must be reachable only from approved private/monitoring networks unless a separately reviewed ingestion case requires otherwise.

Upstream/downstream: applications/exporters may send approved telemetry to Alloy -> Alloy processes/routes telemetry to Prometheus/Loki/Tempo or OpenTelemetry according to configuration -> Grafana consumes the resulting data. Alloy must not become a privileged application write path.

Persistent branch model: `main`, `development`, `test`, `staging`, `production`. Temporary branches: `feature/*`, `fix/*`, `upgrade/*`, `security/*`, `docs/*`, `hotfix/*`, `release/*`, `rollback/*`.

Promotion: feature/fix/upgrade/security -> development -> test -> staging -> production -> main. Never upgrade directly on staging, production, or main.
