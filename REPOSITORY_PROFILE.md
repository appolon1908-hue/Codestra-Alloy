# Repository Profile — `Codestra-Alloy`

## Identity

- **Repository:** `appolon1908-hue/Codestra-Alloy`
- **Category:** Observability agent — Grafana Alloy
- **Visibility:** `public`
- **Default branch:** `main`
- **Canonical hostname:** `allo.codestra.media`
- **Exposure:** Internal/private only; diagnostics must not be Internet-public
- **Authority:** Primary approved discovery, collection, processing, buffering, and forwarding authority for logs, metrics, and traces assigned to Alloy

## Purpose

Discovers approved targets and collects, processes, buffers, and forwards telemetry to Prometheus-compatible metrics paths, Loki, Tempo, or the OpenTelemetry Collector according to explicit ownership rules.

## Owns

- Alloy components, discovery, collection, relabeling, redaction, batching, queues, retries, and forwarding configuration
- Agent health, diagnostics, resource controls, immutable packaging, and deployment source
- Collection ownership boundaries that prevent duplicate telemetry pipelines

## Does not own

- Long-term metrics, logs, or trace storage
- Application instrumentation source
- Collection of secrets, PII, business payloads, or arbitrary high-cardinality labels

## Key integrations

- Prometheus, Loki, Tempo, and OpenTelemetry Collector
- Docker, host, service, or file sources explicitly approved by infrastructure policy
- Grafana operational dashboards

## Current priorities

1. Finalize collection ownership with OpenTelemetry Collector
2. Enforce redaction, label/cardinality budgets, queues, retries, and backpressure
3. Prove target discovery, outage buffering, restart recovery, and synthetic telemetry
4. Add immutable packaging, upgrade, rollback, and configuration evidence

## Governance and safety

- Promotion model: `feature/docs/fix/security/upgrade -> development -> test -> staging -> production -> main`.
- Diagnostics port `12345`, where enabled, must remain private; `allo.codestra.media` must not expose Alloy publicly.
- Never commit credentials, private keys, customer payloads, tokens, or secret-bearing telemetry fixtures.
- Every collection source requires explicit ownership, redaction, retention, and cardinality review.
- Merge does not start Alloy, mount sources, forward telemetry, expose diagnostics, or deploy software.

## Account-wide catalog

See `appolon1908-hue/documentaions/REPOSITORY_CATALOG.md`.
